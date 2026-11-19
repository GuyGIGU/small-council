"""The run's own records read back for council run audit: every stage entered in order, closed after Deliver,
agents on record while they ran, one check at a time, a deliverable, the claim index, every seat on record, every
agent seat with a token figure, the agent limit, and any push let past the freeze. Each check says pass, warn or FAIL
through say(verdict, label, words)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict

from council.clock import iso_moment
from council.records import events as event_stream
from council.records import cells, paths, usage, usage_gaps
from council.records import plan as run_plan
from council.records import stages as run_stages
from council.records import seats as seat_files
from council.records import state as run_state
from council.records.audit_file import FAIL, PASS, WARN
from council.records.home import absolute, native

Say = Callable[[str, str, str], None]
Event = Dict[str, Any]

MAX_FILE = 64 * 1024 * 1024
STAGES = ("convene", "prepare", "assign", "brief", "work", "collect", "judge", "challenge", "deliver", "learn")
RANK = dict((stage, n) for n, stage in enumerate(STAGES))
RANK["build"] = RANK["work"]                       # council-implement's build loop stands in for stages 3-7
SEAT_STAGES = ("assign", "brief", "work", "collect")   # stages 3-6: a run with no worker seat skips them
MODES = ("council-review", "council-plan", "council-implement", "council-research", "council-postgame",
         "council-health")
CLAIM_MODES = ("council-review", "council-plan", "council-research")
VERDICTS = ("CONFIRMED", "REFUTED", "UNCERTAIN", "MISCITED")


def clock(when: datetime | None) -> str:
    return when.astimezone().strftime("%H:%M:%S") if when else "?"


def listed(names: Any, most: int = 4) -> str:
    names = list(names)
    return ", ".join(names[:most]) + (" and %d more" % (len(names) - most) if len(names) > most else "")


class Run:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.name = folder.name
        self.fields = run_state.header(run_state.text(folder, read=lambda path: paths.text_of(path, limit=MAX_FILE)))
        self.mode = self.field("mode")
        self.status = self.field("status").split(" ")[0]
        self.events = [e for e in event_stream.records(folder, MAX_FILE) if e.get("type")]
        for event in self.events:
            event["t"] = iso_moment(event.get("at"))
        self.plan = run_plan.rows(folder, MAX_FILE)
        self.seats = seat_files.rows(folder, MAX_FILE)
        self.usage = seat_files.usage_rows(folder, MAX_FILE)
        self.roles, self.selected = {}, []
        for row in self.plan:
            if row.get("kind") == "seat" and row.get("field") == "role":
                self.roles[row.get("id", "")] = row.get("value", "").strip()
            if row.get("kind") == "seat" and row.get("field") == "disposition" and row.get("value",
                                                                                           "").strip() == "selected":
                self.selected.append(row.get("id", ""))
        self.size = next((r.get("value", "").strip() for r in self.plan
                          if r.get("kind") == "run" and r.get("field") == "size"), "")

    def field(self, key: str) -> str:
        return self.fields.get(key, "").strip()

    def of_type(self, *types: str) -> list[Event]:
        return [e for e in self.events if e["type"] in types]

    @property
    def closed(self) -> Event | None:
        found = self.of_type("run.closed", "run.paused")
        return found[-1] if found else None

    def phase_before(self, index: int) -> str:
        """The stage the run was in at its index-th event: the last run.opened or run.phase_changed before it in the
        stream. By the records' order, never their times: a stamp has one-second resolution, so a gate run in the
        second its stage began read as run in the stage before."""
        phase = "convene"
        for event in self.events[:index]:
            if event["type"] in ("run.opened", "run.phase_changed"):
                phase = "convene" if event["type"] == "run.opened" else event.get("value", "")
        return phase

    def workers(self) -> list[str]:
        if self.plan:
            return [s for s in self.selected if self.roles.get(s) == "worker"] if self.size != "solo" else []
        return [r.get("slug") for r in self.seats if r.get("slug") != "chair" and not r.get("slug",
                                                                                            "").startswith("verify")]


# --- the run's records ----------------------------------------------------------------------------------------
def stages(run: Run, say: Say) -> None:
    label = "Stages"
    if not run.events:
        say(WARN, label, "no event stream (a run from before events.tsv), so the order of stages can't be read")
        return
    entered = [("convene" if e["type"] == "run.opened" else e.get("value", "")) for e in run.events
               if e["type"] in ("run.opened", "run.phase_changed")]
    path = [s for n, s in enumerate(entered) if n == 0 or s != entered[n - 1]]
    if run.mode not in MODES:
        need, why = [], ""                          # council-init, test-architect, context-core: no fixed path
    elif run.mode == "council-implement" or (run.mode in run_stages.ONE_PAGE and run.workers()):
        need, why = run_stages.required(run.folder), ""   # a one-page mode's path, its one definition (D50, D56, D60)
    elif run.mode == "council-postgame" or not run.workers():
        need = [s for s in STAGES if s not in SEAT_STAGES]
        why = "" if run.mode == "council-postgame" else " (stages 3-6 are skipped: no worker seat was selected)"
    else:
        need, why = list(STAGES), ""
    missing = [s for s in need if s not in entered] if run.status == "complete" else []
    back = ["%s back to %s" % (a, b) for a, b in zip(path, path[1:]) if RANK.get(b, 99) < RANK.get(a, -1)]
    unknown = [s for s in path if s not in RANK] if run.mode in MODES else []    # setup names its own phases
    shown = " > ".join(path) or "none"
    # council state phase=... skip="<why>"
    said = [event_stream.details(e.get("detail")) for e in run.of_type("run.phase_changed")]
    said = "".join("; %s skipped on purpose: %s" % (d["skipped"].replace(",", ", "), d.get("reason", "?"))
                   for d in said if d.get("skipped"))
    if missing:
        say(FAIL, label, "%s; never entered: %s%s%s" % (shown, ", ".join(missing), why, said))
    elif back or unknown or said:
        say(WARN, label, "%s; %s" % (shown,
                                     "; ".join(["went " + b for b in back] + ["not a stage: " + u for u in unknown]
                                                     + ([said[2:]] if said else []))))
    else:
        say(PASS, label, shown)


def closing(run: Run, say: Say) -> None:
    label = "Closed after Deliver"
    closed = run.closed
    if run.status == "complete" and not run.events:
        say(WARN, label, "no event stream (a run from before events.tsv), so when it closed can't be read")
    elif run.status == "complete":
        if not closed:
            stamped = run.field("closed")
            if stamped:                            # the close's own stamp, with its event lost or never written
                say(WARN, label, "closed complete at %s by the state's own stamp, but the event stream holds no close "
                    "event, so whether Deliver came first can't be read" % stamped)
            else:
                say(FAIL, label, "the state says complete, but no close is recorded; close it with: council run close "
                    "--run %s" % run.name)
            return
        if run.mode not in MODES:                  # council-init, test-architect: their own phases, no Deliver
            say(PASS, label, "closed complete at %s (%s has no Deliver stage)" % (clock(closed["t"]),
                                                                                  run.mode or "this mode"))
            return
        end = cells.optional_number(closed.get("seq"))
        moves = [e for e in run.of_type("run.phase_changed") if cells.optional_number(e.get("seq")) is not None
                 and cells.optional_number(e.get("seq")) < end]
        deliver = [e for e in moves if e.get("value") == "deliver"]
        if not deliver:
            last = [e.get("value") for e in moves]
            say(FAIL, label, "closed as complete at %s without entering Deliver (its last stage: %s)"
                % (clock(closed["t"]), last[-1] if last else "convene"))
        else:
            say(PASS, label, "closed complete at %s; Deliver began at %s" % (clock(closed["t"]),
                                                                             clock(deliver[0]["t"])))
    elif run.status in ("abandoned", "paused"):
        say(WARN, label, "closed as %s, so no deliverable was due; the items below read what was done" % run.status)
    else:
        say(WARN, label,
            "the run is still %s: audit it again after council run close" % (run.status or "without a status"))


def agents_on_record(run: Run, say: Say) -> None:
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


def gates(run: Run, say: Say) -> None:
    runs = []
    for at, event in enumerate(run.events):
        if event["type"] == "gate.finished" and event["t"]:
            seconds = cells.optional_number(event_stream.details(event.get("detail")).get("seconds")) or 0
            runs.append({"name": event.get("subject", "?"), "end": event["t"], "stage": run.phase_before(at),
                         "start": event["t"] - timedelta(seconds=seconds)})
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
        key = (gate_run["name"], gate_run["stage"])
        counts[key] = counts.get(key, 0) + 1
    repeats = ["%s %d times in %s" % (name, n, stage) for (name, stage), n in sorted(counts.items()) if n > 1]
    if repeats:
        say(WARN, label, "ran again in the same stage: %s" % listed(repeats))
    else:
        say(PASS, label, "; ".join("%s in %s" % key for key in sorted(counts, key=lambda k: (RANK.get(k[1], 99),
                                                                                             k[0]))))


def deliverable(run: Run, say: Say) -> None:
    label = "Deliverable"
    if run.status != "complete":
        say(PASS, label, "not due: the run did not complete")
        return
    recorded = run.field("deliverable")
    if not recorded and run.mode not in MODES:
        say(PASS, label, "not due: %s has no Deliver stage" % (run.mode or "this mode"))
        return
    if not recorded:
        say(FAIL, label, "none recorded; at Deliver: council state deliverable=<path>")
        return
    home = run.folder.parent.parent            # <home>/runs/<run>; a copied run elsewhere is not looked up
    if home.name != ".council" or run.folder.parent.name != "runs":
        where = None
    elif absolute(recorded):
        where = Path(native(recorded))
    elif recorded.replace("\\", "/").startswith(".council/"):
        where = home.parent / recorded
    else:
        where = Path(run.field("code-root") or str(home.parent)) / recorded
    if where is not None and not where.exists():
        say(WARN, label, "recorded as %s, but there is no such file now" % recorded)
    else:
        say(PASS, label, recorded)


def claim_index(run: Run, say: Say) -> None:
    if run.mode not in CLAIM_MODES:
        return
    label = "Claim index"
    index = run.folder / "claims.jsonl"
    if run.status in ("paused", "abandoned") and not index.is_file():   # built after Challenge: a pause comes before
        say(PASS, label, "not due: the run is %s" % run.status)
        return
    if not index.is_file():
        say(FAIL, label, "missing: council evidence check --run %s builds it and checks it" % run.name)
        return
    newer = [p.name for p in [run.folder / "synthesis.md"] + sorted(run.folder.glob("verify-*.md"))
             if p.is_file() and p.stat().st_mtime > index.stat().st_mtime + 1]
    claims = cells.jsonl_rows(paths.text_of(index, limit=MAX_FILE))
    kept = [c for c in claims if c.get("disposition") == "kept"]
    open_claims = [str(c.get("id", "?")) for c in kept if str(c.get("verdict", "")).upper() not in VERDICTS]
    # A cut claim a verifier CONFIRMED is a lone dissenter that was right — unless synthesis.md says why it
    # stays cut (`still-cut: <why>`, recorded as still_cut), which council evidence check accepts too.
    confirmed_cut = [str(c.get("id", "?")) for c in claims if c.get("disposition") == "cut"
                     and str(c.get("verdict", "")).upper() in ("CONFIRMED",
                                                               "MISCITED")   # evidence check's TRUE_VERDICTS
                     and not str(c.get("still_cut", "")).strip()]
    refuted = [str(c.get("id", "?")) for c in kept if str(c.get("verdict", "")).upper() == "REFUTED"]
    if newer:
        say(FAIL, label, "out of date: %s changed after it was built; council evidence check --run %s builds it "
            "again and checks it" % (listed(newer), run.name))
    elif refuted:
        say(FAIL, label, "kept, but a verifier REFUTED it: %s — move it under ## Cut, or get it a new verdict; then "
            "council evidence check --run %s" % (listed(refuted, 8), run.name))
    elif confirmed_cut:
        say(FAIL, label, "cut, but a verifier CONFIRMED it: %s — ship it, or say in synthesis.md why it stays cut; "
            "then council evidence check --run %s" % (listed(confirmed_cut, 8), run.name))
    elif open_claims:
        say(FAIL, label, "kept claim(s) with no verifier's verdict: %s" % listed(open_claims, 8))
    elif not kept:
        say(PASS, label, "%d claim(s), none kept" % len(claims))
    else:
        say(PASS, label, "%d claim(s); all %d kept ones have a verifier's verdict" % (len(claims), len(kept)))


def seats_on_record(run: Run, say: Say) -> None:
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
                                    re.search(r"from:[ \t]*chair\b", paths.text_of(run.folder / "synthesis.md",
                                                                                   limit=MAX_FILE)) is not None)
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
        say(PASS, label, "all %d selected seat(s)%s" % (len(run.selected),
                                                        ", the Chair's own included" if chair else ""))


def agent_limit(run: Run, say: Say) -> None:
    label = "Agent limit"
    cap = next((cells.optional_number(r.get("value")) for r in run.plan
                if r.get("kind") == "budget" and r.get("id") == "run" and r.get("field") == "agent-cap"), None)
    closed = run.of_type("run.closed")
    used = cells.optional_number(event_stream.details(closed[-1].get("detail")).get("agent_runs")) if closed else None
    if used is None:
        used = sum(cells.optional_number(r.get("agents")) or 0 for r in run.seats)
    if not cap:
        say(WARN, label, "%d agent run(s); the plan names no cap to hold them to" % used)
        return
    allowed = [cells.optional_number(r.get("until")) for r in seat_files.allowance_rows(run.folder, MAX_FILE)
               if cells.optional_number(r.get("until"))]
    if used <= cap:
        say(PASS, label, "%d of %d agent runs" % (used, cap))
    elif allowed and allowed[-1] >= used:
        say(PASS, label, "%d agent runs, past the cap of %d on the go recorded with council cap allow (up to %d); "
            "whether the user gave it, the transcript's step check says" % (used, cap, allowed[-1]))
    else:
        say(FAIL, label, "%d agent runs against a cap of %d, with no go from the user on record for them" % (used, cap))



def token_figures(run: Run, say: Say) -> None:
    """Every seat that was an agent run has a token figure. Graded FAIL, as the other gaps in a run's own record
    are: the Chair left the run total and the ledger short, and can put it right with council correct."""
    label = "Token figures"
    if run.status != "complete":
        say(PASS, label, "not checked: the run did not complete")
        return
    gaps = usage_gaps.unfigured(usage.seat_list(run.folder), skip=usage_gaps.chairs(run.roles))
    if not gaps:
        say(PASS, label, "every agent run's tokens are on record")
        return
    fix = 'council correct <seat> tokens=<exact> agents=<exact> evidence="<source>" --run ' + run.name
    lead = "%d seat(s) ran as agents with no token figure, so the run total and the ledger leave them out"
    say(FAIL, label, "%s: %s; put one right with %s" % (lead % len(gaps), usage_gaps.words(gaps), fix))


def pushes_allowed(run: Run, say: Say) -> None:
    """A push or PR let past the push freeze with COUNCIL_ALLOW_PUSH=1 (run.push_allowed): a warning, never a FAIL —
    the escape is the user's to give — so a reader can check that each rested on their word. Nothing when there
    were none, so the report of every other run reads as before."""
    found = [e.get("value", "") for e in run.of_type("run.push_allowed")]
    if not found:
        return
    counts = ", ".join("%s %d" % (what, found.count(what)) for what in sorted(set(found)))
    say(WARN, "Pushes past the freeze", "%d went ahead with COUNCIL_ALLOW_PUSH=1 while the push freeze held (%s); "
        "each should rest on the user's word" % (len(found), counts))
