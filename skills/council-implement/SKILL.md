---
name: council-implement
description: Build an approved Small Council plan (one council-plan wrote), fix council review findings or complete post-game tasks with one builder, task-appropriate proof and independent verification. Use for "build the council plan", "fix these council findings" or /council-implement; not for a plan the council did not write.
---

# Council Implement (mode)

One builder, one task at a time: a builder agent per task, or you yourself in a Solo build. Parallel
agents read; one hand writes code.
**Invoke `context-core`**, then run:
1. stages 1–2 with this file's sections;
2. **the build loop below**, in place of stages 3–7;
3. then stages 8–10.

You dispatch only builders (none in a Solo build), verifiers (how many: build-proof.md, Checking —
one, at converge, by default) and at most one diagnosis worker per stuck task. Outside a Solo build
you never edit project code yourself.

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
5. **Open the run.** `council run open council-implement`, then, in one call,
   `council state input=<the input's path> ask=<its "Your request" file>`: the build continues the
   input's request (Convene, step 7). Then write the log header at `<home>/logs/<YYYY-MM-DD>-<slug>.md`
   (The log, below).
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
- **it exits 4** (context-core, The helper): quote the helper's own NOTHING WAS CHECKED line, which names the real cause (no check
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

Before changing code, make sure the run plan names the Chair, the build seats (`task-<n>`, role
`worker`, one per task) and the expected verifiers with their context and tool budgets. A Solo build
is planned as Squad: the Chair, no `task-<n>` seats, and the converge verifier; `council run plan check` must pass. Then `council state phase=build`,
not `assign`: the build loop replaces the stages in between. When
the converge pass starts, `council state phase=challenge`.

## The build loop — for each task

Steps 1–6 build one round of the task (`${CLAUDE_PLUGIN_ROOT}/references/run/builder-loop.md`);
steps 7 and 8 are yours.

1–6. **Build the task.** Solo: follow builder-loop.md yourself, to its return line. Otherwise:
   - **Queue it:** `council seat task-<n> queued`. The helper names each file changed outside a saved
     round: log each; one you edited yourself is a shortcut, and goes on the receipt. It refuses a
     second build seat while one is queued or running, and a task that is or depends on a
     `NEEDS: fix` stop until the user's decision is on record (Edge cases). A builder goes out only
     from a queued seat, and takes it.
   - **Dispatch** `small-council:council-builder`, `model` from the plan row, with this message and
     nothing else. `Start:` is your only judgement; its orders come from `council context build task-<n>`,
     which it runs itself, so never paste them.

     ```
     Seat: task-<n>
     Run: <absolute run folder>
     Start: <where to start and what worries you; for a fix round, the verdict file and the item to fix>
     Write <absolute run folder>/report-<n>.md
     ```
   - **Record it:** `council seat task-<n> running agent=<id>`. On its line,
     `council seat task-<n> done tokens=<n> tools=<n>`; a `NEEDS:` return, `done note="NEEDS: …"`
     (repair-loop.md, Unknowns; Edge cases); a `BLOCKED:` return, `blocked note="…"`.
   - **Read** the line and `council patch show <n>`, never the diff.

   A `BLOCKED:` line (yours, in a Solo build): jump to blocked-task logging and the receipt
   (`council state phase=deliver skip="blocked: task <n>"`); do not attempt steps 6–7 as a fix path.
   A blocked build stops for the user (context-core, Alerts).
7. **Per-task check — only under `- checking: per task`, and only if not blocked.** Under the
   default, one per batch, skip this step: the converge check (At Challenge) is the build's one
   verifier, and the agent gate refuses a second without the user's go.
   Dispatch `small-council:council-verifier` with:
   - the task and its Done-when;
   - the proof mode and, for preservation, the invariants and their test paths;
   - the governing principle's text, quoted, so it is checked, not cited;
   - the round's saved patch and `patches/T<n>.md`, passed by path;
   - the before, after and gate outputs in `gates/`;
   - the task's risk class as the plan marks it, so a pair-less risky task is refused.

   It judges the Done-when only (build-proof.md, Checking).

   Batch as Checking says; track each with `council seat verify-<n> …` (one stopped at its turn limit:
   context-core, Limits). Then act on the verdict; a fix below is a new round, built by a fresh
   builder on the same seat (Solo: you), its `Start:` naming the verdict file and the item, its
   orders linking the task's history:
   - **INCOMPLETE or REGRESSION** → fix it as a new round (builder-report.md; a third in the same
     files: repair-loop.md, Fix rounds) and re-verify. The re-check writes `verify-<n>b.md` (then
     `c`), so the first verdict stays on disk. A fix that would add a task or a new mechanism — a
     lock, a guard, a file, another re-check round — gets one line to the user first.
   - **A second failed verification** → a **clean-context diagnosis** (repair-loop.md, The diagnosis
     worker: its brief, `<run>/seats/diagnose-<n>.md` and when a third check may run) if this task
     has not already used its one diagnosis worker for a gate failure; otherwise stop and report.
     Then one more attempt; still failing → stop and report.
   - **SCOPE-CREEP** → revert the extra change.
   - **CANNOT VERIFY** → add the missing check, or say why none can exist.
   - **A wrong finding** → don't "fix" it; log it as refuted, with evidence.
8. **Log and state — now, not at the end.**
   - Append the task's log entry.
   - Include each failed gate attempt, as repair-loop.md, The log, says.
   - Update the state: `council state next="task <n+1>: <title>" attempts="T<n> 1/3"`. Keep a short
     "tried and failed" list there too. After a compaction, resume from `council tree`.
   - If commits are on, commit only a task whose mandatory gates pass and whose verifier has no
     unresolved regression. Leave blocked work uncommitted; log its diff and state. Rollback needs
     the user's decision; then `council patch revert <n>` undoes the task's last saved round.

## The log — `<home>/logs/<YYYY-MM-DD>-<slug>.md`, appended after every task

Its template is `${CLAUDE_PLUGIN_ROOT}/references/templates/build-log.md`: copy its header at
Convene (step 5) and its task entry after each task. Its sections, in order: the header,
`## Notes for later tasks` (read first after a reset), one `## Task <n>` entry per task,
Watchpoints addressed, Pre-existing issues (fixed, or left on the user's ruling — never yours),
Follow-ups, `## Shortcuts and concessions` (required, never omitted: `none` when there are none),
`## Converge`, Ready for review, and last the `Post-game:` line. Plain English, never pasted code.

## At Challenge — converge

After the last task, dispatch one `small-council:council-verifier` as seat `verify-<n>`
(`council seat verify-<n> running agent=<id>`), writing `<run>/verify-<n>.md`. Send each task's
number and Done-when (fix mode: each finding's consequence), `patches/T<n>.md` and the saved
patches by path, `gates/`, the brief or plan path and the code root, never the log or the
builders' reports. It answers with its change verdicts. Write them into the log's
`## Converge` table as: OK → `met`; INCOMPLETE → `partly met` or `not met`, as its paragraph
says; REGRESSION → `not met`; SCOPE-CREEP → `met`, with the extra change under Follow-ups;
CANNOT VERIFY → `not met — cannot verify: <what's missing>`. Its `## Noticed` lines go under
Follow-ups, never into a task. A guardrails task's Gates row is yours now
(`${CLAUDE_PLUGIN_ROOT}/references/guardrails.md`, Fitting them).
- Anything not met → one more task, or a logged follow-up. That round is the **finish line**: a
  build ends at its plan's last task plus one fix round after converge; anything beyond is a
  follow-up or a new review run, never a hunt inside the build. One per batch: gates prove the fix round;
  a re-check needs the user's recorded go.
- Then run the final gates: `council gate --all --at verify` (exit 4: context-core, The helper). A gate
  already green on this very tree is not run again; its line names who ran it (`--rerun` runs it).
- If this run has `repairs.jsonl`, run `council repair check` (repair-loop.md, The log).
- Draft any PR text as `<run>/pr-body.md`; the PR is opened from it at Deliver, after the user's OK.
  Then `council check` (build-proof.md, Read the result). Copy each verdict and its
  full note into the `## Converge` table's **Proof** column: `ok` shows a change, `preserved` shows
  the checked invariants held on both versions. Broken proof is fixed or reported; no proof is
  reported as NO PROOF. Passing invariants alone never establish new behaviour.

## At Deliver — the receipt

**Read `${CLAUDE_PLUGIN_ROOT}/references/run/build-receipt.md` now, before you write anything**: the
receipt's rules, open items, the commit, push and PR order, and the post-game offer live there. The
receipt is the same eight lines after every build, in this order, whatever happened: `Built:`,
`Works?:`, `Checked by machine:`, `Your decisions:`, `Shortcuts I took:`, `Not proved:`,
`Left open:`, `Cost:`. Then the rulings as one question (Deliver, step 6), and the memory proposals.

## Edge cases

- **Plan names code that no longer exists** → follow the intent, not the path; log it.
- **Blocked by something outside the input** → log it; carry on with the tasks that do not rest on it.
- **A `NEEDS: fix` return** (a bug in the code under a task: repair-loop.md, Unknowns) → stop that
  task and every task that depends on it (`Depends on`; the helper refuses them). A task that only
  shares the code is not stopped: its builder is held to the same rule. Tell the user in one line: what
  is wrong, where, and what is stopped. The fix is a new task above the blocked one, with its own
  Owner and the Serves line of the task it unblocks; it starts only on the user's yes. The stopped
  builder held its unsaved edits (`council patch hold <n>`), and that task's next pack tells its
  builder to run `council patch apply <n> --held`.
- **Two tasks share one change** → change once; keep each Done-when, evidence and verdict.
- **"Also add X" mid-build** → record their words under ask.md's `## Later, in your words`; it is
  authorized. Ask only about scope or cost beyond the approved budget.
- **Evidence contradicts the plan** → Convene's Rules, *Evidence changes the approach*.
