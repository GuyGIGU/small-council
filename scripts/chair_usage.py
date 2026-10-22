#!/usr/bin/env python3
"""The Chair's own tokens for a council run, read from the session transcripts. Read-only.

    python3 scripts/chair_usage.py --run <run folder> [--transcript <session .jsonl>]

Seats record what each agent used; the Chair's own reading and judging never had a record. Claude Code
writes every main-thread model call to the session's .jsonl with its usage. A call's context is its new
input plus its cache reads and cache writes. This adds up how much the Chair's context grew while the run
was open (its events' open/resume to pause/close spans; an open span runs to now): for each call inside a
span, its context less the call before it, when that is more. That is the measure an agent's figure uses
(its final context size), so the two compare. A cache rebuilt after an idle gap moves tokens from reads to
writes and adds nothing; a compaction shrinks the context and adds nothing until it grows again.

Each call is counted once (the transcript repeats a call's usage on every block it wrote). Agents' calls
(sidechains) and Claude Code's <synthetic> entries (all-zero usage, no model call) are left out. The sessions read are the one the run's state names
and each one a resume came from (its run.resumed event's was=); with --transcript, that file alone.

Prints one line, tokens=<n>;calls=<n>;basis=<complete|partial>, and exits 0; partial means a session the
run was driven from had no transcript to read (or a resume from before was= was recorded), so the figure
is a floor. Exits 3 with the reason on stderr when there is nothing to read; 2 when the run can't be read.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit  # noqa: E402  (the run reader, its spans and the transcript finder)


def number(usage, name):
    value = usage.get(name)
    return value if isinstance(value, int) and value > 0 else 0


def calls_of(path):
    """The main thread's model calls in time order, once each: [(time, context size)]."""
    seen, calls = set(), []
    with open(str(path), "rb") as handle:
        for raw in handle:
            try:
                line = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            if not isinstance(line, dict) or line.get("type") != "assistant" or line.get("isSidechain"):
                continue
            message = line.get("message") if isinstance(line.get("message"), dict) else {}
            usage = message.get("usage") if isinstance(message.get("usage"), dict) else None
            key = message.get("id") or line.get("requestId")
            stamp = line.get("timestamp")
            when = audit.stamp(stamp) if isinstance(stamp, str) else None
            if usage is None or not isinstance(key, str) or when is None or key in seen:
                continue
            seen.add(key)
            size = sum(number(usage, n) for n in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            # Claude Code's <synthetic> entries (an interrupted or failed turn) carry all-zero usage: no model
            # call ran, and as a baseline it would count the next call's whole context as growth.
            if size and message.get("model") != "<synthetic>":
                calls.append((when, size))
    calls.sort(key=lambda c: c[0])
    return calls


def growth(calls, opened):
    """(tokens, calls) of context growth for the calls inside the spans."""
    now = datetime.now(timezone.utc)
    total = count = 0
    before = 0
    for when, size in calls:
        # A second of slack each side: the helper's event times have whole seconds, the transcript's don't.
        if any(start - timedelta(seconds=1) <= when <= (end or now) + timedelta(seconds=1) for start, end in opened):
            total += max(0, size - before)
            count += 1
        before = size
    return total, count


def main():
    parser = argparse.ArgumentParser(description="The Chair's own tokens for a council run (read-only).")
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--transcript", type=Path, help="the Claude Code session .jsonl that drove the run")
    args = parser.parse_args()
    if not (args.run / "session-state.md").is_file():
        print("chair usage: not a run folder: {}".format(args.run), file=sys.stderr)
        return 2
    run = audit.Run(args.run)
    opened = audit.spans(run)
    if not opened:
        print("chair usage: the run has no open span in its events", file=sys.stderr)
        return 3
    partial = False
    if args.transcript is not None:
        paths = [args.transcript] if args.transcript.is_file() else []
    else:
        sessions = [audit.field(run.state, "session")]
        for event in run.of_type("run.resumed"):
            was = re.search(r"(?:^|;)was=([^;]*)", event.get("detail") or "")
            if was is None or not was.group(1):
                partial = True                     # resumed before was= was recorded, or from no session: unknown
            elif was.group(1) and was.group(1) not in sessions:
                sessions.append(was.group(1))
        paths = []
        for session in [s for s in sessions if s]:
            found = audit.find_transcript(session)
            if found is None:
                partial = True
            else:
                paths.append(found)
    total = count = 0
    for path in paths:
        try:
            tokens, calls = growth(calls_of(path), opened)
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            print("chair usage: cannot read {}: {}".format(path, exc), file=sys.stderr)
            partial = True
            continue
        total, count = total + tokens, count + calls
    if not count:
        print("chair usage: no model call of the Chair's inside the run's spans", file=sys.stderr)
        return 3
    print("tokens={};calls={};basis={}".format(total, count, "partial" if partial else "complete"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
