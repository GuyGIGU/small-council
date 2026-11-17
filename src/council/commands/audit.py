"""Check a finished council run against what the method promises. Read-only: no model, no network.

    council run audit [--run <run folder>] [--transcript <session .jsonl>]

The suites test the helper; this reads what a Chair actually did. From the run's own records
(session-state.md, events.tsv, run-plan.tsv, seats.tsv, usage.tsv, cap-allowances.tsv, claims.jsonl):
every stage entered in order; closed complete only after Deliver; every agent on record as running
before it finished; one check (gate) at a time, each once per stage; a deliverable; for a review,
plan or research run the claim index, with a verifier's verdict on every kept claim; every seat the
plan selected on record, the Chair's own included; every agent seat with a token figure; the agent
limit. With a Claude Code session transcript it reads the main thread from the turn that opened the
run to the end of the turn that closed it. The Chair's steps (audit_steps.py): the size and cost recorded before
the first dispatch, the status card at the first dispatch, the rulings as one question at Deliver, a message from
the user before each go past the cap, the closing card after close. How it called the helper: by its plain name
`council`, no output cut short by `| tail` or `| head`, every refusal (told by the call's exit) tried again. Each
item says pass, warn or FAIL in plain words; one the transcript holds none of the run for, n/a.
It only opens files to read them and writes nothing, bytecode included, except with --save (council run close):
then it keeps the report as the run's audit.md. Exit 0 when nothing failed, 1 when something did, 2 when it cannot
read the run or the transcript.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Optional, Tuple

from council.clock import iso_moment
from council.commands.audit_calls import invocations
from council.commands.audit_checks import (Run, Say, agent_limit, agents_on_record, claim_index, clock, closing,
                                           deliverable, gates, listed, seats_on_record, stages, token_figures)
from council.commands.audit_steps import (Entry, ToolCall, block_text, cap_goes, closing_card, exit_of, first_card,
                                          rulings_once, size_first)
from council.records import audit_file, paths
from council.records.audit_file import FAIL, LATER, PASS, UNCHECKED, WARN

Span = Tuple[datetime, Optional[datetime]]
ELSEWHERE = ("Size and cost before the first dispatch", "Status card at the first dispatch", "Closing card",
             "Helper called as plain council", "Helper output shown whole")   # the transcript's items


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
    gives each its own calls, and a pipe or a card is counted under one run only. A span whose open this file
    doesn't hold starts at its own time, and one with no helper call inside it isn't here at all: its calls were
    made from an agent or another session, and nothing this thread did then is the run's."""
    if not any(t for t, _, _ in entries) or not opened_spans:
        return entries
    keep, first = set(), next(t for t, _, _ in entries if t)
    for start, end in opened_spans:
        if end is not None and end + timedelta(minutes=30) < first:
            continue                               # a span from before this session: none of it is here
        opening = _opening(entries, start)
        opened = opening < len(entries) and lifecycle(entries[opening], ("run open", "run resume"))
        if not opened:
            if not _held(entries, start, end):
                continue
            opening = next((n for n, (t, _, _) in enumerate(entries) if t and t >= start - timedelta(seconds=2)),
                           len(entries))            # no open here: the span starts at its own time, not a call near it
        lo = opening
        for n in range(opening - 1, -1, -1) if opened else ():
            t, kind, _ = entries[n]
            if lifecycle(entries[n]) or (t and t < start - timedelta(minutes=30)):
                break
            if kind == "prompt":
                lo = n
                break
        keep.update(range(lo, len(entries) if end is None else _closing(entries, opening, end)))
    return [entries[n] for n in sorted(keep)]


def _held(entries: list[Entry], start: datetime, end: datetime | None) -> bool:
    """Whether this thread made a helper call while the span was open."""
    return any(t and start - timedelta(seconds=2) <= t and (end is None or t <= end + timedelta(seconds=1))
               and kind == "use" and block.get("name") in ("Bash", "PowerShell")
               and invocations(str((block.get("input") or {}).get("command", ""))) for t, kind, block in entries)


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
    if not part and spans(run) and any(t for t, _, _ in entries) and (not session or session in sessions):
        for label in ELSEWHERE:
            say(UNCHECKED, label, "not checked: this transcript holds none of the run — its helper calls were made "
                "from an agent or another session; pass that session's transcript to check it")
        return "none of the run is in it"
    if not part:
        say(WARN, "Transcript", "no lines in the run's window: is it this run's session file?")
        return "nothing in the run's window"
    times = [t for t, _, _ in part if t]
    span = "%s to %s" % (clock(times[0]), clock(times[-1])) if times else "the whole file: it carries no times"
    calls = tool_calls(part)
    size_first(run, part, calls, sessions, say)
    first_card(run, part, calls, sessions, say)
    rulings_once(run, part, calls, say)
    cap_goes(part, calls, say)
    closing_card(run, part, calls, closed, say)
    helper_calls(part, calls, say)
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


def helper_calls(part: list[Entry], calls: list[ToolCall], say: Say) -> None:
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

    if every:
        refusals(part, helper, say)


def refusals(part: list[Entry], helper: list[ToolCall], say: Say) -> None:
    """Each refusal tried again. A refusal is told by the call's exit, never by its words: a "council:" line in a call
    that exited 2 (D19), the helper its one and last command. Where the helper was not (chained, piped, or one of
    several), the call's exit is not its own, so a "council:" line there is named as hidden; any other is a note."""
    label = "Helper refusals tried again"
    exits = dict((b.get("tool_use_id"), exit_of(b)) for _, kind, b in part if kind == "result")
    missed, hidden, refused = [], [], 0
    for index, (_, t, block, found, output) in enumerate(helper):
        lines = [line.strip()[9:] for line in output.splitlines() if line.strip().startswith("council: ")]
        if not lines:
            continue
        sub = "/".join(sorted(set(i["sub"] for i in found)))
        if len(found) > 1 or not found[0]["last"]:
            hidden.append("%s %s: %s" % (clock(t), sub, lines[-1][:90]))
        elif exits.get(block.get("id")) == 2:
            refused += 1
            if not any(sub == i["sub"] for c in helper[index + 1:] for i in c[3]):
                missed.append("%s %s: %s" % (clock(t), sub, lines[-1][:90]))
    words = []
    if missed:
        words.append("%d refusal(s) with no later call of the same command: %s" % (len(missed), listed(missed, 2)))
    if hidden:
        words.append("%d call(s) printed a council: line where the helper was not the call's only and last command, so "
                     "its exit was hidden (the exit of a chained or piped call is the last command's, D21) — run each "
                     "council command as a call of its own: %s" % (len(hidden), listed(hidden, 2)))
    if words:
        say(WARN, label, "; ".join(words))
    else:
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
