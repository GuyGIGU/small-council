# Behavioral drills (run in Claude Code)

Run these by hand before releasing a change to the skills, agents, hooks or helper, and record pass or
fail with a note in the PR.
- Load the working copy with `claude --plugin-dir <repo>`, or the skills-directory install described
  in the README.
- Use a scratch project, never a real one.

## D1 — Roster fit (`council-init`)
**Setup:** a project with no `.council/` whose stack is NOT the canonical web default — a Python
service, a Go CLI, a game.

**Pass if:**
- it detects the real stack from an inventory, not just manifests;
- it recasts before dropping, and gives every seat surface markers in the repo's own idioms;
- it keeps Carmack as chair and Fowler and Beck always;
- it finds the real gate commands and **dry-runs each**, marking any it can't run and never probing
  one with side effects;
- it writes `.council/` (config with run preferences, memory, map, `.gitignore`) and the CLAUDE.md
  block only after confirmation.

**Fail if:** it assumes `tsc`/`vitest`/`cypress`, reports a gate runnable without running it, or
writes files before confirming.

## D2 — Triggering
**Pass if:**
- in a council-enabled project, "review this", finishing a change, or opening a PR makes the agent
  *propose* a council review with its size, seats (and seats not going), and cost;
- it doesn't fire on unrelated chat.

## D3 — Bug caught (fixture)
**Setup:** see `fixtures/README.md` — a copy of `fixtures/` as its own git repo.

**Pass if:** the empty-input bug in `average` comes back as a P1 or P2 that:
- is attributed to the right seat;
- carries origin, basis and "refuted if";
- gives a concrete fix and no code;
- was CONFIRMED by a verifier that saw only the claim and its location.

## D4 — Memory respected (fixture)
**Pass if:** `last_or_none` (Accepted Pattern AP-1) is not flagged.

## D5 — Right-sized runs
**Setup:** a one-file, ten-line change.

**Pass if:** the Chair recommends Solo or a small Squad, shows the seats not going with reasons, and
states the estimated cost. A `/council-review` of that size starts without a second question.

## D6 — Resume after compaction
**Setup:** start a Squad review, then run `/compact` while seats are running.

**Pass if:**
- the hook's "compacted during a council run" note names the mode's skill;
- the agent re-invokes that skill and reads `session-state.md`;
- it waits for the seats still running, and re-dispatches none that are running or done.

## D7 — Close-out
**Pass if:**
- after any run, `council run status` shows nothing open;
- the state says `status: complete` with an `actual:` cost;
- a new session shows no "unfinished run" warning.

## D8 — Proposals survive
**Pass if:**
- memory proposals appear as `- PROPOSED …` lines, with evidence and effect, *before* the user
  answers;
- a "no" moves the proposal to `## Rejected`;
- the next session's hook counts what's still pending.

## D9 — Fix loop
**Setup:** after D3, accept the fix hand-off.

**Pass if:**
- council-implement records a gate baseline;
- it captures before-evidence (the empty-input check fails) and after-evidence (it passes);
- it runs the gate by exit code, and a verifier returns OK citing the saved outputs;
- it appends the task to `.council/logs/…` immediately, runs the converge pass, then offers a review.

## D10 — Map reuse
**Setup:** a second council run in a project with a fresh `map.md`.

**Pass if:** the Chair orients from `map.md` and `council index`, and reads no more than ~10 skeleton
files before writing the brief.

## D11 — Linked worktree
**Setup:** run a council mode from a `git worktree` of a council-enabled repo.

**Pass if:** the run files land in the **main** checkout's `.council/runs/`, and the brief records the
worktree as the code root.

## D12 — Seat check
**Setup:** in a scratch run, dispatch a council-worker with a brief whose output path is unwritable,
or tell it to skip writing its file.

**Pass if:** the SubagentStop hook sends it back once with the reason, and a second stop passes, so
it never loops.

## D13 — Helper-driven bookkeeping
**Pass if**, in any Squad run:
- the Chair uses `council run open`, `state`, `seat`, `index`, `collect`, `check` and `run close`
  rather than hand-editing run files;
- the user sees a progress line as seats finish;
- the cost is reported at the end.

## D14 — Two runs at once
**Setup:** start a review in one worktree and a fix pass in another.

**Pass if:**
- both run to completion;
- `council run status` shows both while they're open;
- neither run's close touches the other.

## Context-hygiene spot checks (any real run)
- The Chair never deep-read implementation files — it used Glob/Grep, the index, and a bounded set of
  skeleton files.
- Each worker returned one line.
- Every seat file has `ref:` on line 2 and an `## Index`.
- `brief.md` is edge-ordered: the deliverable and question at the top, hard constraints at the bottom.
- `synthesis.md` exists before verification, and every shipped item has a verdict.
