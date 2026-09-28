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

`evals/run_tui.py`: 21 checks, about 40 s, no model, against a run the helper itself opened, planned,
seated and gated. They check:
- the facts on screen (plan, seats, skipped reason, gates, repair next step, claim counts, memory
  proposals, budget, timeline);
- the `--json` snapshot;
- ASCII mode;
- that escape, bell and C1 codes never reach the terminal, whether they sit in a name, a number
  field, a note or a verdict, and that a note's newline cannot draw a line of its own;
- malformed values (a null or list exit) and 200,000-deep JSON, on screen and as data;
- an events.tsv over 4 MB, reported as too large;
- a linked gates folder and a linked run folder, neither followed;
- `--watch`: it keeps watching through a moment with no state file, and exits by itself once the
  run closes;
- a legacy run with malformed files still draws;
- `--watch` on a closed run reads it closed twice and stops;
- a folder that is not a run is refused;
- on Windows: 300 of the helper's own renames over a file it reads in a tight loop all succeed,
  while a plain reader (the control) makes some fail;
- five refusals, each with its own message;
- that every file of the run and the council home is byte-for-byte unchanged after drawing.

Also run: structural 619/619 and quick validation (0 warnings).

## Independent review

A reviewer checked `17769f7` without access to my reasoning. It found:

| Severity | Finding | Fix |
|---|---|---|
| medium | A gate's `exit` or `seconds` and a repair's `attempt` reached the screen uncleaned (a window-title or clipboard escape went through); `clean()` kept tab, newline and C1 codes. | Every value is cleaned, and every drawn line is swept again for C0 and C1 controls and line separators. |
| medium | `"exit": null` or a list crashed the screen; 200,000-deep JSON crashed both the screen and `--json`. | Numbers are coerced (unknown shows as `?`), and deep nesting is caught. |
| medium-low | `--watch` quit when `session-state.md` was briefly missing, and on Windows its reads could make the helper's rename of that file fail. | A missing file is read again; the watch stops only after two polls read the run as closed. Files are opened with delete sharing: 0 of 300 of the helper's own renames failed under a tight-loop reader, against 161 of 300 with a plain reader (the control). |
| low | An events.tsv over 4 MB showed as missing; a Windows junction was followed; the README's path fits only the developer install. | Too-large is said as such; links and junctions are refused for the run, its folders and its files; the README names both installs. |

Run against the old cockpit, 6 of the new checks fail; against the fixed one, 21 of 21 pass.

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
- A person looking at real macOS and Linux terminals. Automatic checks passed for the released
  code in CI runs `36305577961` and `36319880515` (checked 2026-09-28).
- Windows' legacy console. The cockpit asks it for ANSI support, and `COUNCIL_ASCII=1` is the
  fallback.
