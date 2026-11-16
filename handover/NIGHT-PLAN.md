# The night's work, after the clean-behaviours PR

Read `handover/HANDOVER.md` first and finish that step. Start nothing below until its PR has MERGED
(CI green on Ubuntu, Windows and macOS). If CI fails, fix it by its cause. If two honest tries do not
make it green, stop the whole night here and write what you found in the PR.

Then, in this order:

1. **Build T3**, reshaped as below. Its PR is opened and left OPEN: no auto-merge. The owner reads it
   in the morning, and a real council run is due before it merges.
2. **Write plans, build nothing**, for T5, issue 62, issue 55 and the other held issues.
3. Stop and report.

## 1. T3 (branch `claude/t3-task-pack`, cut from `origin/main` after the merge)

The design is `docs/design/task-tree.md` on main: sections 2 and 4 (with "A bug underneath stops the
branch"), the T3 row of "Where it lands", and "Decided by the user" points 4 and 5. T1 and T2 are built.
Read the design before anything else. It is approved; do not re-decide it. Where it is silent on
something that would be a new contract name (a command, flag, file name, column, state field, event) or
would touch a decision in `docs/decisions.md`, do not guess: leave that part out and list it in the PR.

What T3 builds:

- **The generated task pack:** `council context build task-<n>` writes a builder's orders from files, in
  the six-part order of section 2 (with the standing builder rules of issue 57, the user's rulings so far
  of issue 61, and doctrine by surface for seats of issue 67). It also carries the task's `Rests on`
  facts and the owner rows of the code it calls. It is the only context provider, written new, in
  `src/council/`, on the records owners (D32).
- **`council tree`:** prints the tree from `ask.md`, the plan and the run's task state.
- **Setup (`council-init`):** reads the project's decision records and architecture docs, proposes each
  decision as a memory entry citing its source, for the user to accept; fills the map's
  one-way-per-job table (job, owner, the one way, an anchor path). A map without the table still skips
  the owner check.
- **The `NEEDS: fix` stop:** the builder's return line, the Chair's rule for it (stop that task and
  those that rest on it, tell the user in one line, the fix starts only on the user's yes), the
  verifier's question on every round, and the two more signs in the helper's list.

The reshape (the owner has seen it and left the call to the planner; the open PR is where they can
still say no, so state these three points at the top of the PR):

- **A hard size ceiling on the pack.** The seat packs cut on 2026-11-15 made briefs 151 to 214 percent
  bigger and were never measured. The pack has one byte ceiling, held in one place: start at 8,000
  bytes. When the parts do not fit, the pack drops whole parts from the end of the order, never cuts
  one mid-way, and names each dropped part under "left out". A scenario proves the ceiling holds and
  that a dropped part is named.
- **Measure it.** In the PR, give the pack's size on the eval fixture plan beside the size of the
  hand-written builder brief the implement skill asks for today, and say whether 8,000 is the right
  number. The owner settles the number.
- **`council tree` stays thin:** a print and nothing more. No new file, no new state, no flags beyond
  what the design names.

Rules (all of `handover/maps/builder-rules.md` binds, except its Windows traps and its "no push"):

- Start with one read-only map on Sonnet: for each part above, the owner today (architecture §3, §8),
  the files it will touch, and the skill and reference files whose text changes, with their sizes
  against the limits in `CLAUDE.md`. Then builders on Opus, split by file ownership so no two write
  the same file, model named explicitly. Check each builder's report against its diff before the PR.
- Skills are at most 20,000 characters and 500 lines; the verifier contract 8,000 characters; a review
  run's method load 59,407 bytes (D13). New rules go into the reference a skill points at.
- Every new command and refusal has a scenario in `evals/run_cli.py` or `evals/run_hook.py` (D25). A
  refusal names the next step (D19).
- Do not edit `docs/decisions.md`. A CHANGELOG line per visible change, under `## [Unreleased]`.
  `docs/architecture.md` gains the new command and owner rows; `docs/design/task-tree.md` gains the
  ceiling in section 2.
- The planted drill cases (T4) are NOT part of this: they land with S10.
- Proof before the PR: the same list as step 6 of `handover/HANDOVER.md`.
- The PR: what was built against the design, part by part; what was left out and why; lines added and
  removed; the pack measurement; proof counts; tokens by model. No auto-merge.

Rough cost: 1M tokens, up to 2M, mostly Opus. If the builders pass 2M, stop and report.

## 2. Plans only (one file each under `handover/plans/` on `claude/clean-handover`, pushed)

Read-only work, on Sonnet where it is a map. Each plan is one page in plain words: what it does and
why, the files it touches, the tasks split by file ownership, what proves it, what could go wrong, and a
rough token cost. Build nothing and open no PR for these.

- **T5, a fresh builder per task** (design section 6 and its row). It supersedes D4's last clause, so
  the plan ends with the exact entry proposed for `docs/decisions.md`, for the owner's word. Add to its
  scope: a revert check (undo the fix in a scratch copy, rerun the test, expect it to fail); receipt
  lines ("checked by machine", "not proved") written by the helper from the gate records, not by the
  builder; the verifier asking "exists, not a stub, wired in"; and running the benchmark both ways.
- **Issue 62** (the map refreshed at close) and **issue 55** (a memory size budget and tidy): moved up,
  because a pack drawn from a stale map or an overgrown memory is worse than a hand-written brief.
- **The other held issues** (47, the rest of 59 and 60, 57, 61, 67, the setup side of 93): for each, one
  paragraph: done by T3, still worth doing (with a cost), or drop, and why. Read each with `gh issue view`.

## 3. Report

One message at the end: what merged; the T3 PR's link and what it leaves out; where the plans are;
tokens by model for each part against the rough costs above; every question for the owner in one list.
