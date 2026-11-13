---
name: council-implement
description: Build an approved Small Council plan, fix review findings or complete post-game tasks with one builder, task-appropriate proof and independent verification. Use for "build the plan", "fix these findings" or /council-implement.
---

# Council Implement (mode)

One builder, one task at a time, in this window. Parallel agents read; one hand writes code.
**Invoke `context-core`**, then run:
1. stages 1–2 with this file's sections;
2. **the build loop below**, in place of stages 3–7;
3. then stages 8–10.

You dispatch only verifiers (how many: build-proof.md, Checking — one, at converge, by
default) and at most one diagnosis worker per stuck task.

**Carmack's filter:** the smallest change satisfying the task, proved by machine.

**Respect the project's hard rules** (the config, `CLAUDE.md`/`AGENTS.md`). Never take a destructive
shortcut — dropping data, force-pushing, disabling a gate — to make a task pass.

## Three kinds of input

- **A plan:** `<home>/plans/<slug>.md`. Each task has Domain, Ref, Depends on, Touches and Done when.
- **A review (fix mode):** `<home>/reviews/<date>-<slug>.md`. Each selected finding becomes a task:
  - its seat's reference doc governs it;
  - its Fix line is the ask;
  - "done" means the consequence can no longer happen.

  Default: introduced or touched P1/P2s, including unknown origin. Use the user's existing selection.
- **A post-game:** `<home>/postgames/<date>-<slug>.md`. Each Next task is a task in the plan's
  format; its Done-when quotes the user's request.

## At Convene

1. **Read what drives the build.**
   - The input, in full.
   - `council.config.md`: gates, hard rules, the roster → reference map.
   - Memory: check its patterns, conventions and decisions against the task (Convene's
     changed-instructions rule); never silently retire or rewrite settled entries.
   - `map.md`.
2. **Order the tasks.** Dependencies first. In fix mode: P1 before P2, then group by file.
3. **Safety net.** If it isn't a git repo, recommend `git init`. If the user declines, copy each
   file to `<run>/backup/<path>` before its first change. Uncommitted work: note it, never discard it.
4. **Carry forward approval, or confirm once:**
   - the task list and order;
   - how the verifier will run, and its cost;
   - *"One commit per task on <branch>, so each task can be reverted?"* Recommended. Never commit on
     the default branch without a yes, and never push unless asked.

   Use Convene's approval rule; state the order and proceed when authorized. Without commit
   authorization, do not commit. The baseline question below still applies once, before task 1; a
   red mandatory gate you cannot fix stops the affected task.
5. **Open the run.** `council run open council-implement`. Continue the input's request (Convene,
   step 8). Then write the log header at `<home>/logs/<YYYY-MM-DD>-<slug>.md`.
6. **Rulings, not stalls.** Inside the approved scope, decide ambiguities and plan defects yourself
   and log each as a Ruling; stop only for a destructive action, a push or shared branch, a
   public contract, or scope or budget beyond approval.

## At Prepare — the baseline

Run every gate once on the untouched code: `council gate --all`; each gate's output is kept as
`gates/baseline/<name>.txt`. It skips gates marked not runnable
and gates with cost, hardware, deploy or credential side effects; record those as not run. Record what already fails before you
touch anything, e.g. `council state baseline="tests: exit 1 (3 failing) · lint: pass"`. A
pre-existing failure is never blamed on a task.

**A red baseline is never waved through.** One numbered question before task 1 — one, not a
conversation — when either:
- **it exits 4:** quote the helper's own NOTHING WAS CHECKED line, which names the real cause (no check
  configured at all, an older Gates layout, none that runs at this stage, or every one skipped), and
  say what it means here: nothing built in this run can be proved by machine. For an older Gates
  layout, offer the council-init refresh that migrates it; otherwise offer to fit the missing ones first
  (`${CLAUDE_PLUGIN_ROOT}/references/guardrails.md`, through a council-init refresh or a guardrails
  plan). Building anyway is a fine answer — it just has to be the user's. Never substitute a cause of
  your own: a project whose suite passed at grounding and has no gate at verify has checks, just not
  here.
- **a mandatory gate is already red:** say which, and since when if git or the logs say.

Record the answer in ask.md under `## Later, in your words`, with the date. Until it goes green, the
receipt's `Checked by machine:` line ends with **exactly one clause** about it — never a paragraph:
*"… · the test suite has been red since 4 August, so nothing here was verified by it"*. It disappears
the moment it passes.

Before changing code, make sure the run plan names the inline Chair and expected verifiers with
their context and tool budgets; `council run plan check` must pass. Then `council state phase=build`,
not `assign`: the build loop replaces the stages in between. When
the converge pass starts, `council state phase=challenge`.

## The build loop — for each task

1. **Load the governing reference doc first.** Plugin references live under `${CLAUDE_PLUGIN_ROOT}`;
   project-local `.council/refs/…` under the council home.
2. **Before-evidence — choose proof for the task before editing.** Read
   `${CLAUDE_PLUGIN_ROOT}/references/build-proof.md`, the authoritative mode, coverage and pair
   contract — which tasks need a pair under the light tier (the default), compiling a new check
   first, `council gate before-<n>` and `--invalid` — and follow it. Log the mode and invariants.
   Label support with `references/run/evidence-model.md`; cite saved outputs for `REPRODUCED`.
3. **Plan the change:** files, minimal diff, governing principle, effects on later tasks, watchpoints.
4. **Implement.**
   - Match existing patterns.
   - Build what the task says, nothing more — no "while we're here".
   - Honour memory.
   - *The function least likely to cause a problem is the one that doesn't exist.*
5. **Gates for what you touched:** `council gate <name>`, judged by exit code.
   - **Never run a gate whose side effects involve cost, hardware, deploys or credentials** without
     asking the user first (`council gates` lists them).
   - **Your change broke it** → fix it before moving on.
   - **A mandatory gate is red that was green at baseline** → hard stop until you understand why.
   - **Red at baseline and waved through** → carry on: check only that your change added no new
     failure — `council gate <name>` names the tests failing now that `gates/baseline/<name>.txt`
     didn't name. When it can't compare, read both outputs side by side. Keep the standing clause
     on the receipt.
   - **It can't run** → config drift (Prepare, Rules); log it too.
   - **It fails during this task** → the bounded loop in `references/run/repair-loop.md`: `council gate`
     records it (no `council repair record`); inspect its saved output and baseline, repair, and rerun
     the **same** gate. The third failed execution blocks the task: jump to blocked-task logging and
     the receipt (`council state phase=deliver skip="blocked: task <n>"`);
     do not attempt steps 6–7 as a fix path. A blocked build stops for the user (context-core,
     Alerts).
6. **After-evidence — only if the task is not blocked.** Run the same check again,
   `council gate after-<n> -- '<same command>'`, keeping `--proof preserve` if selected before editing.
   It must pass under the build-proof contract.
7. **Adversarial check — per task only, if not blocked.**
   Dispatch `small-council:council-verifier` with:
   - the task and its Done-when;
   - the proof mode and, for preservation, the invariants and their test paths;
   - the governing principle's text, quoted, so it is checked, not cited;
   - the diff, written to `<run>/diff-<n>.patch`, passed by path;
   - the before, after and gate outputs in `gates/`;
   - the task's risk class as the plan marks it, so a pair-less risky task is refused.

   It judges the Done-when only (build-proof.md, Checking).

   Batch as Checking says; track each with `council seat verify-<n> …` (one stopped at its turn limit:
   context-core, Limits). Then act on the verdict:
   - **INCOMPLETE or REGRESSION** → fix it and re-verify. The re-check writes `verify-<n>b.md` (then
     `c`), so the first verdict stays on disk. A fix that would add a task or a new mechanism — a
     lock, a guard, a file, another re-check round — gets one line to the user first.
   - **A second failed verification** → a **clean-context diagnosis** (repair-loop.md, The diagnosis
     worker: its brief and `<run>/seats/diagnose-<n>.md`) if this task has not already used its one
     diagnosis worker for a gate failure; otherwise stop and report. Then one more attempt;
     still failing → stop and report. A third check is refused (by `council seat` and the agent gate)
     until a `diagnose-…` seat is on record after the second verdict, or the user's go is
     (`council state decision="…"`).
   - **SCOPE-CREEP** → revert the extra change.
   - **CANNOT VERIFY** → add the missing check, or say why none can exist.
   - **A wrong finding** → don't "fix" it; log it as refuted, with evidence.
8. **Log and state — now, not at the end.**
   - Append the task's log entry.
   - Include each failed gate attempt's category, suggested lens, actual cause (or uncertainty),
     snapshot paths and next action. `council repair check T<n>` checks saved snapshots when used.
   - Update the state: `council state next="task <n+1>: <title>" attempts="T<n> 1/3"`. Keep a short
     "tried and failed" list there too.
   - If commits are on, commit only a task whose mandatory gates pass and whose verifier has no
     unresolved regression. Leave blocked work uncommitted; log its diff and state. Rollback needs
     the user's decision.

## The log — `<home>/logs/<YYYY-MM-DD>-<slug>.md`, appended after every task

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

## At Challenge — converge

After the last task, one council-verifier checks every task's Done-when against the final tree. In
fix mode, it checks every selected finding's consequence instead. Each gets met, partly met or not
met, with evidence — written into the log's `## Converge` table; its `## Noticed` lines go under
Follow-ups, never into a task.
- Anything not met → one more task, or a logged follow-up. That round is the **finish line**: a
  build ends at its plan's last task plus one fix round after converge; anything beyond is a
  follow-up or a new review run, never a hunt inside the build. One per batch: gates prove the fix round;
  a re-check needs the user's recorded go.
- Then run the final gates: `council gate --all --at verify` (exit 4: context-core, The helper).
- If this run has `repairs.jsonl`, run `council repair check`; a broken saved repair trail is
  reported, never folded into a green receipt. Without Python, audit the log's attempts and
  saved gate outputs by hand.
- Draft any PR text as `<run>/pr-body.md`; the PR is opened from it at Deliver, after the user's OK.
  Then `council check`. It checks
  the saved before/after gates against their declared proof mode (`references/build-proof.md`) and
  names the saved test when it can. Copy each verdict and its
  full note into the `## Converge` table's **Proof** column: `ok` shows a change, `preserved` shows
  the checked invariants held on both versions. Broken proof is fixed or reported; no proof is
  reported as NO PROOF. Passing invariants alone never establish new behaviour.

## At Deliver — the receipt

The same seven lines after every build, in this order, whatever happened, so after three builds the
user reads it at a glance and notices the moment a line changes:

```
Built: <fully verified n> of <total n> tasks — <what you can do now that you couldn't before, or "no verified result"> [· <n> partly met or blocked: <one clause each>] [· push and PR held by the freeze[ until <date>]]
Works?: <what proved it — "ran <command> and <what happened>", or honestly "nobody ran it; proved by the tests and by reading the code">
Checked by machine: <the gates' verdict line, baseline → now> | <the helper's own NOTHING WAS CHECKED line, quoted> [· <the standing red-baseline clause>]
Shortcuts I took: <one line each> | none
Not proved: <what nobody actually checked> | nothing
Left open: <each pre-existing hazard, follow-up, verifier note not taken, known hazard from a handoff> | nothing
Cost: helpers ~<k>k tokens across <n> agents; Chair usage <actual total or "unavailable"> · <the proof line from council check> · log: <path>
```

The first `Built:` number counts only fully met tasks with required proof, passing mandatory gates,
and no unresolved verifier regression. A partly met or blocked task is named after the count but
is not counted as built: "5 of 6 tasks · 1 partly met: exports stop at 5,000 rows". A task stopped
by the repair limit is **blocked**, not merely partly met, even if some code works. A red mandatory
gate or known regression cannot be hidden behind a clean count. `Cost:` labels helper-only usage
as such; never imply it includes the Chair or the whole session when those figures are unavailable.
**Never omit the last four.** "none" and "nothing" are answers; silence isn't. A shortcut is one of
these — not a vibe: a hardcoded value, a skipped case, a swallowed error, a loosened or disabled
check, a test that asserts less than the behaviour, a TODO left behind, or a fix whose only proof was
a throwaway command. Every one also goes in the log's `## Shortcuts and concessions`.

A **guardrails task**'s both-ways proof (`${CLAUDE_PLUGIN_ROOT}/references/guardrails.md`) is
evidence, not a shortcut.

Then the rulings as one question (Deliver, step 6), and the memory proposals.

**No commit, push or PR question while anything is left open.** How items close is the config's
`- open items:` line (missing or unreadable: `ask`, and say so):
- **`ask`:** offer each `Left open:` item as *fix now* or *later* in that question
  — a data-loss hazard defaults to fix now — and wait: "later" is the user's ruling, never yours.
- **`fix now`:** no per-item question. Each item is one `Left open:` line — `<what> — ~<time> —
  ~<k>k tokens` — and you fix it like the fix round: gates prove it; a re-check or spend past the
  budget still needs the user's go; one you can't fix goes to the rulings question. A data-loss
  hazard still gets its own line to the user the moment you find it.

Commit, push and PR stay questions under either setting: ask them last, on their own, once the last
verifier (a post-game's too) is back, never beside a fix question, and in this order:
1. **The freeze:** `council pushes` reads the config's `- pushes:` line (missing means `on`). Under
   `off`, or `off until <date>` before that date, the freeze holds push and PR only: commit as
   authorized, record the commit in the log, and stop; the receipt's `Built:` line ends with the
   words it prints after the dash, the date included. The bash gate refuses the push meanwhile.
   From the date on, or for a word it can't read, it is `on`, and it says which.
2. **Fetch first:** `git fetch`, then `gh pr list --state all`. Say whether the base moved since
   `Start:` and whether a related PR merged; no remote or no `gh`, say that instead.
3. **The PR text:** print `<run>/pr-body.md` for the user's edit or OK. The PR question comes only
   after that OK.

Then **offer a post-game when the log shows one is worthwhile**
— at least one of:
1. converge found a Done-when partly met or not met, or the log has a follow-up;
2. the build hit trouble: a blocked task, a clean-context diagnosis, a SCOPE-CREEP revert, or a
   mandatory gate red at the end that was green at baseline;
3. the build left the plan: a material change of approach, plan-named code that no longer exists,
   or a task merged, split or skipped;
4. the request moved: the request file gained words after the plan, or the user ruled on scope
   mid-build;
5. it was big or long: 8 or more tasks, a war-room plan, or resumed after a compaction or in a new
   session;
6. it's the second fix pass on the same request.

Never after a fix pass that met every finding with no follow-ups, when the user already declined one
for this request (a log's `Post-game:` line), or when a post-game for this request is newer than this
log. The offer is one line, and it runs only on a yes: *"Want a post-game? It checks what we built
against your original request, word for word, and lists anything left to do — about ~<k>k tokens, 1
checker."* Record the answer as the log's last line. On a yes, finish Learn and close this run first
(`council run open` refuses a second run on the tree), then start council-postgame.

Then offer a council review of the "Ready for review" files — after the post-game, when both are
offered; a Squad is usually right.

## Edge cases

- **Plan names code that no longer exists** → follow the intent, not the path; log it.
- **Blocked by something outside the input** → log it; carry on with the other tasks.
- **Two tasks share one change** → change once; keep each Done-when, evidence and verdict.
- **"Also add X" mid-build** → record their words under ask.md's `## Later, in your words`; it is
  authorized. Ask only about scope or cost beyond the approved budget.
- **Evidence contradicts the plan** → Convene's Rules, *Evidence changes the approach*.
