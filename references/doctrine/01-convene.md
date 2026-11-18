# Stage 1 — Convene

Decide whether to convene, whom, and at what cost — then get the user's go-ahead.

**Whether, first.** A fully specified one-turn typo, rename, one-line fix or lookup needs no council:
handle it directly, say why, and open none; the user can still request one. Never for a
protected subject (context-core, Limits), or a review or post-game, which add a second look.

## Steps

1. **Open runs first.** `council run status`. Follow the user's instruction to resume, close or run
   alongside one; ask if unresolved. Alongside: `council run open <mode> --alongside`, then
   `--run <folder>` on every command. Never overwrite an open run. `<mode>` is always the skill's
   name, such as `council-review`.
2. **No `council.config.md`?** A **review** starts now on a quick setup,
   `council init scaffold --quick` (council-review, At Convene). A **post-game** needs no roster.
   **Plan, implement and research** run council-init first, on a `setup: quick` config too: they
   lean on the map and the probed checks. Never tailor a roster inline. Otherwise
   `council fingerprint check`: if the stack moved or there is no stack-fingerprint, say so and
   offer a refresh — the roster, cards and gates may be stale.
3. **Resolve the target.** Your mode's `## At Convene` says how: a diff, a plan, a question.
4. **Shape check** — from the map and file counts, without reading code. One dependent chain → Solo
   or one builder; independent slices → seats. Match paths against the roster's Surface column.
5. **Size it** from context-core's size limits and the shape check: the seats the roster's surfaces
   call, plus the verifiers Challenge will need (Challenge, step 2), counted within the agent cap as
   Assign, step 6 does. A lower-cost Solo label never waives a required independent challenge.
6. **Estimate the cost** yourself — no command does: agents × the config's figure, each worker and
   each Challenge verifier at its role's figure in `- estimates:`, else `- estimate per worker:`,
   else 80k. `council ledger` shows each seat's average tokens per run, `council run status --all`
   whole runs. A cost past the user's token ceiling, or a size past `approve without asking`, is
   the user's to decide before a run opens.
7. **Open the run and save the request.** `council run open <mode>` prints the run folder and
   records this session's id (a compaction resumes the right run). Right after it, before anything
   else, write `<run>/ask.md`:
   ```
   # Ask — <short title>
   source: said at the time | recalled after the work | from <PR, issue or spec@sha> | reconstructed from <…>
   continues: <.council/asks/<file>.md>          ← only when this run continues earlier work
   ## In your words
   <the user's message(s) that make up the request, exactly as typed — typos, code and links kept>
   ## Later, in your words
   - <date>: "<words that add to, drop or change what gets built>"
   ```
   "Yes" or "go" isn't a request. A hand-off (plan to build, review to fix …) continues the same
   request: `council state ask=<path>` from the input's "Your request" line, and `(no new words)`
   unless the user adds some; a new /command with new words starts a new one. **The request** is
   then the file `continues:` names plus ask.md's new words: read both. Pasted text (a PR, an issue)
   goes in as it is, headings and all.
8. **Fill the run plan.** `run open` also created `<run>/run-plan.tsv`: fill its run size, risk,
   complexity, uncertainty, token estimate (step 6), your own share of it as `chair-tokens`, and
   verification level. Assign completes seat rows; a mode skipping Assign completes them here, then runs
   `council run plan check`. The same size goes on the status board:
   `council state size="squad — 3 seats + 1 verifier, est. ~300k tokens"`.
9. **Get the go-ahead** if still needed. A `/command` or an instruction to proceed without further
   confirmation approves up to the config's `approve without asking` size (default Squad). Approval
   carries forward for the proposal's scope, size and budget. Full needs explicit size-and-cost
   approval. Never ask again for approval already given. Record their words as Done when shows.

## The approval message

- What you'll deliver, and where it is saved.
- Seats going: what each checks (context-core), and its slice size.
- Seats not going, each with its reason: "Frontend (Dodds) — no UI files in this change".
- The estimated cost, and each role's model when `- models:` names one (`references/run/models.md`).
- End-of-run rulings and memory proposals.

## Rules

- After the go-ahead, work to the deliverable without check-ins, within the boundaries below.
- The user can say "stop — give me what you have" at any time; Collect handles a partial delivery.
- **Changed instructions:** the user's current explicit words supersede stored preferences for
  this request; record them and propose a memory update, never silently rewrite settled entries. A
  vague "go ahead" never overrides a hard rule, authorizes commits, pushes or side-effectful gates,
  or approves a different outcome. Ask about any unresolved conflict or further permission.
- **Evidence changes the approach:** trace it first. A local correction can proceed within the
  approved scope, Done-when, public contracts and budget; log the evidence and verify affected tasks.
  A preference alone isn't enough. Changing an explicit user choice or hard rule, a destructive
  action, wider scope or a bigger budget needs a ruling first.

## Done when

The run is open and approved, and its size is recorded. → `council state decision="<their words>" phase=prepare`
