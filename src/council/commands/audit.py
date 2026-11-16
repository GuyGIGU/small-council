"""Check a finished council run against what the method promises. Read-only: no model, no network.

    council run audit [--run <run folder>] [--transcript <session .jsonl>]

The suites test the helper; this reads what a Chair actually did. From the run's own records
(session-state.md, events.tsv, run-plan.tsv, seats.tsv, usage.tsv, cap-allowances.tsv, claims.jsonl):
every stage entered in order; closed complete only after Deliver; every agent on record as running
before it finished; one check (gate) at a time, each once per stage; a deliverable; for a review,
plan or research run the claim index, with a verifier's verdict on every kept claim; every seat the
plan selected on record, the Chair's own included; every agent seat with a token figure; the agent
limit. With a Claude Code session transcript it reads the main thread from the turn that opened the
run to the end of the turn that closed it: the status card at the first dispatch and after close; the
helper called as a plain
`council`; no helper output cut short by `| tail` or `| head`; every refusal of the helper tried
again. Each item says pass, warn or FAIL in plain words. It only opens files to read them and writes
nothing, bytecode included, except with --save (council run close): then it keeps the report as the run's
audit.md. Exit 0 when nothing failed, 1 when something did, 2 when it cannot read the run or the transcript.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from council.clock import iso_moment
from council.commands.audit_calls import Call, invocations
from council.commands.audit_checks import (MAX_FILE, Run, Say, agent_limit, agents_on_record, claim_index, clock,
                                           closing, deliverable, gates, listed, seats_on_record, stages,
                                           token_figures)
from council.records import audit_file, paths
from council.records import seats as seat_files
from council.records.audit_file import FAIL, LATER, PASS, WARN

Entry = Tuple[Optional[datetime], str, Any]
Span = Tuple[datetime, Optional[datetime]]
ToolCall = Tuple[int, Optional[datetime], Dict[str, Any], List[Call], str]   # position, time, block, calls, output
# The helper's advisory lines on stderr ("council: ..." without a refusal): everything else on a
# "council:" line is a refusal (die, exit 2) or a record that failed to write. A lock refusal is
# answered by waiting, not by a second call, so it is listed here too. evals/run_audit.py checks that
# each lead is still the helper's wording.
NOTE_LEADS = ("save the user's request", "another run is in progress", "a paused run is also open", "its code root is ",
              "first dispatch of this run", "run closed \u2014 show the user", "this run has used",
              "seats still marked", "the claim index is missing", "no request was filed", "no build log names",
              "the log has no", "cleared a gate lock", "WARNING",
              "several runs are open \u2014 only the paths", "checks are already running", "the run changed ",
              "now ignores asks/",
              "KB, over the ~")
NOTES = re.compile(r"council: (?:%s|\S+ now ignores asks/|\S+ is \d+ KB, over)"
                   % "|".join(re.escape(lead) for lead in NOTE_LEADS[:-2]))



def block_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def is_prompt(line: dict[str, Any], content: Any) -> bool:
    """A message the user typed (a /command included), not a tool result, a reminder or a notification."""
    if line.get("type") != "user" or line.get("isMeta"):
        return False
    if isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
        return False
    words = block_text(content).lstrip()
    return bool(words) and (not words.startswith("<") or words.startswith("<command-"))


def transcript_lines(path: Path) -> Iterator[dict[str, Any]]:
    """A session transcript's lines that read as JSON objects, an agent's (a sidechain) left out."""
    with open(str(path), "rb") as handle:
        for raw in handle:
            try:
                line = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            if isinstance(line, dict) and not line.get("isSidechain"):
                yield line


def read_transcript(path: Path) -> tuple[list[Entry], set[str]]:
    """The main thread's messages in order: (time, kind, payload). A line without a time takes the one before."""
    entries: list[Entry] = []
    sessions: set[str] = set()
    last = None
    for line in transcript_lines(path):
        if line.get("parent_tool_use_id"):
            continue
        last = iso_moment(line.get("timestamp")) or last
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


def spans(run: Run) -> list[Span]:
    """When the run was open, from its own events: each open or resume to the pause or close after it (None
    while it is still open). One session can drive several runs; each run's items read only its own spans."""
    found: list[Span] = []
    start = None
    for event in run.events:
        kind, when = event["type"], event["t"]
        if not when:
            continue
        if start is None and (kind in ("run.opened", "run.resumed") or
                              kind == "run.status_changed" and event.get("value") == "in-progress"):
            start = when
        elif start is not None and kind in ("run.paused", "run.closed"):
            found.append((start, when))
            start = None
    if start is not None:
        found.append((start, None))
    return found


def lifecycle(entry: Entry, subs: tuple[str, ...] = ("run open", "run resume", "run close")) -> bool:
    t, kind, block = entry
    if kind != "use" or block.get("name") not in ("Bash", "PowerShell"):
        return False
    return any(i["sub"] in subs for i in invocations(str((block.get("input") or {}).get("command", ""))))


def window(entries: list[Entry], opened_spans: list[Span]) -> list[Entry]:
    """The run's own part of the session: for each span, from the prompt of the turn that opened (or resumed)
    it — or from that call itself when another run opened or closed earlier in the turn — to the prompt after
    the turn that paused or closed it, stopping at another run's open. So a session that drives several runs
    gives each its own calls, and a pipe or a card is counted under one run only."""
    if not any(t for t, _, _ in entries) or not opened_spans:
        return entries
    keep, first = set(), next(t for t, _, _ in entries if t)
    for start, end in opened_spans:
        if end is not None and end + timedelta(minutes=30) < first:
            continue                               # a span from before this session: none of it is here
        opening = _opening(entries, start)
        lo = opening
        for n in range(opening - 1, -1, -1):
            t, kind, _ = entries[n]
            if lifecycle(entries[n]) or (t and t < start - timedelta(minutes=30)):
                break
            if kind == "prompt":
                lo = n
                break
        keep.update(range(lo, len(entries) if end is None else _closing(entries, opening, end)))
    return [entries[n] for n in sorted(keep)]


def _opening(entries: list[Entry], start: datetime) -> int:
    """The call that opened (or resumed) a span: the last open near its start, else the last call there."""
    near = [n for n, (t, kind, _) in enumerate(entries)
            if kind == "use" and t and start - timedelta(minutes=2) <= t <= start + timedelta(seconds=1)]
    opening = next((n for n in reversed(near) if lifecycle(entries[n], ("run open", "run resume"))),
                   near[-1] if near else None)
    if opening is None:
        opening = next((n for n, (t, _, _) in enumerate(entries) if t and t >= start - timedelta(seconds=2)),
                       len(entries))
    return opening


def _closing(entries: list[Entry], opening: int, end: datetime) -> int:
    """Where a span's part of the session stops: the prompt after the turn that paused or closed it."""
    near = [n for n, (t, kind, _) in enumerate(entries) if n >= opening and kind == "use" and t
            and end - timedelta(minutes=2) <= t <= end + timedelta(seconds=1)]
    closing = next((n for n in reversed(near) if lifecycle(entries[n], ("run close",))), near[-1] if near else None)
    if closing is None:
        closing = next((n for n in range(opening, len(entries)) if entries[n][0] and entries[n][0] > end), len(entries))
    for n in range(closing + 1, len(entries)):
        t, kind, _ = entries[n]
        if (t and t > end + timedelta(minutes=30)) or (kind == "prompt" and t and t > end) \
                or lifecycle(entries[n], ("run open", "run resume")):
            return n
    return len(entries)


def transcript(run: Run, path: Path, say: Say) -> str:
    """The transcript's items; returns the span it read, in words."""
    entries, sessions = read_transcript(path)
    closed = run.closed["t"] if run.closed else None
    part = window(entries, spans(run))
    session = run.field("session")
    if session and sessions and session not in sessions:
        say(WARN, "Transcript", "this file is session %s; the run was driven by %s" % (listed(sorted(sessions), 2),
                                                                                       session))
    if not part:
        say(WARN, "Transcript", "no lines in the run's window: is it this run's session file?")
        return "nothing in the run's window"
    times = [t for t, _, _ in part if t]
    span = "%s to %s" % (clock(times[0]), clock(times[-1])) if times else "the whole file: it carries no times"
    calls = tool_calls(part)
    first_card(run, part, calls, sessions, say)
    closing_card(run, part, calls, closed, say)
    helper_calls(calls, say)
    return span


def tool_calls(part: list[Entry]) -> list[ToolCall]:
    """Each tool call in the window: (position, time, tool_use block, its helper invocations, its output)."""
    results = dict((b.get("tool_use_id"), b) for _, kind, b in part if kind == "result")
    calls = []
    for n, (t, kind, block) in enumerate(part):
        if kind != "use":
            continue
        found = []
        if block.get("name") in ("Bash", "PowerShell"):
            found = invocations(str((block.get("input") or {}).get("command", "")))
        result = results.get(block.get("id"))
        calls.append((n, t, block, found, block_text(result.get("content")) if result else ""))
    return calls


def relayed(part: list[Entry], position: int, output: str) -> bool:
    """council status's Status: line passed on to the user in the text after it, before the next prompt."""
    status = next((line.split(":", 1)[1].strip() for line in output.splitlines() if line.startswith("Status:")), "")
    if not status:
        return False
    for _, kind, words in part[position + 1:]:
        if kind == "prompt":
            return False
        if kind == "text" and status[:40] in " ".join(words.split()):
            return True
    return False


def shows_status(part: list[Entry], call: ToolCall, found: list[Call]) -> bool:
    """A council status (not --line or --json) among found, relayed to the user after this call."""
    return any(i["sub"] == "status" and not {"--line", "--json"} & set(i["flags"]) for i in found) \
        and relayed(part, call[0], call[4])


def first_card(run: Run, part: list[Entry], calls: list[ToolCall], sessions: set[str], say: Say) -> None:
    """The status card at the first dispatch: between the first agent sent (or recorded) and its first result.
    It is owed once per run, at the run's first dispatch (context-core, "Talking to the user"): a run carried
    on in a later session made that dispatch in an earlier one, so a transcript that didn't make it owes none."""
    label = "Status card at the first dispatch"
    opened_at = next((n for n, t, block, found, _ in calls if any(i["sub"] == "run open" for i in found)), 0)
    sent = [n for n, t, block, found, _ in calls if n >= opened_at and (block.get("name") in ("Agent", "Task",
                                                                                              "Workflow")
            or any(i["sub"] == "seat" and re.search(r"\bseat\s+\S+\s+(running|queued)\b", i["text"]) for i in found))]
    starts = [(iso_moment(r.get("at")), r.get("session", "")) for r in seat_files.start_rows(run.folder, MAX_FILE)
              if not r.get("tool", "").startswith("before:")]          # the gate's starts name their session
    starts += [(iso_moment(r.get("at")), "") for r in run.usage if r.get("kind") == "dispatched"]
    first_at, first_by = min([s for s in starts if s[0]], key=lambda s: (s[0], s[1] in ("", "-")), default=(None, ""))
    began = next((t for t, _, _ in part if t), None)
    if first_by not in ("", "-") and sessions and first_by not in sessions:
        elsewhere = "session " + first_by
    elif first_at and began and first_at < began:
        elsewhere = "an earlier session"
    else:
        elsewhere = ""
    if elsewhere:
        say(PASS, label, "not this transcript's to show: the run's first dispatch, at %s, was made in %s — the card "
            "is owed once per run" % (clock(first_at), elsewhere))
        return
    if not sent:
        say(PASS, label, "no agent was dispatched, so none was due")
        return
    done = [n for n, t, block, found, _ in calls if n > sent[0]
            and any(i["sub"] == "seat" and re.search(r"\bseat\s+\S+\s+(done|failed|blocked)\b",
                                                     i["text"]) for i in found)]
    end = done[0] if done else len(part)
    shown = any(sent[0] <= call[0] <= end and ("show_widget" in str(call[2].get("name", "")) or
                                               shows_status(part, call, call[3])) for call in calls)
    if shown:
        say(PASS, label, "shown after the first agent went out at %s" % clock(part[sent[0]][0]))
    else:
        say(FAIL, label, "not shown: the first agent went out at %s, and no show_widget call or relayed "
            "council status followed%s" % (clock(part[sent[0]][0]), " before its result was recorded at %s"
                                           % clock(part[end][0]) if done else ""))


def closing_card(run: Run, part: list[Entry], calls: list[ToolCall], closed: datetime | None, say: Say) -> None:
    """The closing card: after this run's own close, to the end of that turn. A close the helper refused
    (is_error, "Exit code …", and no "closed <this run>" line) is no close, and another run's close in the
    same window is not this one's: this run's last close that printed its line is — a pause before it is
    not — else the last one that went through."""
    label = "Closing card"
    mine = r"\bclosed %s\b" % re.escape(run.name)
    refused = set(b.get("tool_use_id") for _, kind, b in part if kind == "result"
                  and (b.get("is_error") or block_text(b.get("content")).startswith("Exit code ")))
    closes = [(n, k, output) for n, t, block, found,
              output in calls if block.get("id") not in refused or re.search(mine, output)
              for k, i in enumerate(found) if i["sub"] == "run close"]
    named = [c for c in closes if re.search(mine, c[2])]
    close_at = (named[-1:] or closes[-1:] or [None])[0]
    if close_at is None:
        tried = any(i["sub"] == "run close" for c in calls for i in c[3])
        if closed or tried:
            say(WARN, label, "every council run close call in the window was refused, so the close can't be found"
                if tried else "no council run close call in the transcript's window, so it can't be checked")
        return
    n0, k0, _ = close_at
    shown = False
    for call in calls:
        n, _, block, found, _ = call
        if n < n0:
            continue
        if "show_widget" in str(block.get("name", "")) and n > n0:
            shown = True
        if shows_status(part, call, found[k0 + 1:] if n == n0 else found):
            shown = True
    if shown:
        say(PASS, label, "shown after the close at %s" % clock(part[n0][0]))
    else:
        say(FAIL, label, "not shown after the close at %s: no show_widget call, and no council status "
            "output passed on to the user" % clock(part[n0][0]))


def helper_calls(calls: list[ToolCall], say: Say) -> None:
    """How the helper was called: by its plain name, its output whole, each refusal tried again."""
    helper = [c for c in calls if c[3]]
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
    cut = ["%s council %s | %s" % (clock(t), i["sub"], i["cut"]) for _, t, _, found,
           _ in helper for i in found if i["cut"]]
    if cut:
        say(FAIL, label, "%d call(s) piped through tail or head, which hides the helper's exit status and can "
            "swallow a refusal: %s" % (len(cut), listed(cut, 3)))
    elif every:
        say(PASS, label, "no helper call piped through tail or head")

    label = "Helper refusals tried again"
    missed, refused = [], 0
    for index, (_, t, _, found, output) in enumerate(helper):
        lines = [line.strip() for line in output.splitlines()
                 if line.strip().startswith("council: ") and not NOTES.match(line.strip())]
        if not lines:
            continue
        refused += 1
        subs = set(i["sub"] for i in found)
        if not any(subs & set(i["sub"] for i in c[3]) for c in helper[index + 1:]):
            missed.append("%s %s: %s" % (clock(t), "/".join(sorted(subs)), lines[0][len("council: "):][:90]))
    if missed:
        say(WARN, label, "%d refusal(s) with no later call of the same command: %s" % (len(missed), listed(missed, 2)))
    elif every:
        say(PASS, label,
            "%d refusal(s), each followed by another try" % refused if refused else "the helper refused nothing")


def find_transcript(session: str) -> Path | None:
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


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check a finished council run against the method (read-only).")
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--transcript", type=Path, help="the Claude Code session .jsonl that drove the run")
    parser.add_argument("--at-close", action="store_true",
                        help="council run close's own audit: the closing card comes after")
    parser.add_argument("--save", action="store_true",
                        help="keep the report as <run>/audit.md (council run close does)")
    args = parser.parse_args(argv)
    folder = args.run
    if not paths.is_run(folder, refuse_links=False):
        print("audit: not a council run folder: {}".format(folder), file=sys.stderr)
        return 2
    if args.transcript is not None and not args.transcript.is_file():
        print("audit: no such transcript file: {}".format(args.transcript), file=sys.stderr)
        return 2
    run = Run(folder)
    found = None
    if args.transcript is None:
        args.transcript = found = find_transcript(run.field("session"))
    items = []

    def say(verdict: str, label: str, words: str) -> None:
        items.append((verdict, label, words))

    for check in (stages, closing, agents_on_record, gates, deliverable, claim_index, seats_on_record, token_figures,
                  agent_limit):
        check(run, say)
    split, span = len(items), ""
    if args.transcript is not None:
        try:
            span = transcript(run, args.transcript, say)
        except OSError as exc:
            print("audit: cannot read the transcript: {}".format(exc), file=sys.stderr)
            return 2
    if args.at_close:                     # run by council run close: the card it asks for comes after it
        items[:] = [(LATER, label,
                     "not checked yet: it follows this close; council run audit --run %s checks it" % run.name)
                    if label == "Closing card" else (verdict, label, words) for verdict, label, words in items]
    text, failed = audit_file.render(run, items, split, span, args.transcript, found is not None, args.save)
    print(text)
    if args.save:
        print(audit_file.save(folder, text))
    return 1 if failed else 0
