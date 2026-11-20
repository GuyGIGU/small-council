# The build log — `<home>/logs/<YYYY-MM-DD>-<slug>.md`

council-implement's Chair writes the header from this file at Convene (step 5) and appends a task's
three lines after every task (Build, step 6). The log is tracked by git: it is the build's record
months later.

```
---
(kind: log, with the run's title, areas and date)
---
# Council Implementation Log — <feature or review title>
**Your request:** `.council/asks/<file>` — "<its first ~12 words>…"
Input: `<the plan, review or post-game, repo-relative>` · Run: <run folder> · Restore point: <council restore point's commit> · Baseline: <gate results before any change>

## Notes for later tasks
- <area>: <a fact a later task needs> (task <n>)        ← at most ~12; read first after a reset

## Task <n>: <title>
Files: `path` — <what changed and why, one line each>
Proof: change | preserve | gates only — <the check, and its saved outputs> · Gates: ✅ tests ✅ lint (or ❌ + what happened)
Ruling: <what you decided instead of stopping> — <why> — <cost if wrong>   (omit if none)
```

It closes with these sections:
- **Pre-existing issues** (fixed, or left on the user's ruling — never yours), and what went to
  known problems
- **`## Shortcuts and concessions`** — required, never omitted. One line per shortcut:
  `- <date> — <what I did instead> — <path> — <why> — <what undoing it would take>`, or the single
  word `none`. Logs are tracked by git, so this is the one place the pile stays visible months later;
  `council run close` warns when a build log has no such section.
- **`## Converge`:** `| Task | Done when | Result | Evidence | Proof |`, one row per task, written
  from the check at the end (the reader's and the runner's files, and your own check of their
  items): Result `met`, `partly met` or `not met` (after the fix round, `partly met → met`);
  Evidence how it was shown; Proof council check's verdict for the task. The closing card and
  `council tree` read this table.
- **Ready for review:** every file created or modified, which is the next review's target.

Its last line records the post-game offer: `Post-game: offered <date> — yes | no`, or
`Post-game: not offered`.

Plain English: what changed and why, never pasted code.
