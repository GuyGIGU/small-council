"""A read-only snapshot of one council run, for the status views (views/status.py and its parts).

It reads what the run already records. The run's files are:
- session-state.md, run-plan.tsv and seats.tsv;
- events.tsv and gates/*.json;
- repairs.jsonl and claims.jsonl.
It also reads the memory proposals waiting in the council home. It never writes a file, appends an
event or changes a run. On Windows each file is opened with delete sharing, so a helper that replaces
a file by rename while the snapshot reads it is never refused. Every value is stripped of control
characters, and a file that is a link, leads outside the run, is too large or does not parse is
skipped rather than followed or trusted. Every fact comes from a file the helper or the Chair already
writes; the snapshot adds no state of its own.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

from council.records import cells, events as event_stream, gates as gate_files, plan as run_plan, state as run_state
from council.records import usage
from council.records.cells import clean, integer
from council.records.paths import contained, linked, text_of
from council.records.seats import corrections as corrections_of
from council.records.stages import COUNCIL_NEXT_AT_OPEN as NEXT_AT_OPEN

Snap = Dict[str, Any]
CLAIM_MODES = ("council-review", "council-plan", "council-research")   # the modes that keep a claim index
CONVERGE_RESULT = re.compile(r"(not met|partly met|partly|blocked|met)\b")
CONVERGE_KEYS = {"not met": "not_met", "partly met": "partly", "partly": "partly", "blocked": "blocked", "met": "met"}


def header(run: Path) -> dict[str, str]:
    """The run's session-state header, read by records.state.header's rule, each value cleaned."""
    return {key: clean(value) for key, value in run_state.header(run_state.text(run)).items()}


def decisions(run: Path, limit: int = 20) -> list[str]:
    """The user's recorded decisions (council state decision=), oldest first, each cleaned and cut to 300."""
    return [clean(entry)[:300] for entry in run_state.decisions(run_state.text(run))][-limit:]


def next_step(state: dict[str, str]) -> str:
    """The run's recorded next step. The one written at run open is Convene's own: nothing replaces it
    on its own, so once the run has left convene it is stale and reads as no step at all. A step the
    Chair recorded is shown as written."""
    step = state.get("next", "")
    if step.strip() == NEXT_AT_OPEN and state.get("phase", "") not in ("", "convene"):
        return ""
    return step


def jsonl(run: Path, name: str) -> list[dict[str, Any]]:
    return cells.jsonl_rows(text_of(run / name, run))


def repairs_of(run: Path) -> dict[str, dict[str, Any]]:
    """Each repair task's last attempt, and the category of its last failed attempt (a trail that
    resolved ends on a RESOLVED row, which is no failure category)."""
    tasks: dict[str, dict[str, Any]] = {}
    for row in jsonl(run, "repairs.jsonl"):
        task = clean(row.get("task", "?")) or "?"
        result, category = clean(row.get("result", "")), clean(row.get("category", ""))
        failed = category if result == "failed" else tasks.get(task, {}).get("failure_category", "")
        tasks[task] = {"gate": clean(row.get("gate", "")), "attempts": integer(row.get("attempt")),
                       "result": result, "category": category, "next": clean(row.get("action", "")),
                       "failure_category": failed}
    return tasks


def claim_index_stale(run: Path) -> bool:
    """Fail closed on missing/unreadable indexes; reading never refreshes the index."""
    sources = [p for p in [run / "synthesis.md", *run.glob("verify-*.md")] if p.is_file()]
    try:
        index = run / "claims.jsonl"
        if linked(index) or any(linked(p) for p in sources):
            return True
        if not index.is_file():
            return bool(sources)
        # An index with no source files is an orphan. The indexed rows also name
        # their source files, which catches a deleted verifier even when every
        # remaining source is older than the index.
        if not sources or not (run / "synthesis.md").is_file():
            return True
        index_at = index.stat().st_mtime_ns
        if any(p.stat().st_mtime_ns > index_at for p in sources):
            return True
        for row in jsonl(run, "claims.jsonl"):
            refs = [row.get("source", "")]
            links = row.get("verification")
            if isinstance(links, list):
                refs.extend(link.get("ref", "") for link in links if isinstance(link, dict))
            for ref in refs:
                name = str(ref).split(":", 1)[0]
                if name == "synthesis.md" or re.fullmatch(r"verify-[A-Za-z0-9._-]+\.md", name):
                    source = run / name
                    if linked(source) or not source.is_file():
                        return True
        return False
    except OSError:
        return True


def claims_expected(run: Path, mode: str) -> bool:
    """A review, plan or research run keeps a claim index (the helper's close warns when it is missing), and a run
    with no recorded mode is read as one. Another mode keeps none — a build checks tasks, not claims — unless its
    folder holds a synthesis or an index all the same."""
    if mode in CLAIM_MODES or not mode:
        return True
    try:
        return (run / "synthesis.md").exists() or (run / "claims.jsonl").exists()
    except OSError:
        return True


def claims_of(run: str | Path, mode: str | None = None) -> dict[str, Any]:
    """by_verdict counts every indexed claim. shipped counts what the closing card reports: the kept claims,
    and the cut ones a verifier was sent anyway; self_checked, those only the Chair's own check covers.
    expected is False for a run that keeps no claim index (a build), which is then never out of date."""
    run = Path(run)
    if not claims_expected(run, header(run).get("mode", "") if mode is None else mode):
        return {"total": 0, "by_verdict": {}, "stale": False, "shipped": {}, "self_checked": 0, "expected": False}
    if claim_index_stale(run):
        return {"total": 0, "by_verdict": {}, "stale": True, "shipped": {}, "self_checked": 0, "expected": True}
    rows = jsonl(run, "claims.jsonl")
    verdicts: dict[str, int] = {}
    shipped: dict[str, int] = {}
    own = 0
    for row in rows:
        verdict = clean(row.get("verdict") or "UNVERIFIED").upper()[:24] or "UNVERIFIED"
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
        links = row.get("verification") if isinstance(row.get("verification"), list) else []
        if row.get("disposition") == "cut" and not links:
            continue                     # set aside by the Chair and never sent: not a verdict to report
        shipped[verdict] = shipped.get(verdict, 0) + 1
        if links and all(isinstance(link, dict) and link.get("self") for link in links):
            own += 1
    return {"total": len(rows), "by_verdict": dict(sorted(verdicts.items())), "stale": False,
            "shipped": dict(sorted(shipped.items())), "self_checked": own, "expected": True}


def converge_result(cell: str) -> str:
    """A Converge Result cell's verdict, read after its last arrow ("partly met → met" is met) by its first words:
    met, partly, not_met, blocked or other."""
    words = re.sub(r"[`*_]", "", re.split("→|->", cell)[-1]).strip().lower()
    found = CONVERGE_RESULT.match(words)
    return CONVERGE_KEYS[found.group(1)] if found else "other"


def converge_fixed(cell: str) -> bool:
    """A met result that records the check finding it short first: an earlier verdict before an arrow ("partly met →
    met"), or one named after the leading "met" ("met (after 8cbfc45; verify-5 partly met)")."""
    parts = re.split("→|->", cell)
    if len(parts) > 1:
        return converge_result(parts[0]) != "met"
    words = re.sub(r"[`*_]", "", cell).strip().lower()
    return re.search(r"\b(not met|partly met|partly|blocked)\b", words[3:]) is not None


def converge_of(run: str | Path, deliverable: str) -> dict[str, Any]:
    """A build's final check, from its log's '## Converge' table (council-implement writes it at Challenge): each
    task's final result, and whether a fix came after the check found it short. {"missing": why} when no such
    table can be read: no deliverable, one outside the council home's logs folder, unreadable, or without one."""
    run = Path(run)
    if not deliverable:
        return {"missing": "no build log recorded"}
    home = run.parent.parent
    logs, path = home / "logs", Path(deliverable)
    path = path if path.is_absolute() else home.parent / path
    if run.parent.name != "runs" or linked(logs) or not contained(path, logs):
        return {"missing": "the build log isn't in the council's logs folder"}
    content = text_of(path, logs)
    if not content:
        return {"missing": "the build log can't be read"}
    rows = converge_rows(content)
    if not rows:
        return {"missing": "the build log has no Converge table"}
    return {"rows": rows}


def converge_rows(content: str) -> list[dict[str, Any]]:
    """The rows of the table under the log's '## Converge' heading, keyed by its Task, Done when and Result."""
    rows: list[dict[str, Any]] = []
    inside, columns = False, None
    for line in cells.lines_of(content):
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip().lower() == "converge"
            continue
        if not inside:
            continue
        if not line.lstrip().startswith("|"):
            if columns is not None:
                break                               # the table ended
            continue
        row = [clean(c) for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if columns is None:
            names = [c.lower() for c in row]
            if "result" not in names:
                break
            columns = {name: names.index(name) for name in ("task", "done when", "result") if name in names}
            continue
        if all(re.fullmatch(r":?-{3,}:?", c) for c in row if c):
            continue                                # the header's rule
        cell = {name: row[at] if at < len(row) else "" for name, at in columns.items()}
        result = cell.get("result", "")
        final = converge_result(result)
        rows.append({"task": cell.get("task", "").replace("`", "")[:40] or str(len(rows) + 1),
                     "done_when": cell.get("done when", "").replace("`", "")[:200], "result": final,
                     "fixed_after": final == "met" and converge_fixed(result)})
        if len(rows) >= 500:
            break
    return rows


def events_of(run: Path, last: int) -> dict[str, Any]:
    stream = event_stream.table(run)
    if stream.too_large:
        return {"count": None, "malformed": 0, "last": [], "present": True, "header_ok": None, "too_large": True,
                "gates": {}, "chair": None}
    good = [r for r in stream.rows if len(r) == 7]
    shown = [{"seq": clean(r[1]), "at": clean(r[2]), "type": clean(r[3]), "subject": clean(r[4]),
              "value": clean(r[5]), "detail": clean(r[6])} for r in good[-last:]] if last else []
    gates: dict[str, dict[str, Any]] = {}   # every gate's runs from the stream: a re-run overwrites gates/<name>.json
    chair = None        # the latest reading of the Chair's own tokens (council run close; it covers every span so far)
    for r in good:
        if r[3] == "run.chair_usage" and clean(r[5]).isdigit():
            calls = re.search(r"(?:^|;)calls=([0-9]+)(?:;|$)", clean(r[6]))
            basis = re.search(r"(?:^|;)basis=([a-z]+)(?:;|$)", clean(r[6]))
            chair = {"tokens": int(clean(r[5])), "calls": int(calls.group(1)) if calls else None, "at": clean(r[2]),
                     "partial": bool(basis) and basis.group(1) == "partial"}
        if r[3] == "gate.finished":
            seen = gates.setdefault(clean(r[4]), {"passed": 0, "failed": 0, "last": ""})
            result = clean(r[5])
            if result in ("passed", "failed"):
                seen[result] += 1
                seen["last"] = result
    return {"count": len(good), "malformed": len(stream.rows) - len(good), "last": shown, "present": stream.present,
            "header_ok": stream.header_ok, "too_large": False, "gates": gates, "chair": chair}


def brief_names(snap: Snap) -> dict[str, str]:
    """Seat names as the brief gives them — "### <slug> — <what it checks> (<Seat name>)". Read once per
    snapshot, like every other run file."""
    cached = snap.get("_names")
    if cached is None:
        cached = {}
        run = Path(snap["run"].get("path") or ".")
        for line in cells.lines_of(text_of(run / "brief.md", run)):
            match = re.match(r"^###\s+([A-Za-z0-9._-]+)\s+[-—].*\(([^()]+)\)\s*$", line)
            if match:
                cached[match.group(1)] = clean(match.group(2))[:40]
        snap["_names"] = cached
    return cached


def proposals_in(home: str | Path | None) -> int | None:
    """How many entries wait under memory's ## Proposed section (### headings or - PROPOSED lines)."""
    if not home:
        return None
    content = text_of(Path(home) / "conventions.md", home)
    if not content:
        return None
    count, inside = 0, False
    for line in content.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().lower().startswith("propos")
        elif inside and (line.startswith("### ") or re.match(r"\s*-\s+PROPOSED\b", line)):
            count += 1
    return count


def snapshot(run: str | Path, home: str | Path | None = None, last_events: int = 8) -> Snap:
    run = Path(run)
    state = header(run)
    if "next" in state:
        state["next"] = next_step(state)     # every reader — the card, the summary — shares this
    fixes = corrections_of(run)
    seats = usage.seat_list(run, fixes)
    return {
        "run": {"id": clean(run.name), "path": str(run), **{k: state.get(k, "") for k in (
            "status", "mode", "phase", "updated", "opened", "closed", "size", "ask", "deliverable", "next", "actual",
            "waiting")}},
        "plan": run_plan.summary(run),
        "decisions": decisions(run),
        "seats": seats,
        "usage": usage.usage_totals(seats),
        "corrections": sorted(fixes.values(), key=lambda f: (f["seat"], f["field"])),
        "gates": gate_files.results(run),
        "repairs": repairs_of(run),
        "claims": claims_of(run, state.get("mode", "")),
        "events": events_of(run, last_events),
        "memory": {"proposed": proposals_in(home)},
    }
