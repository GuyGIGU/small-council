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
stops by itself once the run is no longer in progress. Control codes in any file are neutralised
before display. `COUNCIL_ASCII=1` gives plain ASCII for consoles that cannot show UTF-8.

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
