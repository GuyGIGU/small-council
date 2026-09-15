---
name: council-implement
description: Build a Small Council plan task by task, fix the findings of a council review, or finish a post-game's next tasks — one builder, the governing expert's reference doc loaded per task, before-and-after evidence, the project's real gates after every change, a blind verifier on each result, a converge pass at the end, and a running log that feeds the next review. Use when the user says implement or build the plan, "fix these findings", "council implement", or invokes /council-implement.
---

# Council Implement (mode)

One builder, one task at a time, in this window. Parallel agents read; one hand writes code.
**Invoke `context-core`**, then run:
1. stages 1–2 with this file's sections;
2. **the build loop below**, in place of stages 3–7;
3. then stages 8–10.

The only agents you dispatch are verifiers, plus at most one diagnosis worker per stuck task.

**Voice of the build:** Carmack. Make the smallest change that satisfies the task; write code that
looks like the same team wrote it; no speculative generality; verify by machine, not by feel.

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

  Default selection: every P1 and P2 the change introduced. Confirm it, or let the user pick.
- **A post-game:** `<home>/postgames/<date>-<slug>.md`. Each of its Next tasks is a task, in the plan's
  format; its Done-when quotes the user's request.

## At Convene

1. **Read what drives the build.**
   - The input, in full.
   - `council.config.md`: gates, hard rules, and the roster → reference map.
   - Memory: never build against an accepted pattern, enforced convention or decision. If a task
     conflicts with one, follow memory and log it.
   - `map.md`.
2. **Order the tasks.** Dependencies first. In fix mode: P1 before P2, then group by file.
3. **Safety net.** If it isn't a git repo, recommend `git init` plus a first commit. If the user
   declines, copy each file to `<run>/backup/<path>` before its first change. If uncommitted work
   exists, note it and never discard it.
4. **Confirm once:**
   - the task list and order;
   - how the verifier will run, and its cost;
   - *"One commit per task on <branch>, so each task can be reverted?"* Recommended. Never commit on
     the default branch without a yes, and never push unless asked.

   Approval means autonomy to the end. Stop only for:
   - a red mandatory gate you can't fix;
   - a destructive step;
   - a ruling that belongs to the user;
   - growth beyond the input.
5. **Open the run.** `council run open council-implement`. Continue the input's request: its "Your
   request" line gives the path → `council state ask=<path>`, and ask.md gets `continues: <path>` plus
   this run's new words, or `(no new words)`. An input from before 0.6 has no such line: start a new
   request from the user's words now, or restate the plan's Scope line, confirmed by the user
   (`source: restated from <plan>`). Then write the log header at
   `<home>/logs/<YYYY-MM-DD>-<slug>.md`.

## At Prepare — the baseline

Run every gate once on the untouched code: `council gate --all`. It skips gates marked not runnable
and gates with cost, hardware, deploy or credential side effects; record those as not run. Record what already fails before you
touch anything, e.g. `council state baseline="tests: exit 1 (3 failing) · lint: pass"`. A
pre-existing failure is never blamed on a task.

## The build loop — for each task

1. **Load the governing reference doc first.**
   - `references/<file>.md` → `${CLAUDE_PLUGIN_ROOT}/references/<file>.md`.
   - Project-local `.council/refs/…` → under the council home.
   - It is the constraint set, not background reading. Cross-referenced docs inform specific decisions.
2. **Before-evidence.** Write or name one check that shows the problem (fix mode) or the missing
   behaviour (plan task): a test, a command or a query. Run it with
   `council gate before-<n> -- '<command>'` — quote the whole command, so `&&`, pipes and quotes stay
   inside it. It should fail or show the gap.
3. **Plan the change:**
   - which files;
   - the minimal diff;
   - which principle constrains it;
   - what it changes for later tasks;
   - which watchpoints apply.
4. **Implement.**
   - Match existing patterns.
   - Build what the task says and nothing more — no "while we're here".
   - Honour memory.
   - *The function least likely to cause a problem is the one that doesn't exist.*
5. **Gates for what you touched:** `council gate <name>`, judged by exit code.
   - **Never run a gate whose side effects involve cost, hardware, deploys or credentials** without
     asking the user first; `council gates` lists each gate's side effects.
   - **Your change broke it** → fix it before moving on.
   - **A mandatory gate is red** → hard stop until you understand why.
   - **It can't run** → that's config drift: log it and tell the user.
6. **After-evidence.** Run the same check again, `council gate after-<n> -- '<same command>'`. It
   must now pass.
7. **Adversarial check.** Dispatch `small-council:council-verifier` with:
   - the task and its Done-when;
   - the diff, written to `<run>/diff-<n>.patch`, passed by path;
   - the before, after and gate outputs in `gates/`.

   Verify every P1 fix and every risky task (data writes, security, core logic) on its own; batch
   small tasks two or three per verifier. Track each with `council seat verify-<n> …`. Then act on
   the verdict:
   - **INCOMPLETE or REGRESSION** → fix it and re-verify. The re-check writes `verify-<n>b.md` (then
     `c`), so the first verdict stays on disk.
   - **A second failed verification** → a **clean-context diagnosis**: one council-worker, read-only.
     Its dispatch message is its whole brief — the task and its Done-when, both verdict files, the
     diff's path, `ref: none` — and it writes `<run>/seats/diagnose-<n>.md`, an index of root-cause
     candidates (`<n> · likely|possible · root cause · <path:line> · <title>`). Track it with
     `council seat diagnose-<n> …`. Then one more attempt; still failing → stop and report.
   - **SCOPE-CREEP** → revert the extra change.
   - **CANNOT VERIFY** → add the missing check, or record why it can't exist.
   - **A finding that turns out to be wrong** → don't "fix" it. Log it as refuted, with evidence; it's
     a memory candidate.
8. **Log and state — now, not at the end.**
   - Append the task's entry to the log.
   - Update the state: `council state next="task <n+1>: <title>" attempts="T<n> 1/3"`. Keep a short
     "tried and failed" list there too.
   - If commits are on, commit the task.

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
Evidence: before <check> → failed as expected · after → passes
Gates: ✅ tests ✅ lint ✅ build   (or ❌ + what happened)
Verifier: OK   (or: fixed after INCOMPLETE — <what>)
Notes: <judgment calls, watchpoints hit, conventions followed — omit if none>
```

It closes with these sections:
- **Watchpoints addressed**
- **Pre-existing issues** (fixed or left)
- **Follow-ups**
- **`## Converge`:** `| Task | Done when | Result | Evidence |`, written by the converge pass
- **Ready for review:** every file created or modified, which is the next review's target.

Its last line records the post-game offer: `Post-game: offered <date> — yes | no`, or
`Post-game: not offered`.

Plain English: what changed and why, never pasted code.

## At Challenge — converge

After the last task, one council-verifier checks every task's Done-when against the final tree. In
fix mode, it checks every selected finding's consequence instead. Each gets met, partly met or not
met, with evidence — written into the log's `## Converge` table.
- Anything not met → one more task, or a logged follow-up.
- Then run the final gates: `council gate --all --at verify`.

## At Deliver

In chat:
- tasks done, N of N;
- the gates, baseline vs final;
- the verifier and converge results;
- anything blocked;
- the cost and the log path.

File the request (`council ask save`). Then **offer a post-game when the log shows one is worthwhile**
— at least one of:
1. converge found a Done-when partly met or not met, or the log has a follow-up;
2. the build hit trouble: a blocked task, a clean-context diagnosis, a SCOPE-CREEP revert, or a
   mandatory gate red at the end that was green at baseline;
3. the build left the plan: plan-named code that no longer exists, "the plan's approach looks wrong",
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
- **Two tasks would be cleaner merged** → keep them separate for attribution. Shared code goes in the
  first task and is reused by the second.
- **"Also add X" mid-build** → put the user's words under ask.md's `## Later, in your words`, and stop
  for a go-ahead: it's growth beyond the input.
- **The plan's approach looks wrong** → build it as written and log the concern; the review decides.
  Exception: it would break a hard rule or lose data → stop and ask.
