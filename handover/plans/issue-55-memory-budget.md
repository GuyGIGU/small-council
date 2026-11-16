# Plan: issue 55, a memory size budget and a tidy

Written 2026-11-16. The issue has no comments. It is moved up because T3's pack carries the memory in
scope (part 3): an overgrown memory does not make the pack bigger, it makes the 8,000-byte ceiling
drop whole parts.

## What it asks

1. A size budget in the config, default about 25 KB.
2. Past it, `council memory tidy` proposes merges and retirements as a reviewable diff, of three kinds:
   - the same rule under two ids;
   - a rule superseded by a later decision;
   - a rule now enforced by a hook.
3. The closing card nags once per run while memory is over the budget.

## What exists today

The budget half is mostly built, but hard-coded.

- `records/memory.py:16` holds `COUNCIL_MEMORY_SIZE_LIMIT = 25600`. It is a named value in architecture
  §6, it only ever warns, and no config key sets it.
- The warning is written by hand three times, with two roundings:
  - `memory.size_note`: run open
  - `views/status.py:318-329`: the status card, and only while a run is open, so the closing card never
    shows it
  - `doctor_memory.py:94-98`
- `audit.py` recognises the note by its lead ("KB, over the ~25 KB").
- No tidy exists. `memory.replace` is the one guarded rewrite and changes one entry per call.
  `references/doctrine/10-learn.md:43-46` already says how a consolidation is proposed: as numbered
  operations ("merge AP-7 into AP-3", "retire EC-2 — superseded by EC-9"), applied one by one on the
  user's yes, never as a wholesale rewrite.
- There is no real memory file in the repo. The evals use 30 KB and 66 KB files of filler.

## The plan

1. **The budget.** Add a `- memory budget: <n> KB` line under the config's `## Memory`, read by one new
   function in `records/config.py`, with 25 KB as the stated default. The named value stays as that
   default. The three warnings become one sentence in `records/memory.py`, used by run open, status
   and doctor, and it keeps the audit's lead.
2. **The nag.** Add one `closing.CHECKS` code (for example `memory-over`), so `run close` warns once per
   close. The closing card and the `run.closed` event's `warnings=` then carry it. No per-run state is
   needed, because a close happens once.
3. **`council memory tidy`.** It prints numbered operations and writes nothing. They are the same
   operations 10-learn.md describes, so the Chair proposes them and the user's yes applies them one at
   a time through `memory.replace`. Which of the three kinds it can find by reading:
   - **Same rule under two ids:** found by normalising each entry's rule text (case, spaces,
     punctuation) and comparing. Only exact matches after normalising count; near-duplicates are left
     to the Chair.
   - **Superseded by a later decision:** found when an entry's text names an id that is under
     `## Retired`, or carries a `superseded` mark (`memory_entries.MARKS`).
   - **Now enforced by a hook:** needs a reader of what the hooks enforce, which does not exist. Leave
     it out and say so. It would be guesswork.

## Files and tasks

| Task | Files |
|---|---|
| A. Budget and nag | `records/config.py`, `references/templates/council.config.md`, `records/memory.py`, `views/status.py`, `commands/doctor_memory.py`, `records/closing.py`, `commands/audit.py` (lead kept), `evals/run_cli.py`, `evals/run_status.py`, `evals/run_audit.py` |
| B. Tidy | `commands/memory.py` (a `tidy` sub, imported lazily like `select`), a new `commands/memory_tidy.py`, `records/memory_entries.py` (487 of 500 lines, so any reader goes in the new module, not here), `references/doctrine/10-learn.md` (5,260 of 6,000), `references/run/helper-commands.md`, `help.py`, `evals/run_cli.py`, `evals/run_memory.py` |

## What proves it

- Scenarios for each of these:
  - the budget read, including an unreadable value, which falls back to the default and says so;
  - the one warning at run open, status and doctor;
  - the close warning;
  - `tidy` on a fixture with a duplicate, a superseded entry and a clean entry.
- `tidy` writes nothing (the file's bytes are unchanged).
- The usual proof list and CI on all three OS.

## What could go wrong

- **Changing the warning text.** The audit and three eval files pin it, and some files would show a
  different number (doctor rounds by 1,024, the others by 1,000). That is a visible difference, so it
  needs its own CHANGELOG line.
- **Over-eager duplicate matching.** Merging two rules that only look alike would lose a rule. Keep
  the match exact after normalising, and leave the rest to the Chair.
- **New contract names.** The config key and `memory tidy` are both new.

## Rough cost

About 400-550k tokens: two Opus builders and the planner. The map is shared with issue 62.
