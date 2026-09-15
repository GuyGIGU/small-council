---
name: council-implement
description: Build a Small Council plan task by task, or fix the findings of a council review — one builder, the governing expert's reference doc loaded per task, the project's real gates after every change, an adversarial verifier on each result, and a running log that feeds the next review. Use when the user says implement or build the plan, "fix these findings", "council implement", or invokes /council-implement.
---

# Council Implement (mode)

One builder, one task at a time, in this window — **not a fan-out**. **Invoke `context-core` first**
for its doctrine, layout, run files, resume, verification, memory, and close-out rules; skip its
partition and dispatch phases. The only agent you dispatch is the verifier.

**Voice of the build:** Carmack — the smallest change that satisfies the task, code that looks like
the same team wrote it, no speculative generality, verification by machine rather than by feel.

**Respect the project's hard rules** (config, `CLAUDE.md`/`AGENTS.md`). Never take a destructive
shortcut — dropping data, force-pushing, disabling a gate — to make a task pass.

## Two kinds of input

- **A plan** — `<home>/plans/<slug>.md` (legacy: `PLAN-<slug>.md` at the project root). Each task has
  Domain, Ref, Depends on, and Done when.
- **A review — fix mode** — `<home>/reviews/<date>-<slug>.md` (legacy: a `FINAL-REVIEW.md` in an old
  run dir). Each selected finding becomes a task: its seat's reference doc governs it, its Fix line is
  the ask, and "done" means the consequence can no longer happen. Default selection: every P1 and P2 —
  confirm it, or let the user pick.

## Phase 1 — Prepare (don't skip)

1. Read the input completely. Read `council.config.md` (Gates, Hard rules, Roster → reference map),
   memory (never build against an AP / EC / D — if a task conflicts, follow memory and log it), and
   `map.md`.
2. Map the code the tasks touch (Glob/Grep). Read every file in a task's scope before changing it.
3. **Order:** dependencies first (the plan's Depends on). Fix mode: P1 before P2, then group by file.
4. **Safety net:** not a git repo → recommend `git init` plus a first commit before any edit; if the
   user declines, copy each file to `<run>/backup/<path>` before its first change. Uncommitted work
   already present → note it and never discard it.
5. **Confirm once:** the task list, the order, and how the verifier will run (below) with its cost.
   Approval means autonomy to the end — stop only for a red mandatory gate you can't fix, a
   destructive step, a ruling that belongs to the user, or growth beyond the input.
6. **Open the run:** `<home>/runs/<TS>-implement/` (fix mode: `-fix/`), `session-state.md`,
   `active-run`, and the log at `<home>/logs/<YYYY-MM-DD>-<slug>.md` — write its header now.

## Phase 2 — Each task

1. **Load the governing reference doc first.** `references/<file>.md` →
   `${CLAUDE_PLUGIN_ROOT}/references/<file>.md` (project-local `.council/refs/…` → council home).
   Cross-referenced docs inform specific decisions. It is the constraint set, not background reading.
2. **Plan the change:** which files, the minimal diff, which principle constrains it, what it changes
   for later tasks, which watchpoints apply.
3. **Implement.** Match existing patterns. Build what the task says and nothing more — no "while we're
   here". Honour memory. *The function least likely to cause a problem is the one that doesn't exist.*
4. **Gates.** Run the config's gates for what you touched — full output to `<run>/gates/`, judged by
   exit code, never through a pipe to `tail`/`head`/`grep`.
   - Your change broke it → fix it before moving on.
   - A **mandatory** gate red → hard stop until it's understood.
   - Pre-existing failure → fix it if it's small and log it; otherwise log it and carry on.
   - Can't run (missing tool, deleted file) → config drift: log it and tell the user.
5. **Adversarial check.** Dispatch `small-council:council-verifier` with the task, its Done-when, and
   the changed files or diff. Verify every P1 fix and every risky task (data writes, security, core
   logic) on its own; batch two or three small tasks per verifier otherwise.
   - INCOMPLETE or REGRESSION → fix and re-verify, at most twice more, then stop and report.
   - SCOPE-CREEP → revert the extra change.
   - A finding that turns out to be wrong → don't "fix" it; log it as refuted, with evidence (a memory
     candidate).
6. **Log and state — now, not at the end.** Append the task's entry to the log and overwrite
   `session-state.md` (`next:` = the next task). This is what lets a reset resume mid-build.

## Log — `<home>/logs/<YYYY-MM-DD>-<slug>.md`, appended per task

```
# Council Implementation Log — <feature or review title>
Input: <plan or review path> · Started: <date> · Run: <run dir>

## Task <n>: <title>
Domain: <Seat> × Carmack — <principle> · Ref applied: <principle(s)>
Files: `path` — <what changed and why, one line each>
Gates: ✅ tests ✅ lint ✅ build   (or ❌ + what happened)
Verifier: OK   (or: fixed after INCOMPLETE — <what>)
Notes: <judgment calls, watchpoints hit, conventions followed — omit if none>
```

It closes with **Watchpoints addressed** · **Pre-existing issues fixed** · **Follow-ups** (anything out
of scope) · **Ready for review** (every file created or modified — the next review's target). The log
is plain English: what changed and why, never pasted code.

## Phase 3 — Close

Run the final gates on everything, finish the log's closing sections, propose memory candidates, and
close the run (Core phase 9). In chat: tasks done N/N, gate status, verifier results, anything blocked,
the log path — then offer a council review of the "Ready for review" files (Squad size is usually
right).

## Edge cases

- **The plan names code that no longer exists** → follow the intent, not the literal path; log it.
- **Blocked by something outside the input** (a key, a service, an env var) → do what you can, log the
  blocker, continue with the unblocked tasks.
- **Two tasks would be cleaner merged** → keep them separate for attribution; shared code goes in the
  first and is reused by the second.
- **The plan's approach looks wrong** → build it as written and log the concern; the review decides.
  Exception: it would break a hard rule or lose data → stop and ask.
- **Commits** → only if the user asked. Then one commit per task, never on the default branch without a
  yes, never a push unless asked.
