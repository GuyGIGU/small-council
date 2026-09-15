# Behavioral drills (run in Claude Code)

Run these by hand before releasing a change to the skills, agents, or hook. Record pass/fail and a note
in the PR. Load the working copy with `claude --plugin-dir <repo>` (or the skills-directory install
described in the README), and use a scratch project — never a real one.

## D1 — Roster fit (`council-init`)
**Setup:** a project with no `.council/`, whose stack is NOT the canonical web default — a Python
service, a Go CLI, a game.
**Pass if:** it detects the real stack and surfaces; recasts before dropping (a persistent store →
data integrity; a compute engine → numerical correctness); drops only seats with truly no surface;
keeps Carmack as chair and Fowler/Beck always; finds the real gate commands and **dry-runs each**,
marking any it can't run; writes `.council/` (config, memory, map, `.gitignore`) and the CLAUDE.md
block only after confirmation.
**Fail if:** it assumes `tsc`/`vitest`/`cypress`, reports a gate as runnable without running it, or
writes files before confirming.

## D2 — Triggering
**Pass if:** in a council-enabled project, "review this" / finishing a change / opening a PR makes the
agent *propose* a council review with its size and cost — and it doesn't fire on unrelated chat.
**Fail if:** it never proposes, dispatches without a go-ahead, or proposes during idle conversation.

## D3 — Bug caught (fixture)
**Setup:** see `fixtures/README.md` — a copy of `fixtures/` as its own git repo.
**Pass if:** the empty-input bug in `average` is a P1 or P2, attributed to the right seat, with a
concrete fix, no code, CONFIRMED by the verifier.
**Fail if:** missed, code in the review, or shipped without a verdict.

## D4 — Memory respected (fixture)
**Pass if:** `last_or_none` (Accepted Pattern AP-1) is not flagged.
**Fail if:** it's flagged as a finding.

## D5 — Right-sized runs
**Setup:** a one-file, ten-line change.
**Pass if:** the Chair recommends Solo or a small Squad (not Full) and states the estimated cost.

## D6 — Resume after compaction
**Setup:** start a Squad review; run `/compact` while seats are dispatched.
**Pass if:** the hook's "compacted during a council run" note appears; the agent re-invokes
context-core, reads `session-state.md`, and resumes without re-dispatching seats whose files exist.

## D7 — Close-out
**Pass if:** after any run, `session-state.md` says `status: complete`, `.council/active-run` is empty,
and a new session shows no "unfinished run" warning.

## D8 — Proposals survive
**Pass if:** memory proposals appear as `- PROPOSED …` lines in the memory file *before* the user
answers, and a new session's hook reports how many are pending.

## D9 — Fix loop
**Setup:** after D3, accept the fix hand-off.
**Pass if:** council-implement fixes the P1, runs the gate by exit code, dispatches the verifier on
the fix (OK), and appends the task to `.council/logs/…` immediately — then offers a review.

## D10 — Map reuse
**Setup:** a second council run in a project with a fresh `map.md`.
**Pass if:** the Chair orients from `map.md` and reads no more than ~10 skeleton files before writing
the brief.

## D11 — Linked worktree
**Setup:** run a council mode from a `git worktree` of a council-enabled repo.
**Pass if:** the run files land in the **main** checkout's `.council/runs/`, and the brief records the
worktree as the code root.

## Context-hygiene spot checks (any real run)
- The Chair never deep-read implementation files (Glob/Grep plus a bounded set of skeleton files).
- Each worker returned one line; every seat file's line 2 is `ref: <its doc's title>`.
- `brief.md` is edge-ordered: deliverable and question at the top, hard constraints at the bottom.
- `session-state.md` stayed under ~40 lines; history went to `log.md`.
