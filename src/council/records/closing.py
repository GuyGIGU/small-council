"""What a close reads in a run and decides."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from council.records import bytewise, events, gate_table, home, map_file, plan, seat_files, stages, state, usage

MODES = ("council-review", "council-plan", "council-implement", "council-research", "council-postgame")
EARLY = ("convene", "prepare", "assign", "brief", "work", "build", "collect", "judge", "challenge")
PAUSED = "council run close --status paused --run %s"


def _field(run: Path, key: str) -> str:
    return state.field(state.text(run), key)


def undelivered(run: Path) -> str:
    """The refusal of a complete close for a run that never reached Deliver, or went back after it; ''."""
    mode, phase, name = _field(run, "mode"), _field(run, "phase") or "unknown", run.name
    if mode not in MODES or not _field(run, "events-schema"):
        return ""
    back = ""
    if events.path(run).is_file():                       # the stream, else the state's phase alone
        seen = False
        for row in events.table(run).rows:
            stage = (row + [""] * 6)[5] if row[3:4] == ["run.phase_changed"] else ""
            if stage == "deliver":
                seen, back = True, ""
            elif seen and not back and stage in EARLY:
                back = stage
        if seen and not back:
            return ""
    elif phase in ("deliver", "learn"):
        return ""
    if back:
        return ("%s can't close as complete: it went back to %s after Deliver and never came through Deliver again, so "
                "the user has no receipt for what changed since. Re-enter Deliver — %s — show the user the receipt "
                "(anything left open with it), then close. If the user paused the work, close it paused: " + PAUSED
                ) % (name, back, deliver_route(run), name)
    return ("%s can't close as complete: it never reached Deliver (it is at %s). If the user paused the work — \"stop "
            "for tonight\" too — close it paused: " + PAUSED + "; if it stopped for good: --status abandoned. "
            "Otherwise go on through Deliver first") % (name, phase, name)


def deliver_route(run: Path) -> str:
    """'`council state phase=<s> --run <name>`, then ...', one a stage, ending at Deliver."""
    steps = stages.skipped(run, _field(run, "phase"), "deliver") + ["deliver"]
    return ", then ".join("`council state phase=%s --run %s`" % (stage, run.name) for stage in steps)


def actual(run: Path, totals: dict) -> str:
    """The close line's and the state's actual: words, set against the plan's estimate and the agents' share."""
    words, estimate = usage.usage_words(totals), usage.budget_value(run, "estimated-tokens")
    if not words or estimate is None:
        return words
    words += " · estimated ~" + usage.token_text(estimate)
    share, total = usage.agents_share(run) or 0, totals["tokens"]["known"]
    whose = "" if share == estimate else " the agents' %s share" % usage.token_text(share)
    if share > 0 and total > share:
        least = "" if totals["tokens"]["basis"] == "complete" else "at least "
        words += " (%sabout %d%% over%s)" % (least, ((total - share) * 100 + share // 2) // share, whose)
    return words


def warnings(run: Path) -> list[tuple[str, str]]:
    """(code, line without 'council: ') for each check a complete close of a council mode fails, in order."""
    if _field(run, "mode") not in MODES:
        return []
    found = ((code, check(run), text) for code, check, text in CHECKS)
    return [(code, text.format(value=value, name=run.name)) for code, value, text in found if value is not None]


def _short_of_deliver(run: Path) -> str | None:
    phase = _field(run, "phase")
    return None if phase in ("deliver", "learn") else phase or "unknown"


def stopped_short(run: Path) -> bool:
    """A council mode's run that never reached Deliver, which its close may re-close as abandoned."""
    return _field(run, "mode") in MODES and _short_of_deliver(run) is not None


def _red_gates(run: Path) -> str | None:
    """The required gates whose last run in this run failed, in byte order."""
    required, last = {g.name for g in gate_table.gates(home.council_home()) if g.must != "no"}, {}
    for row in events.table(run).rows:
        if row[3:4] == ["gate.finished"] and len(row) > 5 and row[4] in required:
            last[row[4]] = row[5]
    red = sorted((gate for gate, value in last.items() if value == "failed"), key=lambda g: g.encode())
    return ", ".join(red) or None


def _misshapen(run: Path) -> str | None:
    """The first verify file (not a Solo run's verify-self.md) out of shape, with its problems."""
    for name in seat_files.listed(run, "verify-*.md"):
        problems = seat_files.verify_problems(run / name) if (run / name).is_file() else ""
        if name != "verify-self.md" and problems:
            return "%s is out of shape (%s)" % (name, problems[:-2])
    return None


def _no_verdicts(run: Path) -> str | None:
    """'' for a review or plan run with no verify file whose plan's verification is not self."""
    if _field(run, "mode") not in ("council-review", "council-plan"):
        return None
    level = next((r["value"] for r in plan.rows(run) if (r["kind"], r["id"], r["field"]) ==
                  ("verification", "run", "level")), "")
    verified = any((run / name).is_file() for name in seat_files.listed(run, "verify-*.md"))
    return None if verified or level == "self" else ""


def _unmapped(run: Path) -> str | None:
    """The top-level areas whose tracked files the run changed since the commit it opened on, less those a map line
    under ## Changes has named since the day it opened; None with no map or none left."""
    start, top, council = _field(run, "start-head"), _field(run, "code-root"), home.native(home.run_home(run))
    top = home.native(top) if top not in ("", "-") else "."
    if not start or not map_file.path(council).is_file() or not Path(top).is_dir():
        return None
    noted = map_file.noted(council, _field(run, "opened")[:10])
    left = [area for area, _ in map_file.areas(map_file.changed(top, start)) if area not in noted]
    return ", ".join(left) or None


CHECKS = (  # (code, check: the value its line names, or None when the run passes, line)
    ("phase", _short_of_deliver, "closed as complete at stage {value}, so it never reached Deliver — if it stopped "
     "early, tell the user, or close it as abandoned: council run close --run {name} --status abandoned"),
    ("check", _red_gates, "closed as complete with a required check failing on its last run: {value} — say so to the "
     "user"),
    ("verify", _misshapen, "{value} — mend it, or resume the verifier that wrote it"),
    ("deliverable", lambda run: None if _field(run, "deliverable") else "", "closed as complete with no deliverable "
     "recorded — council state deliverable=<path> --run {name}"),
    ("verdicts", _no_verdicts, "closed as complete with no verifier verdicts (no verify-*.md in the run folder)"),
    ("map-touched", _unmapped, "the run changed {value} since it opened, with no line in the map yet — say what "
     "changed in each, in the user's words: council map touch <dir>=\"<line>\" …"),
)


def claims_stale(run: Path, says_stale: Callable[[], bool]) -> bool:
    """A synthesis run's claim index missing, or older than a source (a deleted one only says_stale tells)."""
    synthesis, claims = run / "synthesis.md", run / "claims.jsonl"
    synthesised = _field(run, "mode") in stages.SYNTHESISED
    if not synthesised or not (synthesis.is_file() or claims.is_file()):
        return False
    if says_stale() or not (synthesis.is_file() and claims.is_file()):
        return True
    sources = [synthesis] + [run / name for name in seat_files.listed(run, "verify-*.md")]
    return any(f.is_file() and f.stat().st_mtime_ns > claims.stat().st_mtime_ns for f in sources)


def build_log(run: Path, council_home: str) -> str:
    """A build run's log: '' when one names the run and has its Shortcuts section, else the line to say."""
    folder, name = Path(home.native(council_home)) / "logs", re.escape(run.name)
    logs = [(f, bytewise.file_lines(folder / f, fold=False))
            for f in seat_files.listed(folder, "*.md") if (folder / f).is_file()]
    found = [f for pattern in ("Run:[^|]*%s([^0-9A-Za-z-]|$)", "(^|[^0-9A-Za-z-])%s([^0-9A-Za-z-]|$)")
             for f, lines in logs if any(re.search(pattern % name, line) for line in lines)]
    if not found:
        return ('no build log names this run — write %s/logs/<date>-<slug>.md with "Run: %s" and a "## Shortcuts and '
                'concessions" section' % (council_home, run.name))
    if any(line.startswith("## Shortcuts and concessions")
           for line in bytewise.file_lines(folder / found[0], fold=False)):
        return ""
    return ('the log has no "## Shortcuts and concessions" section — say what was traded away, or the single word '
            'none: %s/logs/%s' % (council_home, found[0]))
