# Plan: issue 62, the map refreshed at close

Written 2026-11-16. The issue has no comments, so its body is the whole ask. It is moved up because
T3's pack prints the map's one-way rows: a pack drawn from a stale map is worse than a hand-written
brief.

## What it asks

1. At `council run close`, list the directories the run's diff touched.
2. The Chair gives one line for each, or `--map-unchanged`.
3. Those lines go under a dated section of `map.md`.
4. `council map touch <paths>` does the same outside a run.
5. The SessionStart banner shows staleness per top-level directory, not one number.

## What exists today

- **No code writes `map.md`.** `records/map_file.py` reads only the `map-commit:` stamp and the
  `## One way per job` table. The map is written by council-init's and council-research's prose.
- **Staleness is commit distance only.** The `map-commit:` stamp is compared against `git rev-list
  --count <sha>..HEAD` in three places:
  - `map_status.py`
  - `doctor.py:215-232`, which warns past 50 commits
  - `session_start.py:123-139`, which copies the stamp regex instead of calling `map_file.commit` (a
    second way)
- **`council map status` already counts changed files per top-level area** (`by_area`, 12 at most). The
  banner shows one number only.
- **Close never touches the map.** `run_close.py` has only `--status`, no step that asks the Chair for
  input, and nothing about the map.

## The plan

1. **One map writer.** Add it to `records/map_file.py` (through `paths.atomic_write`). It appends a
   dated `## Changes <date>` section with one line per directory and sets `map-commit:` to HEAD. It
   never touches the one-way table, whose heading and columns the plan check parses (D35).
2. **`council map touch <dir>="<line>" …`.** A subcommand in `commands/map_status.py`, or a
   `map_touch.py` that `map_status.main` routes to. The line form must be fixed in the plan before
   anyone builds: `<dir>="<line>"` pairs, or one `--line` per path. It is a new contract name either
   way.
3. **At close.** A complete close of a run that changed code says, on stderr, which top-level
   directories its diff touched since the run's opening commit. It names the next step:
   `council map touch …` or `council run close --map-unchanged`. It must never block an abandoned or
   paused close (D8). Open question: is a missing answer a refusal or a warning? A refusal makes
   `--map-unchanged` a new flag on close; a warning keeps close as it is. **I recommend a warning**,
   added as a `closing.CHECKS` code, so the closing card and the `run.closed` event's `warnings=` carry
   it.
4. **The banner.** It names the stalest top-level areas from `map_status.by_area`, for example
   "map: 625 commits behind; most changed since: src/ 41, docs/ 9". It goes through `map_file.commit`,
   which folds the copied regex as its own named step. SessionStart must stay fast and never write
   stdout on a fault (D20).

## Files and tasks

| Task | Files |
|---|---|
| A. Writer and `map touch` | `records/map_file.py`, `commands/map_status.py` (or the new `map_touch.py`), `dispatch.py`, `help.py`, `references/run/helper-commands.md`, `references/templates/map.md` (the dated section), `evals/run_cli.py`, `tests/py/test_reports.py` |
| B. Close and banner | `commands/run_close.py`, `records/closing.py`, `commands/session_start.py`, `evals/run_cli.py` (a lifecycle block), `evals/run_hook.py` (the banner text is pinned there) |
| C. Prose | `references/doctrine/02-prepare.md`, `skills/council-research/SKILL.md` (Learn), the init skill's Refresh line. The init skill has 305 characters left, so add nothing there; point at the reference. |

## What proves it

- A scenario for each of these (D25): `map touch`, its refusals, the close line for a run with changes
  and for one without, and the banner per area.
- The plan check still reads the table after a touch.
- The usual proof list and CI on all three OS.

## What could go wrong

- **A map that never gets a real refresh.** Dated lines pile up and the map grows past its ~250-line
  aim. The template should say that a refresh folds the dated sections into the body.
- **Review and research runs have no code diff.** The close line must stay silent for them.
- **New contract names.** `map touch` and possibly `--map-unchanged` are both new. A detail key on
  `run.closed` would extend the event contract (`references/run/event-stream.md`).

## Rough cost

About 400-600k tokens: two Opus builders and the planner. The facts map is done (Sonnet, about 157k,
shared with issue 55).
