# T5: the prompt for the session that builds it

Paste everything below the line into a fresh Claude Code session opened in the `small-council` repo.

---

Build step T5 of the Small Council task tree: a fresh builder agent per task. Open the PR when it is
proved, and leave it open with no auto-merge. I read it before it merges.

## Read first, in this order

1. `CLAUDE.md`, then `docs/architecture.md` §3, §6 and §8, then `docs/decisions.md`.
2. `docs/design/task-tree.md` §6 ("A fresh builder per task") and the T5 row of "Where it lands". The
   design is approved: do not re-decide it.
3. Run `git fetch origin claude/clean-handover`. Then read these with `git show
   origin/claude/clean-handover:<path>`:
   - `handover/plans/T5-fresh-builder.md`, the plan. It binds, with the owner's answers already in it.
   - `handover/maps/t5-facts.md`, a read-only facts map, file:line cited. It was written before #116
     and #117 merged, so check every line you rely on.
   - `handover/maps/builder-rules.md`, the rules builders work under. Its Windows traps section applies
     if this machine is Windows.

## Settled; do not re-open

- **Seat slug:** the build seat is `task-<n>`, which `records.tasks.number` and `council tree` already
  match. Change the design's `build-<n>` to `task-<n>` in this branch.
- **Decision entry:** D42, worded as in the plan (it supersedes D4's last clause, and D37's clause "in a
  build the Chair, which builds, counts as a builder" becomes "in a Solo build …"). I approved it on
  2026-11-16, so write it into `docs/decisions.md` in this branch. It goes in D4's table (Method),
  at its end, because the file says a superseding entry goes in the same table. Mark D4's and D37's
  rows as the file's header says for a superseded entry, naming only the clause D42 replaces.
- **Scope:** everything the plan lists:
  - the builder's contract;
  - the build seat's refusals: one at a time, not past a `NEEDS: fix` stop without my recorded
    decision, and naming files changed outside a round;
  - the seat gate covering the builder;
  - the loop moved out of the implement skill into a reference;
  - the revert check;
  - helper-written receipt lines ("Checked by machine", "Not proved") from the gate records;
  - the verifier's "exists, not a stub, wired in" question;
  - a benchmark arm for Chair-builds against builder-builds, with no model calls in CI.
- **Rest of #59 and #60:** `council patch apply|revert` shares the revert check's reverse-apply. Each
  round's history line names the gate that went red. The pack links the task's own `patches/T<n>.md`
  for a fix round.
- **The benchmark run:** NOT part of this branch. It is a pilot (about $12-25) after this merges, and
  only on my go.

## How to work

- **Branch:** `claude/t5-fresh-builder` from the latest `origin/main`. Never work on main.
- **Who does what:**
  - You plan, decide and check.
  - Start with one read-only map on Sonnet if the facts map has gone stale.
  - Then use builders on Opus, with the model passed explicitly. Split them by file ownership, so no two
    write the same file: the plan's tasks A-E. A builder that needs another's file hands its text
    over, and that file's owner pastes it.
  - Check every builder's report against its diff before you rely on it.
- **Rules that bind:**
  - Behaviour that stays, stays byte for byte. Only the stated differences may show, each with a
    scenario in `evals/run_cli.py` or `evals/run_hook.py` and a CHANGELOG line under `## [Unreleased]`.
  - D19: a refusal names the next step.
  - D20: a hook lets the call through on its own fault and never writes stdout.
  - D22: bash 3.2, no jq.
  - Contract names (architecture §6) are frozen. A new agent name, seat-slug rule or receipt line
    becomes one the day it ships, so list each in §6.
  - One way per job. A helper needs a second caller or must name one idea.
  - Functions are at most 60 lines and modules at most 500 in `src/council/`. Never join lines to fit.
  - Reads go through `src/council/records/` (D32).
  - Skills are at most 20,000 characters and 500 lines. Count characters, not bytes: the implement
    skill has about 122 left. The verifier is at most 8,000 (it has 4 left), and a doctrine file at
    most 6,000. A review run's method load is at most 59,407 bytes. Move text out before adding any.
  - A fix names its cause. If you find a fault in code you build on, stop that item and tell me; do
    not work around it.
  - Don't edit `CLAUDE.md` or `CONTRIBUTING.md`; list what you would change. `docs/decisions.md` gets
    D42 only.
- **Testing:**
  - Never run `evals/run_all.py` without `--fast`.
  - Run the `timing` group of `run_cli.py` last and alone.
  - Never pipe a `council …` command into head, tail or grep (a hook refuses it): redirect to a file.
  - Never use the repo's own `.council/`. Try commands in a scratch git repo outside this one.
  - Don't edit tracked files while a suite runs.
- **On Linux:** `pip install ruff shellcheck-py`, and the ratchet must print "ShellCheck measured".

## Proof before the PR

```
python scripts/quick_validate.py
python evals/run_all.py --fast
python -m ruff check .
python evals/run_ratchet.py --update && python evals/run_ratchet.py   # commit the update last, on its own
python evals/run_cli.py --group <each group touched>                  # timing last and alone
python evals/run_hook.py --group main
python evals/run_audit.py; python evals/run_memory.py; python evals/run_status.py
```

Then one real build in a scratch project, before the PR goes up:
- Use this branch's helper (`bin/council` on PATH, `CLAUDE_PLUGIN_ROOT` set to the checkout).
- Run two dependent tasks, each built by a dispatched builder agent with a verifier at converge.
- Try one `NEEDS: fix` stop, and one Chair edit outside a round, which the next build seat should name.
- Report what worked and what didn't. Run this from the main session, not a subagent: a subagent cannot
  dispatch agents.

## The PR

- Its top states the D42 change, and where the design moved (`build-<n>` → `task-<n>`, "adds no
  agents" → one builder agent).
- Then, part by part, what was built against §6.
- What was left out and why.
- Lines added and removed.
- The proof counts.
- The real build's findings.
- Tokens by model.
- Every question for me, in one list.
- No auto-merge.

Rough cost: 1.2-1.6M tokens, mostly Opus. If the builders pass 2M, stop and tell me.
