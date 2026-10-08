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

The only agents you dispatch are verifiers, plus at most one diagnosis worker per stuck task across
gate and verifier failures.

**Carmack's filter:** the smallest change satisfying the task, proved by machine.

**Respect the project's hard rules** (the config, `CLAUDE.md`/`AGENTS.md`). Never take a destructive
shortcut — dropping data, force-pushing, disabling a gate — to make a task pass.

## Three kinds of input

- **A plan:** `<home>/plans/<slug>.md` (legacy: `PLAN-<slug>.md` at the project root). Each task has
  Domain, Ref, Depends on, Touches and Done when.
- **A review (fix mode):** `<home>/reviews/<date>-<slug>.md` (legacy: a `FINAL-REVIEW.md` in an old
  run folder). Each selected finding becomes a task:
  - its seat's reference doc governs it;
  - its Fix line is the ask;
  - "done" means the consequence can no longer happen.

  Default: introduced or touched P1/P2s, including unknown origin. Use the user's existing selection.
- **A post-game:** `<home>/postgames/<date>-<slug>.md`. Each of its Next tasks is a task, in the plan's
  format; its Done-when quotes the user's request.

## At Convene

1. **Read what drives the build.**
   - The input, in full.
   - `council.config.md`: gates, hard rules, and the roster → reference map.
   - Memory: check accepted patterns, enforced conventions and decisions against the task using
     Convene's changed-instructions rule; do not silently retire or rewrite settled entries.
   - `map.md`.
2. **Order the tasks.** Dependencies first. In fix mode: P1 before P2, then group by file.
3. **Safety net.** If it isn't a git repo, recommend `git init` plus a first commit. If the user
   declines, copy each file to `<run>/backup/<path>` before its first change. If uncommitted work
   exists, note it and never discard it.
4. **Carry forward approval, or confirm once:**
   - the task list and order;
   - how the verifier will run, and its cost;
   - *"One commit per task on <branch>, so each task can be reverted?"* Recommended. Never commit on
     the default branch without a yes, and never push unless asked.

   Use Convene's approval rule; state the order and proceed when this build is authorized.
   Without commit authorization, do not commit. The baseline question below still applies once,
   before task 1; a red mandatory gate you cannot fix stops the affected task.
5. **Open the run.** `council run open council-implement`. Continue the input's request: its "Your
   request" line gives the path → `council state ask=<path>`, and ask.md gets `continues: <path>` plus
   this run's new words, or `(no new words)`. An input from before 0.6 has no such line: start a new
   request from the user's words now, or restate the plan's Scope line, confirmed by the user
   (`source: restated from <plan>`). Then write the log header at
   `<home>/logs/<YYYY-MM-DD>-<slug>.md`.

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
   contract: change for a fix or new behaviour, preserve only for unchanged behaviour. Record the
   chosen mode and invariants in the log, then run `council gate before-<n>` as it specifies.
   Label support with `references/evidence-model.md`; cite saved outputs for `REPRODUCED`.
3. **Plan the change:** files, minimal diff, governing principle, effects on later tasks and watchpoints.
4. **Implement.**
   - Match existing patterns.
   - Build what the task says and nothing more — no "while we're here".
   - Honour memory.
   - *The function least likely to cause a problem is the one that doesn't exist.*
5. **Gates for what you touched:** `council gate <name>`, judged by exit code.
   - **Never run a gate whose side effects involve cost, hardware, deploys or credentials** without
     asking the user first (`council gates` lists them).
   - **Your change broke it** → fix it before moving on.
   - **A mandatory gate is red that was green at baseline** → hard stop until you understand why.
   - **Red at baseline and waved through** → carry on: check only that your change added no new
     failure — `council gate <name>` names the tests failing now that `gates/baseline/<name>.txt`
     didn't name. When it can't compare, read both outputs side by side before calling it
     unchanged. Keep the standing clause on the receipt.
   - **It can't run** → that's config drift: log it and tell the user.
   - **It fails during this task** → use the bounded loop in `references/repair-loop.md`:
     `council gate` records it (no `council repair record`), inspect its advisory
     category, saved output and baseline, then repair and rerun the **same** gate. The first failure
     stays with the builder; the second calls for one independent read-only diagnosis if this task
     has not used that worker already; otherwise stop and report. The third failed execution stops
     product-code mutation for this task, and the gate is refused until the user's go
     (`council repair allow <gate> --user-said "…"`). Jump to blocked-task logging and the receipt;
     do not attempt steps 6–7 as a fix path, start another gate trail, or commit it as complete.
     Preserve the diff and gate output; never silently revert unrelated work. Read-only review
     cannot reopen repair. When the build stops blocked, run `council status --line`; if it prints
     a line, send it once with a `PushNotification` tool (deferred? search the tools first).
     Without Python 3.8+, log the same attempts and limit. Never count the intentionally failing
     `before-<n>` check as a repair attempt.
6. **After-evidence — only if the task is not blocked.** Run the same check again,
   `council gate after-<n> -- '<same command>'`, keeping `--proof preserve` if selected before editing.
   It must pass under the build-proof contract.
7. **Adversarial check — only if the task is not blocked.** Dispatch `small-council:council-verifier` with:
   - the task and its Done-when;
   - the proof mode and, for preservation, the invariants and their test paths;
   - the governing principle's own text, quoted from the reference doc, so it is checked, not cited;
   - the diff, written to `<run>/diff-<n>.patch`, passed by path;
   - the before, after and gate outputs in `gates/`.

   Verify every P1 fix and every risky task (data writes, security, core logic) on its own; batch
   small tasks two or three per verifier, or up to five of one kind (renames, copy edits). Track each
   with `council seat verify-<n> …`; one stopped at its turn limit is resumed with SendMessage
   ("write your file now"), never re-dispatched. Then act on the verdict:
   - **INCOMPLETE or REGRESSION** → fix it and re-verify. The re-check writes `verify-<n>b.md` (then
     `c`), so the first verdict stays on disk.
   - **A second failed verification** → a **clean-context diagnosis** if this task has not already
     used its one diagnosis worker for a gate failure; otherwise stop and report. The worker is read-only.
     Its dispatch message is its whole brief — the task and its Done-when, both verdict files, the
     diff's path, `ref: none` — and it writes `<run>/seats/diagnose-<n>.md`, an index of root-cause
     candidates (`<n> · likely|possible · root cause · <path:line> · <title>`). Plan it
     (`council run plan check`), then `council seat diagnose-<n> …`. Then one more attempt; still
     failing → stop and report.
   - **SCOPE-CREEP** → revert the extra change.
   - **CANNOT VERIFY** → add the missing check, or record why it can't exist.
   - **A finding that turns out to be wrong** → don't "fix" it; log it as refuted, with evidence.
8. **Log and state — now, not at the end.**
   - Append the task's entry to the log.
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
met, with evidence — written into the log's `## Converge` table.
- Anything not met → one more task, or a logged follow-up.
- Then run the final gates: `council gate --all --at verify`. Exit 4 means nothing was checked — say
  so; never report it as a pass.
- If this run has `repairs.jsonl`, run `council repair check`; a broken saved repair trail is
  reported, never folded into a green receipt. Without Python, audit the log's attempts and
  saved gate outputs by hand.
- Then `council check`. It checks the saved before/after gates against their declared proof mode
  (`references/build-proof.md`) and names the saved test when it can. Copy each verdict and its
  full note into the `## Converge` table's **Proof** column: `ok` shows a change, `preserved` shows
  the checked invariants held on both versions. Broken proof is fixed or reported; no proof is
  reported as NO PROOF. Passing invariants alone never establish new behaviour.

## At Deliver — the receipt

The same seven lines after every build, in this order, whatever happened. The shape never changes, so
after three builds the user reads it at a glance and notices the moment a line does:

```
Built: <fully verified n> of <total n> tasks — <what you can do now that you couldn't before, or "no verified result"> [· <n> partly met or blocked: <one clause each>]
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
as such; never imply that it includes the Chair or the whole session when those figures are not
available. **Never omit the last four.** "none" and "nothing" are answers; silence isn't. A shortcut is one of
these — not a vibe: a hardcoded value, a skipped case, a swallowed error, a loosened or disabled
check, a test that asserts less than the behaviour, a TODO left behind, or a fix whose only proof was
a throwaway command. Every one also goes in the log's `## Shortcuts and concessions`.

One carve-out: a **guardrails task** — fitting a formatter, linter, type check, audit or test runner —
proves itself by the gate going red on a deliberate violation and green once it's removed, exactly as
`${CLAUDE_PLUGIN_ROOT}/references/guardrails.md` requires. That is evidence, not a shortcut, and it
doesn't belong on the shortcut line.

Then the numbered rulings and memory proposals, as always.

**No commit, push or PR question while anything is left open.** First offer each `Left open:` item as
*fix now* or *later* — a data-loss hazard defaults to fix now — and wait: "later" is the user's ruling,
never yours. Ask the commit, push or PR question last and on its own, once the last verifier (a
post-game's too) is back — never in the same message as a fix question.

File the request (`council ask save`). Then **offer a post-game when the log shows one is worthwhile**
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

- **The plan names code that no longer exists** → follow the intent, not the literal path, and log it.
- **Blocked by something outside the input** (a key, a service, an env var) → do what you can, log the
  blocker, and carry on with the unblocked tasks.
- **Two tasks share one change** → implement the shared change once; retain each task's Done-when,
  evidence and verdict so neither disappears from the receipt.
- **"Also add X" mid-build** → record the user's words under ask.md's `## Later, in your words` and
  update the task list. Their instruction authorizes the addition; ask only about unresolved scope,
  dependencies or cost beyond the approved budget before doing dependent work.
- **Evidence contradicts the plan's approach** → apply Convene's changed-instructions rule. Log the
  contradiction, corrected approach and affected tasks, then re-verify every affected Done-when.
