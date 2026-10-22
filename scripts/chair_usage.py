#!/usr/bin/env python3
"""The Chair's own tokens for a council run, read from the session transcript. Read-only.

    python3 scripts/chair_usage.py --run <run folder> [--transcript <session .jsonl>]

Seats record what each agent used; the Chair's own reading and judging never had a record. Claude Code
writes every main-thread model call to the session's .jsonl with its usage. This sums, for the calls made
while the run was open (its events' open/resume to pause/close spans; an open span runs to now): the new
input, the input written to the prompt cache, and the output. Cache reads are left out: they are the
same context read again, and an agent's figure (its final context size) does not count them either. So
the figure says how much the Chair's own work grew, comparable with a seat's, not what it cost.

Each call is counted once (the transcript repeats a call's usage on every block it wrote). Agents'
calls (sidechains) are left out: their seats record them. With no --transcript, the session the run's
state names is looked up as council run audit does.

Prints one line, tokens=<n>;calls=<n>, and exits 0. Exits 3 with the reason on stderr when there is
nothing to read (no transcript found, no call inside the run's spans); 2 when the run can't be read.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit  # noqa: E402  (the run reader, its spans and the transcript finder)


def calls_in(path, opened):
    """{message id: fresh tokens} for the main thread's model calls inside the spans."""
    found = {}
    now = datetime.now(timezone.utc)
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
            when = audit.stamp(line.get("timestamp"))
            if usage is None or not key or when is None or key in found:
                continue
            # A second of slack each side: the helper's event times have whole seconds, the transcript's don't.
            if not any(start - timedelta(seconds=1) <= when <= (end or now) + timedelta(seconds=1) for start, end in opened):
                continue
            fresh = 0
            for name in ("input_tokens", "cache_creation_input_tokens", "output_tokens"):
                value = usage.get(name)
                if isinstance(value, int) and value > 0:
                    fresh += value
            found[key] = fresh
    return found


def main():
    parser = argparse.ArgumentParser(description="The Chair's own tokens for a council run (read-only).")
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--transcript", type=Path, help="the Claude Code session .jsonl that drove the run")
    args = parser.parse_args()
    if not (args.run / "session-state.md").is_file():
        print("chair usage: not a run folder: {}".format(args.run), file=sys.stderr)
        return 2
    run = audit.Run(args.run)
    path = args.transcript or audit.find_transcript(audit.field(run.state, "session"))
    if path is None or not Path(path).is_file():
        print("chair usage: no session transcript found for this run", file=sys.stderr)
        return 3
    opened = audit.spans(run)
    if not opened:
        print("chair usage: the run has no open span in its events", file=sys.stderr)
        return 3
    try:
        calls = calls_in(path, opened)
    except OSError as exc:
        print("chair usage: cannot read the transcript: {}".format(exc), file=sys.stderr)
        return 3
    if not calls:
        print("chair usage: no model call of the Chair's inside the run's spans", file=sys.stderr)
        return 3
    print("tokens={};calls={}".format(sum(calls.values()), len(calls)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
