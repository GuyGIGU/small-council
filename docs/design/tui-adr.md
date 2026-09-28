# ADR: a thin terminal cockpit

## Problem

A council run spreads its state over several files:
- `session-state.md`;
- `run-plan.tsv`, `seats.tsv` and `events.tsv`;
- `gates/*.json`;
- `repairs.jsonl` and `claims.jsonl`.

While a run is live, the owner can only see it through the Chair's messages or several separate
helper commands. The roadmap asks for a live cockpit that is not part of the orchestration core.

## Constraints

- **No business logic in the UI.** The core must not depend on the cockpit, and the cockpit must not
  write, append events or decide anything.
- **Portability.** It has to work where the helper works: Windows Git Bash, macOS bash 3.2 and Linux.
  Python's `curses` is missing on Windows.
- **Optional.** Python stays optional, and there is no daemon, server or new dependency.
- **Robust.** The cockpit has to survive legacy runs, malformed files and hostile text (escape codes
  in names).

## Options

1. A full-screen curses application with navigable screens. Rich, but it does not run on Windows,
   and it is a large surface for a contract that is still settling.
2. A web dashboard. The roadmap puts that later, and it needs a server.
3. One read-only composite screen drawn from the run's files, with a `--watch` redraw loop and a
   `--json` snapshot for other tools.

## Decision

The original schema below is superseded in 0.14 by `council.run-snapshot/2`,
which replaces flat token totals with a `usage` block.

Option 3, as `council tui [--watch | --json]` (`scripts/cockpit.py`). The snapshot
(`council.run-snapshot/1`) collects:
- the run header;
- the plan's decisions and each seat's disposition and reason;
- seat states and tokens, with verifiers split from workers;
- agents against the cap;
- gates;
- each repair task's last attempt and next step;
- claim verdict counts;
- memory proposals waiting;
- the last events, with times shown locally.

`--watch` redraws every two seconds with ANSI clearing (on a terminal; plain frames otherwise). It
stops once two polls in a row read the run as closed; a state file that is briefly missing (a
helper replacing it) is read again, not taken for a closed run. `COUNCIL_ASCII=1` gives plain ASCII
for consoles that cannot show UTF-8.

**What it trusts.**
- **Every value** from a file — a number field included — is stripped of C0 and C1 controls (tab
  and newline too) before it is drawn.
- **Malformed values** (a null or list exit, deeply nested JSON) draw as unknown.
- **Links.** A file or folder that is a link or a Windows junction, or leads outside the run, is not
  read.
- **Windows file sharing.** On Windows every file is opened with delete sharing. Without it, a
  cockpit reading `session-state.md` at the wrong moment made the helper's own `mv` of that file
  fail: 161 of 300 renames in a tight-loop test, against 0 with delete sharing.

## Tradeoffs

- One screen, not eleven: the per-area views the roadmap sketches (impact, context, budget) are
  represented only where the run records them today.
- Polling every two seconds, not events pushed to the cockpit.
- The run is still resolved by the helper, so the owner's terminal needs the helper's full path
  outside Claude Code.

## Alternatives rejected

- curses.
- A background service.
- Writing a "last viewed" marker.
- Having the cockpit run gates or checks. Those belong to the core, which records them.

## Revisit when

- The event contract grows events for seat dispatch or claim verdicts, which would make a
  per-seat timeline worth drawing.
- Owners ask for navigation.
- A dashboard (Phase 12) needs the same snapshot across many runs.
