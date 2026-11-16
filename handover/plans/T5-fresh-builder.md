# Plan: T5, a fresh builder per task

Written 2026-11-16, after T3 (PR #116, open). Design: `docs/design/task-tree.md` section 6 and the T5
row of "Where it lands". The design is the user's; this plan only says how to build it. Build nothing
from it until T3 has merged: T5 needs the pack.

## What it does, and why

Today the Chair writes the code of every build in its own window (D4). So the checks on a builder are
the Chair checking itself, the Chair's window grows with every task, and a build's verifier can never be
on a cheaper model than the session (D37 counts the Chair as the builder). T5 hands each task to a
builder agent in a clean window, one at a time. The agent gets the pack (`council context build
task-<n>`) plus the Chair's note on where to start, does the before gate, the change, the gates, the
report and `council patch save`, and returns one line: done, `NEEDS: <question>`, `NEEDS: fix …`, or
blocked at the third failed gate. The Chair reads that line and `council patch show <n>`, not the diff.
A Solo-size build stays with the Chair.

Added to the scope by the night plan:
- **A revert check.** Undo the round's patch in a scratch copy (`git apply -R` on
  `patches/T<n>-<r>.patch`), rerun the after gate there, and expect it to fail. A test that still
  passes with the fix undone proves nothing. Nothing does this today: `council check` compares recorded
  gates only (`check_proofs.status`), and build-proof.md says the helper cannot.
- **Receipt lines written by the helper.** "Checked by machine" and "Not proved" are composed by the
  Chair today, from the skill's prose. The helper writes them from the gate records (`gates/*.json`:
  gate, command, exit, seconds, proof, tree, seat, invalid), so the builder cannot claim a check it did
  not run.
- **The verifier asks "exists, not a stub, wired in".** It is not asked today. It goes into
  build-proof.md, Checking, with a one-line pointer in the verifier. The verifier has 4 characters left,
  so a sentence moves out first.
- **The benchmark both ways.** `evals/bench.py` has two fixed arms (with and without the plugin). It
  needs a third tag, the Chair building against a builder agent, scored by tokens by role, hidden
  checks passed and false completion claims. It has never been run for a result.

## Files, and the tasks split by file ownership

| Task | Owner | Files |
|---|---|---|
| A. The builder's contract | Opus builder | new `agents/council-builder.md` (with edit tools, its one-line return), `hooks/hooks.json` (SubagentStop matcher), `hooks/seat-gate.sh` and `hooks/agent-gate.sh` allow-lists (as written, with D20 fault paths), `src/council/commands/agent_gate.py` `KINDS`, `evals/run_hook.py` |
| B. The build seat's refusals | Opus builder | `src/council/commands/seat*.py`, `rounds.py` or a new `build_seat.py`: `council seat build-<n> running` refused while another build seat runs, refused for a task resting on one stopped by `NEEDS: fix` until a `council state decision=` is on record (D7), and naming any file changed since the last saved round's tree (`patches.Round.tree` against `git.files_tree`). `seat … done` for a build seat needs its `report-<n>.md`. `evals/run_cli.py` scenarios |
| C. Revert check and receipt lines | Opus builder | `src/council/commands/check*.py` (`check_proofs`), `gate_exec`, a new receipt printer reading `records/gates`, `references/build-proof.md`, `evals/run_cli.py` |
| D. The loop moved and the prose | Opus builder | `skills/council-implement/SKILL.md` (lines 91-158, the loop; steps 2-6 at 97-126 are the builder's), new `references/run/builder-loop.md`, `agents/council-verifier.md` (pointer only), `references/run/models.md`, `references/run/repair-loop.md`, `evals/run_structural.py` pins re-homed |
| E. Benchmark arm | Opus builder | `evals/bench.py` and its self-test; no model calls in CI |
| Planner | me | `docs/architecture.md` (§3 agents row, §6 new names, §8 rows), `docs/design/task-tree.md`, CHANGELOG, `src/council/commands/plan_models.py` stays until the D37 question is answered |

The seat slug must be settled first. The design says `build-<n>`, but `tasks.number` and
`council tree` match only `3`, `T3` and `task-3`, so a `build-3` note would land under "unclaimed".
Either `tasks.number` learns `build-<n>` (one shared parser), or the seat is `task-<n>`.

## What proves it

- A scenario for every new refusal (D25), each naming the next step (D19). Hook scenarios with the
  fault path (D20).
- The revert check on a fixture where the test passes without the fix (refused) and where it fails
  (passes).
- The fast tier, ruff, the ratchet ("ShellCheck measured"), the touched run_cli groups, timing last and
  alone, and CI on all three OS.
- Then the benchmark run both ways on the same cases. This is a paid run: about $12-25 for a pilot, and
  $50-90 for 10 or more pairs. It is the owner's go, not part of the build.

## What could go wrong

- **D37 goes stale.** `plan_models.verifiers()` adds the Chair as a builder in every build, as D37 and
  `references/run/models.md` say. With a builder agent that is wrong, but changing it touches a decision.
- **The size limits.** The implement skill has 122 characters of room and the verifier 4. The loop
  must move out before anything is added.
- **The seat gate expects a worker's return.** It greps `Wrote <path>.md`, which a builder's one-line
  return does not have. Its contract needs a second form, and the hooks stay bash (D22).
- **Gates that write files.** A gate that leaves unignored files would look like an edit outside a
  round. The tree check must ignore gate output paths, or name them as such.
- **"Adds no agents".** The design's "What this does not do" says the tree adds no agents, and T5
  adds one. State it in the PR.
- **Tokens may not fall.** Each builder reads its code again. The gain is the Chair's window and the
  cheaper models, so the estimate is measured again from the ledger before the default changes.

## Rough cost

About 1.2-1.6M tokens, mostly Opus: five builders at 200-300k each, a Sonnet map (done, about 264k,
in the scratchpad), and the planner's checks. The benchmark run is extra and paid.

## The entry proposed for `docs/decisions.md` (for the owner's word; not written)

| D41 | One builder at a time edits project code: a builder agent (`small-council:council-builder`) per task in council-implement, or the Chair itself for a Solo build. Agents still read and write only their own seat or verify file, except the builder, which writes the project code of its one task and its `report-<n>.md`. This supersedes D4's last clause ("and only council-implement's Chair edits project code"). | the user, <date> | `council seat` (one build seat running at a time); `seat-gate.sh`; agent contracts | supersedes D4 (last clause) |

D37 needs a matching change: "in a build the Chair, which builds, counts as a builder" holds only for a
Solo build. Whether that is an amendment in D41 or its own entry is the owner's call.
