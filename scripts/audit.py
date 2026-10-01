#!/usr/bin/env python3
"""Check a finished council run against what the method promises. Read-only: no model, no network.

    python3 scripts/audit.py --run <run folder> [--transcript <session .jsonl>]

The suites test the helper; this reads what a Chair actually did. From the run's own records
(session-state.md, events.tsv, run-plan.tsv, seats.tsv, usage.tsv, cap-allowances.tsv, claims.jsonl):
every stage entered in order; closed complete only after Deliver; every agent on record as running
before it finished; one check (gate) at a time, each once per stage; a deliverable; for a review,
plan or research run the claim index, with a verifier's verdict on every kept claim; every seat the
plan selected on record, the Chair's own included; the agent limit. With a Claude Code session
transcript it reads the main thread from the turn that opened the run to the end of the turn that
closed it: the status card at the first dispatch and after close; the helper called as a plain
`council`; no helper output cut short by `| tail` or `| head`; every refusal of the helper tried
again. Each item says pass, warn or FAIL in plain words. It only opens files to read them and writes
nothing, bytecode included. Exit 0 when nothing failed, 1 when something did, 2 when it cannot read
the run or the transcript.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shlex
import sys

sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PASS, WARN, FAIL = "pass", "warn", "FAIL"
MAX_FILE = 64 * 1024 * 1024
STAGES = ("convene", "prepare", "assign", "brief", "work", "collect", "judge", "challenge", "deliver", "learn")
RANK = dict((stage, n) for n, stage in enumerate(STAGES))
RANK["build"] = RANK["work"]                       # council-implement's build loop stands in for stages 3-7
SEAT_STAGES = ("assign", "brief", "work", "collect")   # stages 3-6: a run with no worker seat skips them
MODES = ("council-review", "council-plan", "council-implement", "council-research", "council-postgame")
CLAIM_MODES = ("council-review", "council-plan", "council-research")
VERDICTS = ("CONFIRMED", "REFUTED", "UNCERTAIN", "MISCITED")
HELPER_WORDS = {"home", "run", "state", "seat", "cap", "correct", "index", "impact", "context", "evidence", "repair",
                "gate", "gates", "changed", "collect", "check", "map", "fingerprint", "memory", "prior", "ask",
                "ledger", "route", "tune", "history", "outcomes", "tui", "status", "pet", "doctor", "help"}
TWO_WORD = {"run", "cap", "memory", "evidence", "context", "repair", "tune", "route"}
# The helper's advisory lines on stderr ("council: ..." without a refusal): everything else on a
# "council:" line is a refusal (die, exit 2) or a record that failed to write. A lock refusal is
# answered by waiting, not by a second call, so it is listed here too. evals/run_audit.py checks that
# each lead is still the helper's wording.
NOTE_LEADS = ("save the user's request", "another run is in progress", "a paused run is also open", "its code root is ",
              "first dispatch of this run", "run closed \u2014 show the user", "this run has used",
              "seats still marked", "the claim index is missing", "no request was filed", "no build log names",
              "the log has no", "optional impact graph", "impact needs optional", "cleared a gate lock", "WARNING",
              "several runs are open \u2014 only the paths", "checks are already running", "now ignores asks/",
              "KB, over the ~25 KB")
NOTES = re.compile(r"council: (?:%s|\S+ now ignores asks/|\S+ is \d+ KB, over)"
                   % "|".join(re.escape(lead) for lead in NOTE_LEADS[:-2]))


# --- reading ------------------------------------------------------------------------------------------------
def text_of(path):
    """A file's text (BOM dropped), or "" for a missing, linked, oversized or unreadable one."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE:
            return ""
        with open(str(path), "rb") as handle:
            return handle.read().decode("utf-8", "replace").lstrip("\ufeff")
    except OSError:
        return ""


def tsv(path):
    """Rows of a TSV file as dicts keyed by its header; "#" comment lines are skipped."""
    rows = [line.rstrip("\r").split("\t") for line in text_of(path).split("\n")
            if line.strip() and not line.startswith("#")]
    if not rows:
        return []
    head = rows[0]
    return [dict(zip(head, row + [""] * (len(head) - len(row)))) for row in rows[1:]]


def field(state, key):
    """The helper's field(): the first "key:" line, value trimmed, a trailing "  # note" dropped."""
    match = re.search(r"^%s:[ \t]*(.*)$" % re.escape(key), state, re.MULTILINE)
    return re.sub(r"\s{2,}#.*$", "", match.group(1)).strip() if match else ""


def stamp(value):
    """An ISO time (the helper's 2026-09-30T10:14:16Z, a transcript's ...16.894Z) as UTC, or None."""
    match = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.\d+)?(?:Z|\+00:00)?$", (value or "").strip())
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def clock(when):
    return when.astimezone().strftime("%H:%M:%S") if when else "?"


def details(cell):
    """"exit=1;seconds=57" as a dict."""
    return dict(part.split("=", 1) for part in (cell or "").split(";") if "=" in part)


def number(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def listed(names, most=4):
    names = list(names)
    return ", ".join(names[:most]) + (" and %d more" % (len(names) - most) if len(names) > most else "")


class Run:
    def __init__(self, folder):
        self.folder = folder
        self.name = folder.name
        self.state = text_of(folder / "session-state.md")
        self.mode = field(self.state, "mode")
        self.status = field(self.state, "status").split(" ")[0]
        self.events = [e for e in tsv(folder / "events.tsv") if e.get("type")]
        for event in self.events:
            event["t"] = stamp(event.get("at"))
        self.plan = tsv(folder / "run-plan.tsv")
        self.seats = tsv(folder / "seats.tsv")
        self.usage = tsv(folder / "usage.tsv")
        self.roles, self.selected = {}, []
        for row in self.plan:
            if row.get("kind") == "seat" and row.get("field") == "role":
                self.roles[row.get("id", "")] = row.get("value", "").strip()
            if row.get("kind") == "seat" and row.get("field") == "disposition" and row.get("value", "").strip() == "selected":
                self.selected.append(row.get("id", ""))
        self.size = next((r.get("value", "").strip() for r in self.plan
                          if r.get("kind") == "run" and r.get("field") == "size"), "")

    def of_type(self, *types):
        return [e for e in self.events if e["type"] in types]

    @property
    def opened(self):
        found = self.of_type("run.opened")
        return found[0]["t"] if found else None

    @property
    def closed(self):
        found = self.of_type("run.closed", "run.paused")
        return found[-1] if found else None

    def phase_at(self, when):
        """The stage in effect at a moment, from the phase events."""
        phase = "convene"
        for event in self.events:
            if event["type"] in ("run.opened", "run.phase_changed") and event["t"] and when and event["t"] <= when:
                phase = "convene" if event["type"] == "run.opened" else event.get("value", "")
        return phase

    def workers(self):
        if self.plan:
            return [s for s in self.selected if self.roles.get(s) == "worker"] if self.size != "solo" else []
        return [r.get("slug") for r in self.seats if r.get("slug") != "chair" and not r.get("slug", "").startswith("verify")]


# --- the run's records ----------------------------------------------------------------------------------------
def stages(run, say):
    label = "Stages"
    if not run.events:
        say(WARN, label, "no event stream (a run from before events.tsv), so the order of stages can't be read")
        return
    entered = [("convene" if e["type"] == "run.opened" else e.get("value", "")) for e in run.events
               if e["type"] in ("run.opened", "run.phase_changed")]
    path = [s for n, s in enumerate(entered) if n == 0 or s != entered[n - 1]]
    if run.mode not in MODES:
        need, why = [], ""                          # council-init, test-architect, context-core: no fixed path
    elif run.mode == "council-implement":
        need, why = ["convene", "prepare", "build", "challenge", "deliver", "learn"], ""
    elif run.mode == "council-postgame" or not run.workers():
        need = [s for s in STAGES if s not in SEAT_STAGES]
        why = "" if run.mode == "council-postgame" else " (stages 3-6 are skipped: no worker seat was selected)"
    else:
        need, why = list(STAGES), ""
    missing = [s for s in need if s not in entered] if run.status == "complete" else []
    back = ["%s back to %s" % (a, b) for a, b in zip(path, path[1:]) if RANK.get(b, 99) < RANK.get(a, -1)]
    unknown = [s for s in path if s not in RANK] if run.mode in MODES else []    # setup names its own phases
    shown = " > ".join(path) or "none"
    if missing:
        say(FAIL, label, "%s; never entered: %s%s" % (shown, ", ".join(missing), why))
    elif back or unknown:
        say(WARN, label, "%s; %s" % (shown, "; ".join(["went " + b for b in back] + ["not a stage: " + u for u in unknown])))
    else:
        say(PASS, label, shown)


def closing(run, say):
    label = "Closed after Deliver"
    closed = run.closed
    if run.status == "complete" and not run.events:
        say(WARN, label, "no event stream (a run from before events.tsv), so when it closed can't be read")
    elif run.status == "complete":
        if not closed:
            say(FAIL, label, "the state says complete, but no close is recorded; close it with: council run close --run %s" % run.name)
            return
        if run.mode not in MODES:                  # council-init, test-architect: their own phases, no Deliver
            say(PASS, label, "closed complete at %s (%s has no Deliver stage)" % (clock(closed["t"]), run.mode or "this mode"))
            return
        deliver = [e for e in run.of_type("run.phase_changed") if e.get("value") == "deliver"
                   and number(e.get("seq")) is not None and number(e.get("seq")) < number(closed.get("seq"))]
        if not deliver:
            last = [e.get("value") for e in run.of_type("run.phase_changed")
                    if number(e.get("seq")) is not None and number(e.get("seq")) < number(closed.get("seq"))]
            say(FAIL, label, "closed as complete at %s without entering Deliver (its last stage: %s)"
                % (clock(closed["t"]), last[-1] if last else "convene"))
        else:
            say(PASS, label, "closed complete at %s; Deliver began at %s" % (clock(closed["t"]), clock(deliver[0]["t"])))
    elif run.status in ("abandoned", "paused"):
        say(WARN, label, "closed as %s, so no deliverable was due; the items below read what was done" % run.status)
    else:
        say(WARN, label, "the run is still %s: audit it again after council run close" % (run.status or "without a status"))


def agents_on_record(run, say):
    """Each agent's id reaches usage.tsv with the seat call that names it; a call that starts a seat records
    it as running. So a seat with more agent ids than running records had an agent that was first written
    down when it finished (usage.tsv's times are to the second, too coarse to order two quick calls)."""
    label = "Agents on record while they ran"
    if not run.events:
        say(WARN, label, "no event stream (a run from before events.tsv), so when agents were recorded can't be read")
        return
    late, count, ids, bare = [], 0, {}, {}
    for row in run.usage:
        slug, agent, kind = row.get("seat", ""), row.get("agent", ""), row.get("kind", "")
        if kind == "finished" and row.get("runs", "") == "0":
            continue                                            # agents=0: the Chair did the work, no agent ran
        if agent:
            ids.setdefault(slug, [])
            if agent not in ids[slug]:
                ids[slug].append(agent)
        elif kind == "finished":
            bare[slug] = bare.get(slug, 0) + 1
    for slug in sorted(set(ids) | set(bare)):
        states = [e.get("value") for e in run.events if e["type"] == "seat.updated" and e.get("subject") == slug]
        started = states.count("running")
        agents = ids.get(slug, [])
        count += len(agents) + bare.get(slug, 0)
        if len(agents) > started:
            late.append("%s (agent %s)" % (slug, ", ".join(a[:10] for a in agents[started:])))
        elif bare.get(slug) and not started:
            late.append(slug)
    busy = [r.get("slug") for r in run.seats if r.get("state") in ("running", "queued")]
    if late:
        say(FAIL, label, "%s recorded only when it finished, so while it ran the agent limit could not count it"
            % listed(late))
    elif busy and run.status != "in-progress":
        say(WARN, label, "still marked running or queued after close: %s" % listed(busy))
    elif not count:
        say(PASS, label, "no agent was dispatched")
    else:
        say(PASS, label, "%d dispatch(es), each recorded as running before it finished" % count)


def gates(run, say):
    runs = []
    for event in run.of_type("gate.finished"):
        seconds = number(details(event.get("detail")).get("seconds")) or 0
        if event["t"]:
            runs.append({"name": event.get("subject", "?"), "end": event["t"], "start": event["t"] - timedelta(seconds=seconds)})
    if not runs:
        say(WARN, "Checks one at a time", "no check (gate) ran in this run")
        return
    runs.sort(key=lambda r: r["start"])
    overlaps = []
    for n, first in enumerate(runs):
        for later in runs[n + 1:]:
            if later["start"] < first["end"] - timedelta(seconds=2):
                overlaps.append("%s %s-%s ran while %s %s-%s was still running" % (
                    later["name"], clock(later["start"]), clock(later["end"]),
                    first["name"], clock(first["start"]), clock(first["end"])))
    if overlaps:
        say(FAIL, "Checks one at a time", "two copies of the checks ran at once: %s" % listed(overlaps, 2))
    else:
        say(PASS, "Checks one at a time", "%d gate run(s), never two at once" % len(runs))
    label = "Each check once per stage"
    if run.mode == "council-implement":
        say(PASS, label, "not counted: a build runs its checks again after every change")
        return
    counts = {}
    for gate_run in runs:
        key = (gate_run["name"], run.phase_at(gate_run["start"]))
        counts[key] = counts.get(key, 0) + 1
    repeats = ["%s %d times in %s" % (name, n, stage) for (name, stage), n in sorted(counts.items()) if n > 1]
    if repeats:
        say(WARN, label, "ran again in the same stage: %s" % listed(repeats))
    else:
        say(PASS, label, "; ".join("%s in %s" % key for key in sorted(counts, key=lambda k: (RANK.get(k[1], 99), k[0]))))


def deliverable(run, say):
    label = "Deliverable"
    if run.status != "complete":
        say(PASS, label, "not due: the run did not complete")
        return
    recorded = field(run.state, "deliverable")
    if not recorded and run.mode not in MODES:
        say(PASS, label, "not due: %s has no Deliver stage" % (run.mode or "this mode"))
        return
    if not recorded:
        say(FAIL, label, "none recorded; at Deliver: council state deliverable=<path>")
        return
    home = run.folder.parent.parent            # <home>/runs/<run>; a copied run elsewhere is not looked up
    if home.name != ".council" or run.folder.parent.name != "runs":
        where = None
    elif os.path.isabs(recorded):
        where = Path(recorded)
    elif recorded.replace("\\", "/").startswith(".council/"):
        where = home.parent / recorded
    else:
        where = Path(field(run.state, "code-root") or str(home.parent)) / recorded
    if where is not None and not where.exists():
        say(WARN, label, "recorded as %s, but there is no such file now" % recorded)
    else:
        say(PASS, label, recorded)


def claim_index(run, say):
    if run.mode not in CLAIM_MODES:
        return
    label = "Claim index"
    index = run.folder / "claims.jsonl"
    if not index.is_file():
        say(FAIL, label, "missing; build it: council evidence build --run %s, then evidence check" % run.name)
        return
    newer = [p.name for p in [run.folder / "synthesis.md"] + sorted(run.folder.glob("verify-*.md"))
             if p.is_file() and p.stat().st_mtime > index.stat().st_mtime + 1]
    claims = []
    for line in text_of(index).splitlines():
        try:
            claim = json.loads(line)
        except ValueError:
            continue
        if isinstance(claim, dict):
            claims.append(claim)
    kept = [c for c in claims if c.get("disposition") == "kept"]
    open_claims = [str(c.get("id", "?")) for c in kept if str(c.get("verdict", "")).upper() not in VERDICTS]
    confirmed_cut = [str(c.get("id", "?")) for c in claims if c.get("disposition") == "cut"
                     and str(c.get("verdict", "")).upper() == "CONFIRMED"]
    if newer:
        say(FAIL, label, "out of date: %s changed after it was built; council evidence build --run %s" % (listed(newer), run.name))
    elif confirmed_cut:
        say(FAIL, label, "cut, but a verifier CONFIRMED it: %s — ship it, or say in synthesis.md why it stays cut; "
            "then council evidence build and evidence check --run %s" % (listed(confirmed_cut, 8), run.name))
    elif open_claims:
        say(FAIL, label, "kept claim(s) with no verifier's verdict: %s" % listed(open_claims, 8))
    elif not kept:
        say(PASS, label, "%d claim(s), none kept" % len(claims))
    else:
        say(PASS, label, "%d claim(s); all %d kept ones have a verifier's verdict" % (len(claims), len(kept)))


def seats_on_record(run, say):
    label = "Every seat on record"
    if not run.plan:
        say(WARN, label, "no run plan, so the seats it selected can't be read")
        return
    if run.status != "complete":
        say(PASS, label, "not checked: the run did not complete")
        return
    recorded = set(r.get("slug") for r in run.seats)
    chair = [s for s in run.selected if run.roles.get(s) == "chair"]
    worked = run.mode in MODES and (run.size == "solo" or
                                    re.search(r"from:[ \t]*chair\b", text_of(run.folder / "synthesis.md")) is not None)
    # Judging and synthesis are not seat work: the Chair's record is due in Solo, or for a finding from: chair.
    missing_chair = [s for s in chair if s not in recorded] if worked else []
    missing = [s for s in run.selected if s not in recorded and s not in chair]
    chair = [s for s in chair if s in recorded]
    if missing_chair:
        say(FAIL, label, "the Chair's own seat (%s) has no record: council seat %s done agents=0 --run %s%s" % (
            ", ".join(missing_chair), missing_chair[0], run.name, "; nor has %s" % listed(missing) if missing else ""))
    elif missing:
        say(FAIL, label, "selected in the plan but never recorded: %s" % listed(missing))
    else:
        say(PASS, label, "all %d selected seat(s)%s" % (len(run.selected), ", the Chair's own included" if chair else ""))


def agent_limit(run, say):
    label = "Agent limit"
    cap = next((number(r.get("value")) for r in run.plan
                if r.get("kind") == "budget" and r.get("id") == "run" and r.get("field") == "agent-cap"), None)
    closed = run.of_type("run.closed")
    used = number(details(closed[-1].get("detail")).get("agent_runs")) if closed else None
    if used is None:
        used = sum(number(r.get("agents")) or 0 for r in run.seats)
    if not cap:
        say(WARN, label, "%d agent run(s); the plan names no cap to hold them to" % used)
        return
    allowed = [number(r.get("until")) for r in tsv(run.folder / "cap-allowances.tsv") if number(r.get("until"))]
    if used <= cap:
        say(PASS, label, "%d of %d agent runs" % (used, cap))
    elif allowed and allowed[-1] >= used:
        say(PASS, label, "%d agent runs, past the cap of %d on the user's go (up to %d)" % (used, cap, allowed[-1]))
    else:
        say(FAIL, label, "%d agent runs against a cap of %d, with no go from the user on record for them" % (used, cap))


# --- the session transcript ---------------------------------------------------------------------------------------
def heredoc_free(command):
    """The command without here-document bodies (their lines are data, not commands)."""
    out, ends = [], []
    for line in command.split("\n"):
        if ends:
            if line.strip() == ends[0]:
                ends.pop(0)
            continue
        out.append(line)
        ends += [tag for _, tag in re.findall(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1", line)]
    return "\n".join(out)


def pipelines(command):
    """Each simple command of a shell line as its list of pipe stages. Splits on ; && || & newline $( ( )
    and backquotes outside quotes, then on single |; enough to see how the helper was called."""
    lines, stages, cur, quote, n = [], [], [], None, 0
    while n < len(command):
        ch, two = command[n], command[n:n + 2]
        if quote:
            cur.append(ch)
            if ch == "\\" and quote == '"' and n + 1 < len(command):
                cur.append(command[n + 1])
                n += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            cur.append(ch)
        elif ch == "\\" and n + 1 < len(command):
            cur.append(two)
            n += 1
        elif ch == "&" and (command[n - 1:n] in "<>" and n > 0 or command[n + 1:n + 2] == ">"):
            cur.append(ch)                                       # 2>&1, &>file: a redirection, not a separator
        elif two in ("&&", "||", "$("):
            stages.append("".join(cur)); lines.append(stages); stages, cur = [], []
            n += 1
        elif ch in ";\n&`()":
            stages.append("".join(cur)); lines.append(stages); stages, cur = [], []
        elif ch == "|":
            stages.append("".join(cur)); cur = []
        else:
            cur.append(ch)
        n += 1
    stages.append("".join(cur))
    lines.append(stages)
    return [[s.strip() for s in line] for line in lines if line and line[0].strip()]


def words_of(stage):
    try:
        return shlex.split(stage, posix=True)
    except ValueError:
        return stage.split()


def invocations(command):
    """The helper calls in a Bash or PowerShell command: how each was called (plain, path or variable),
    its subcommand, and the tail/head stage that cut its output, if any."""
    command = heredoc_free(command or "")
    variables = {"C", "COUNCIL"} | set(name for name, value in re.findall(
        r"(?:^|[\s;&(|])([A-Za-z_]\w*)=(\"[^\"]*\"|'[^']*'|\S*)", command) if re.search(r"[/\\]council\b", value))
    found = []
    for stages in pipelines(command):
        words = words_of(stages[0])
        while words and (re.match(r"^[A-Za-z_]\w*=", words[0]) or words[0] in ("!", "&", "time", "command", "exec", "nohup")):
            words = words[1:]
        if not words:
            continue
        first = words[0].replace("\\", "/")
        form, rest = None, []
        if first == "council":
            form, rest = "plain", words[1:]
        elif re.search(r"(^|/)(ba)?sh(\.exe)?$", first) and len(words) > 1 and words[1].replace("\\", "/").endswith("/council"):
            form, rest = "path", words[2:]
        elif first.endswith("/council"):
            form, rest = "path", words[1:]
        else:
            match = re.match(r"^\$\{?([A-Za-z_]\w*)\}?$", first)
            if match and match.group(1) in variables:
                form, rest = "variable", words[1:]
        if not form or not rest or rest[0] not in HELPER_WORDS:
            continue
        sub = rest[0]
        if sub in TWO_WORD and len(rest) > 1 and re.match(r"^[a-z]+$", rest[1]):
            sub += " " + rest[1]
        cut = next((s for s in stages[1:] if words_of(s)[:1] and words_of(s)[0] in ("tail", "head")), None)
        found.append({"form": form, "sub": sub, "flags": [w for w in rest if w.startswith("--")], "cut": cut,
                      "text": stages[0][:120]})
    return found


def block_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def is_prompt(line, content):
    """A message the user typed (a /command included), not a tool result, a reminder or a notification."""
    if line.get("type") != "user" or line.get("isMeta"):
        return False
    if isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
        return False
    words = block_text(content).lstrip()
    return bool(words) and (not words.startswith("<") or words.startswith("<command-"))


def read_transcript(path):
    """The main thread's messages in order: (time, kind, payload). A line without a time takes the one before."""
    entries, sessions, last = [], set(), None
    with open(str(path), "rb") as handle:
        for raw in handle:
            try:
                line = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            if not isinstance(line, dict) or line.get("isSidechain") or line.get("parent_tool_use_id"):
                continue
            last = stamp(line.get("timestamp")) or last
            if line.get("sessionId"):
                sessions.add(line["sessionId"])
            message = line.get("message") if isinstance(line.get("message"), dict) else {}
            content = message.get("content")
            if is_prompt(line, content):
                entries.append((last, "prompt", block_text(content)))
                continue
            for block in content if isinstance(content, list) else []:
                if not isinstance(block, dict):
                    continue
                kind = block.get("type")
                if kind == "tool_use":
                    entries.append((last, "use", block))
                elif kind == "tool_result":
                    entries.append((last, "result", block))
                elif kind == "text" and line.get("type") == "assistant":
                    entries.append((last, "text", block.get("text", "")))
    return entries, sessions


def window(entries, opened, closed):
    """From the prompt of the turn that opened the run to the prompt after the turn that closed it."""
    if not any(t for t, _, _ in entries) or not opened:
        return entries
    start = None
    for n, (t, kind, _) in enumerate(entries):
        if t and t > opened:
            break
        if kind == "prompt" and t and t >= opened - timedelta(minutes=30):
            start = n
    if start is None:
        start = next((n for n, (t, _, _) in enumerate(entries) if t and t >= opened - timedelta(minutes=2)), len(entries))
    end = len(entries)
    if closed:
        for n in range(start, len(entries)):
            t, kind, _ = entries[n]
            if t and (t > closed + timedelta(minutes=30) or (kind == "prompt" and t > closed)):
                end = n
                break
    return entries[start:end]


def transcript(run, path, say):
    """The transcript's items; returns the span it read, in words."""
    entries, sessions = read_transcript(path)
    closed = run.closed["t"] if run.closed else None
    part = window(entries, run.opened, closed)
    session = field(run.state, "session")
    if session and sessions and session not in sessions:
        say(WARN, "Transcript", "this file is session %s; the run was driven by %s" % (listed(sorted(sessions), 2), session))
    if not part:
        say(WARN, "Transcript", "no lines in the run's window: is it this run's session file?")
        return "nothing in the run's window"
    times = [t for t, _, _ in part if t]
    span = "%s to %s" % (clock(times[0]), clock(times[-1])) if times else "the whole file: it carries no times"
    results = dict((b.get("tool_use_id"), b) for _, kind, b in part if kind == "result")
    calls = []                                   # (position, time, tool_use block, its helper invocations, output)
    for n, (t, kind, block) in enumerate(part):
        if kind != "use":
            continue
        found = []
        if block.get("name") in ("Bash", "PowerShell"):
            found = invocations(str((block.get("input") or {}).get("command", "")))
        result = results.get(block.get("id"))
        calls.append((n, t, block, found, block_text(result.get("content")) if result else ""))
    helper = [c for c in calls if c[3]]

    def relayed(position, output):
        status = next((l.split(":", 1)[1].strip() for l in output.splitlines() if l.startswith("Status:")), "")
        if not status:
            return False
        for t, kind, words in part[position + 1:]:
            if kind == "prompt":
                return False
            if kind == "text" and status[:40] in " ".join(words.split()):
                return True
        return False

    def card(after, until):
        """Was the status shown between two positions: a show_widget call, or council status relayed?"""
        for n, t, block, found, output in calls:
            if after <= n <= until:
                if "show_widget" in str(block.get("name", "")):
                    return True
                if any(i["sub"] == "status" and not {"--line", "--json"} & set(i["flags"]) for i in found) \
                        and relayed(n, output):
                    return True
        return False

    # The status card at the first dispatch: between the first agent sent (or recorded) and its first result.
    label = "Status card at the first dispatch"
    opened_at = next((n for n, t, block, found, _ in calls if any(i["sub"] == "run open" for i in found)), 0)
    sent = [n for n, t, block, found, _ in calls if n >= opened_at and (block.get("name") in ("Agent", "Task", "Workflow")
            or any(i["sub"] == "seat" and re.search(r"\bseat\s+\S+\s+(running|queued)\b", i["text"]) for i in found))]
    if not sent:
        say(PASS, label, "no agent was dispatched, so none was due")
    else:
        done = [n for n, t, block, found, _ in calls if n > sent[0]
                and any(i["sub"] == "seat" and re.search(r"\bseat\s+\S+\s+(done|failed|blocked)\b", i["text"]) for i in found)]
        end = done[0] if done else len(part)
        if card(sent[0], end):
            say(PASS, label, "shown after the first agent went out at %s" % clock(part[sent[0]][0]))
        else:
            say(FAIL, label, "not shown: the first agent went out at %s, and no show_widget call or relayed "
                "council status followed%s" % (clock(part[sent[0]][0]), " before its result was recorded at %s"
                                               % clock(part[end][0]) if done else ""))

    # The closing card: after the run close call, to the end of that turn.
    label = "Closing card"
    close_at = next(((n, k) for n, t, block, found, _ in calls for k, i in enumerate(found) if i["sub"] == "run close"), None)
    if close_at is None:
        if closed:
            say(WARN, label, "no council run close call in the transcript's window, so it can't be checked")
    else:
        n0, k0 = close_at
        shown = False
        for n, t, block, found, output in calls:
            if n < n0:
                continue
            if "show_widget" in str(block.get("name", "")) and n > n0:
                shown = True
            later = found[k0 + 1:] if n == n0 else found
            if any(i["sub"] == "status" and not {"--line", "--json"} & set(i["flags"]) for i in later) and relayed(n, output):
                shown = True
        if shown:
            say(PASS, label, "shown after the close at %s" % clock(part[n0][0]))
        else:
            say(FAIL, label, "not shown after the close at %s: no show_widget call, and no council status "
                "output passed on to the user" % clock(part[n0][0]))

    # How the helper was called.
    label = "Helper called as plain council"
    every = [i for c in helper for i in c[3]]
    forms = dict((f, sum(1 for i in every if i["form"] == f)) for f in ("plain", "path", "variable"))
    if not every:
        say(WARN, label, "no helper call found in the window")
    elif forms["variable"]:
        say(FAIL, label, "%d of %d call(s) by the plain name; %d through a shell variable%s. Permission rules "
            "match only the plain form" % (forms["plain"], len(every), forms["variable"],
                                             ", %d by the full path" % forms["path"] if forms["path"] else ""))
    elif forms["path"]:
        say(WARN, label, "%d of %d call(s) by the full path: right only when council is not on PATH"
            % (forms["path"], len(every)))
    else:
        say(PASS, label, "all %d call(s)" % len(every))

    label = "Helper output shown whole"
    cut = ["%s council %s | %s" % (clock(t), i["sub"], i["cut"]) for n, t, block, found, _ in helper for i in found if i["cut"]]
    if cut:
        say(FAIL, label, "%d call(s) piped through tail or head, which hides the helper's exit status and can "
            "swallow a refusal: %s" % (len(cut), listed(cut, 3)))
    elif every:
        say(PASS, label, "no helper call piped through tail or head")

    label = "Helper refusals tried again"
    missed, refused = [], 0
    for index, (n, t, block, found, output) in enumerate(helper):
        lines = [l.strip() for l in output.splitlines() if l.strip().startswith("council: ") and not NOTES.match(l.strip())]
        if not lines:
            continue
        refused += 1
        subs = set(i["sub"] for i in found)
        if not any(subs & set(i["sub"] for i in c[3]) for c in helper[index + 1:]):
            missed.append("%s %s: %s" % (clock(t), "/".join(sorted(subs)), lines[0][len("council: "):][:90]))
    if missed:
        say(WARN, label, "%d refusal(s) with no later call of the same command: %s" % (len(missed), listed(missed, 2)))
    elif every:
        say(PASS, label, "%d refusal(s), each followed by another try" % refused if refused else "the helper refused nothing")
    return span


def find_transcript(session):
    """The session's own .jsonl, which Claude Code keeps as projects/<project>/<session id>.jsonl under its
    config folder (CLAUDE_CONFIG_DIR, else ~/.claude). Only one match counts; None otherwise."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{7,99}", session or ""):
        return None
    roots = [Path(os.environ["CLAUDE_CONFIG_DIR"])] if os.environ.get("CLAUDE_CONFIG_DIR") else []
    roots.append(Path.home() / ".claude")
    for root in roots:
        try:
            hits = sorted((root / "projects").glob("*/%s.jsonl" % session))
        except OSError:
            continue
        if len(hits) == 1 and hits[0].is_file():
            return hits[0]
    return None


def main():
    parser = argparse.ArgumentParser(description="Check a finished council run against the method (read-only).")
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--transcript", type=Path, help="the Claude Code session .jsonl that drove the run")
    parser.add_argument("--no-transcript", action="store_true", help="read the run's records only")
    args = parser.parse_args()
    folder = args.run
    if not folder.is_dir() or not (folder / "session-state.md").is_file():
        print("audit: not a council run folder: {}".format(folder), file=sys.stderr)
        return 2
    if args.transcript is not None and not args.transcript.is_file():
        print("audit: no such transcript file: {}".format(args.transcript), file=sys.stderr)
        return 2
    run = Run(folder)
    found = None
    if args.transcript is None and not args.no_transcript:
        args.transcript = found = find_transcript(field(run.state, "session"))
    items = []

    def say(verdict, label, words):
        items.append((verdict, label, words))

    for check in (stages, closing, agents_on_record, gates, deliverable, claim_index, seats_on_record, agent_limit):
        check(run, say)
    split, span = len(items), ""
    if args.transcript is not None:
        try:
            span = transcript(run, args.transcript, say)
        except OSError as exc:
            print("audit: cannot read the transcript: {}".format(exc), file=sys.stderr)
            return 2
    print("Run audit: %s (%s, %s). Read-only: nothing was written." % (run.name, run.mode or "no mode", run.status or "no status"))
    if found is not None:
        print("Transcript: %s (found from the run's session id)" % found)
    print("\nFrom the run's records")
    for n, (verdict, label, words) in enumerate(items):
        if n == split:
            print("\nFrom the session transcript (%s)" % span)
        print("  %-4s  %s: %s" % (verdict, label, words))
    if span and split == len(items):
        print("\nFrom the session transcript (%s): nothing to check" % span)
    if args.transcript is None:
        print("\nNo transcript given: pass --transcript <session .jsonl> to check what the Chair showed and ran%s."
              % (" (this run's session: %s)" % field(run.state, "session") if field(run.state, "session") else ""))
    counts = dict((v, sum(1 for item in items if item[0] == v)) for v in (FAIL, WARN, PASS))
    print("\n%d failed, %d warning(s), %d passed" % (counts[FAIL], counts[WARN], counts[PASS]))
    return 1 if counts[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
