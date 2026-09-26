# Phase 11 — a thin terminal cockpit

## What changed

- **`council tui`** (`scripts/cockpit.py`) draws one read-only screen of a run from its own files:
  - its mode, phase, status and request;
  - the plan's size, risk, complexity, uncertainty and verification level;
  - the estimated budget against the tokens spent (workers and verifiers separately), and agents
    against the cap;
  - each seat's state, tokens, role and context level, with planned and skipped seats and the
    reason a seat was skipped;
  - gates, each repair task's last attempt and next step, and claim verdict counts;
  - memory proposals waiting for the user;
  - the last events, with times shown locally.
- **`--watch`** redraws every two seconds and stops by itself when the run is no longer in progress.
- **`--json`** prints the snapshot as data (`council.run-snapshot/1`), so a later dashboard or
  history can read runs the same way.
- The README explains how to watch a run from your own terminal. The design is in
  `docs/design/tui-adr.md`.

## Why

A live run's state was spread over seven kinds of files and several helper commands. The roadmap
asked for a live cockpit outside the orchestration core.

## Architecture and compatibility

- **Read-only.** The cockpit reads files and writes nothing: no state, no event, no marker.
- **Not part of the core.** No stage calls it, and the doctrine does not mention it (a structural
  check guards this).
- **Flags.** `--watch` is a new boolean flag; every other command refuses it.
- **Degrades gracefully.** Without Python, the helper says which commands give the same facts.
  Legacy runs (no events, no plan) and malformed files still draw.

## Tests

`evals/run_tui.py`: 15 checks, about 17 s, no model, against a run the helper itself opened, planned,
seated and gated. They check:
- the facts on screen (plan, seats, skipped reason, gates, repair next step, claim counts, memory
  proposals, budget, timeline);
- the `--json` snapshot;
- ASCII mode;
- that a gate name holding an escape sequence never reaches the terminal;
- `--watch`: it redraws while the run is open and exits by itself within seconds of the run closing;
- a legacy run with malformed files still draws;
- `--watch` on a closed run draws once;
- a folder that is not a run is refused;
- five refusals, each with its own message;
- that every file of the run and the council home is byte-for-byte unchanged after drawing.

Also run: structural 619/619 and quick validation (0 warnings).

## Metrics / baseline comparison

None: this is an inspection tool. There is no claim that it improves runs.

## Known limitations

- One composite screen: no navigation, and no impact, context or per-claim screens.
- Polling, not push.
- Outside Claude Code the helper needs its full path.

## Deferred

- Per-area screens.
- Navigation.
- A history view across runs (Phase 12 uses the same snapshot).

## Not verified

- A live council run watched end to end.
- macOS Terminal and Linux terminals (CI runs the checks on all three once pushed).
- Windows' legacy console. The cockpit asks it for ANSI support, and `COUNCIL_ASCII=1` is the
  fallback.
