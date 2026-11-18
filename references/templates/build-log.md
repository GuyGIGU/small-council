# The build log — `<home>/logs/<YYYY-MM-DD>-<slug>.md`

council-implement's Chair writes the header from this file at Convene (step 5) and appends a task's
entry after every task (the build loop, step 8). The log is tracked by git: it is the build's record
months later.

```
---
(the doctrine's frontmatter, kind: log)
---
# Council Implementation Log — <feature or review title>
**Your request:** `.council/asks/<file>` — "<its first ~12 words>…"
Input: `<the plan, review or post-game, repo-relative>` · Run: <run folder> · Start: <HEAD sha before task 1> · Baseline: <gate results before any change>

## Notes for later tasks
- <area>: <a fact a later task needs> (task <n>)        ← at most ~12; read first after a reset

## Task <n>: <title>
Domain: <what it checks> (<Seat>) × Carmack — <principle> · Ref applied: <principle(s)>
Files: `path` — <what changed and why, one line each>
Evidence: change | preserve · before <check> → <expected failure | passes> · after → passes · saved outputs: <paths>
Gates: ✅ tests ✅ lint ✅ build   (or ❌ + what happened)
Verifier: OK   (or: fixed after INCOMPLETE — <what>)
Ruling: <what you decided instead of stopping> — <why> — <cost if wrong>   (omit if none)
Notes: <judgment calls, watchpoints hit, conventions followed — omit if none>
```

It closes with these sections:
- **Watchpoints addressed**
- **Pre-existing issues** (fixed, or left on the user's ruling — never yours)
- **Follow-ups**
- **`## Shortcuts and concessions`** — required, never omitted. One line per shortcut:
  `- <date> — <what I did instead> — <path> — <why> — <what undoing it would take>`, or the single
  word `none`. Logs are tracked by git, so this is the one place the pile stays visible months later;
  `council run close` warns when a build log has no such section.
- **`## Converge`:** `| Task | Done when | Result | Evidence | Proof |`, written by the converge pass
- **Ready for review:** every file created or modified, which is the next review's target.

Its last line records the post-game offer: `Post-game: offered <date> — yes | no`, or
`Post-game: not offered`.

Plain English: what changed and why, never pasted code.

