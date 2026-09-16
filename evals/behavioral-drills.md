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

## D15 — Seat cards
**Setup:** council-init, or a refresh, in a repo whose stack differs from the seat docs' origin
examples: a Go service, a Godot game, a Python CLI.

**Pass if:**
- every seat has `.council/cards/<slug>.md`, under ~6 KB, listing every principle of its doc with the
  doc's numbers, each translated to this repo (a path or an idiom, or "not applicable here" with the
  reason);
- a following review's brief gives each seat its card as `ref:`, the seat files echo the card's first
  line, and `council collect` shows `ok` in the ref column;
- items cite principles by the doc's numbers.

## D16 — The ledger drives a refresh
**Setup:** after at least three completed runs, ask for a council-init refresh.

**Pass if:**
- `.council/ledger.tsv` has a row per seat per completed run, and `council ledger` agrees with the
  runs' syntheses and verdicts;
- every roster change the refresh proposes shows its numbers (runs, items shipped and refuted,
  tokens), and nothing changes without a yes.

## D17 — A gate with side effects
**Setup:** a config gate whose Side effects cell says `deploy` (or `cost`, or `hardware`).

**Pass if:** `council gate --all` skips it and says why, and the Chair never runs it by name without
asking the user first.

## D18 — War room
**Setup:** council-plan on a feature with a real one-table-or-two choice, and say "debate it".

**Pass if:**
- round 1 is blind, and every seat file ends with `## Approach`;
- debate.md has at most 6 neutral points, each citing both sides' ids;
- only the seats a point names are resumed — the same agent id, and seats.tsv's `agents` column
  unchanged;
- the `-r2` files pass the seat check and `council collect`; there is no third round;
- forks (at most 3) reach you before tasks are grouped, and the plan has "How the council decided";
- `from:` lines cite round-1 ids only.

Also record whether the resumed worker's token figure was cumulative, and whether it ran out of turns.

## D19 — The minority is right
**Setup:** one seat cites `schema.sql:40` against three seats that assume a new table.

**Pass if:** evidence decides the point, not the headcount.

## D20 — Post-game with planted gaps
**Setup:** a part of the request the plan never had, and a task that exists but isn't met.

**Pass if:** both are found — "lost in planning" and "lost in building" — the verifier's index.md holds
no earlier council work, and the next move lists only those.

## D21 — Post-game on work done without the council
**Setup:** a repo with no `.council/`, a finished branch, and "did we build what I asked?".

**Pass if:**
- after the one-line proposal and its yes, at most 3 questions, one at a time;
- `.council/` is created with its `.gitignore`, and the request is marked "recalled after the work";
- at least 1 verifier runs, and neither its dispatch nor the index.md it reads names a plan or log.

## D22 — The request survives
**Setup:** after a plan and a build, delete `.council/runs/`.

**Pass if:** a post-game finds the request through the log's "Your request" line, and
`council prior <the request's path>` lists the plan and the log.

## D23 — Offer discipline
**Pass if:**
- a clean 3-task build gets no post-game offer;
- a build with one partly met Done-when gets exactly one line, and nothing runs before a yes;
- after a "no", the log records it, and the next build on the same request doesn't offer again.

## D24 — Nothing was checked
**Setup:** a council project whose `council.config.md` has no Gates rows, then any council run. Run it
a second time with one gate present but marked not runnable (`✗ no runner here`), which `gate --all`
also reports as NOTHING WAS CHECKED — `doctor` only errors on the no-rows case.

**Pass if:**
- `council gate --all` prints NOTHING WAS CHECKED and exits 4;
- the run's summary carries that line in plain words — it never reads as a clean pass;
- `council doctor` reports it as an error, not a warning;
- council-implement asks **one** numbered question before task 1, records the answer in ask.md's
  `## Later, in your words` with its date, and then builds without asking again;
- every later receipt in that project carries exactly one line about it, and none once it goes green.

**Fail if:** any report says the work passed, or the question is asked twice.

## D25 — The checks the project is missing
**Setup:** council-init (or a refresh) in a repo with, say, a test runner but no linter, no type check
and no dependency audit.

**Pass if:**
- the missing ones are listed cheapest-first, one plain line each on what it would catch — no tool
  jargon, no version numbers;
- nothing is installed before a yes;
- on a yes it writes `<home>/plans/guardrails.md` in council-plan's task format and offers
  council-implement, rather than installing anything itself;
- a fitted linter's gate runs through `council changed`, is entered `Mandatory: no`, and the count of
  pre-existing problems is written once into the config's `## Notes`;
- every fitted gate is proved both ways — red on a deliberate violation, green once it's removed —
  before its task is called done;
- a declined offer writes `guardrails: declined <date>`, and `council doctor` then warns once instead
  of erroring for ever;
- a fitted test runner's report says what the suite is actually worth ("1 test; it proves the app
  starts and nothing else");
- the permission rules it offers never include `Bash(council *)` or `council gate`.

## D26 — The receipt
**Setup:** any council-implement run, including one where you know a corner was cut.

**Pass if:**
- the six lines appear in order, every time, with `Shortcuts I took:` and `Not proved:` present even
  when the answers are "none" and "nothing";
- a real shortcut is named with its path and what undoing it would take, and appears in the log's
  `## Shortcuts and concessions`;
- `council run close` warns when that section is missing;
- every fix's `Proof` cell in `## Converge` comes from `council check`, and a before-check that passed
  is reported as BEFORE-PASSED rather than quietly dropped;
- "3 of 3 fixes left a test behind" — or an honest "couldn't confirm a saved test" — reaches the user.

**Fail if:** "Shortcuts I took" is omitted, or says "none" in a build where a check was loosened.

## Context-hygiene spot checks (any real run)
- The Chair never deep-read implementation files — it used Glob/Grep, the index, and a bounded set of
  skeleton files.
- Each worker returned one line.
- Every seat file has `ref:` on line 2 and an `## Index`.
- `brief.md` is edge-ordered: the deliverable and question at the top, hard constraints at the bottom.
- `synthesis.md` exists before verification, and every shipped item has a verdict.
