# Stage 1 — Convene

Decide whether to convene, whom, and at what cost — then get the user's go-ahead.

**Whether, first.** A fully specified one-turn typo, rename, one-line fix or lookup needs no council:
handle it directly, say why, and open none; the user can still request one. This never applies
to a protected subject (authorization, data loss, injection, secrets, concurrency or ordering,
public contracts), or to a review or post-game, which add a second look.

## Steps

1. **Open runs first.** `council run status`. Follow the user's instruction to resume, close or run
   alongside one; ask if unresolved. Alongside uses `council run open <mode> --alongside`, then
   `--run <folder>` on every command. Never overwrite an open run.
2. **No `council.config.md`?** Run council-init first; a post-game needs no roster. Never tailor a
   roster inline. Otherwise `council fingerprint check`: if the stack moved or there is
   no stack-fingerprint, say so and offer a refresh — the roster, cards and gates may be stale.
3. **Resolve the target.** Your mode's `## At Convene` says how: a diff, a plan, a question.
4. **Shape check** — from the map and file counts, without reading code. One dependent chain → Solo
   or one builder; independent slices → seats. Match paths against the roster's Surface column.
5. **Size it.** Start with `council route recommend --task "<short task>"`, adding explicit
   `--risk`, `--complexity`, `--uncertainty`, or `--surface` inputs only when the known evidence
   warrants them. Routing and budget are advice, not authorization. Compare with the roster,
   surfaces, project history and risks;
   record any override and why in the run plan. `--classic` shows the static policy. If the route says
   `needs-rescope`, resolve the budget or verification shortfall with the user before opening or
   dispatching a run; a lower-cost Solo label does not waive required independent challenge.
   Use context-core's size limits. Count Challenge's verifiers — one per expected P1 or protected
   item, one for the rest — within the config's agent cap (default 10). A Workflow counts every
   agent it starts.
6. **Estimate from this project's history.** `council ledger` shows each seat's average tokens per
   run; `council run status --all` shows whole runs. With no history, assume ~60–100k tokens per
   worker. The route budgets with the config's `estimate per worker` (set by `council tune`), else 80k.
7. **Open the run.** `council run open <mode>` prints the run folder and records this session's id,
   so a compaction resumes the right run. It also creates `<run>/run-plan.tsv`: fill its run size,
   risk, complexity, uncertainty, token estimate, the route's `chair-tokens` and verification level
   from your decision. Assign completes seat rows; modes skipping Assign complete them here, then
   run `council run plan check`.
   Record the same size on the status board:
   `council state size="squad — 3 seats + 1 verifier, est. ~300k tokens"`.
8. **Save the request** — right after opening the run, before anything else. Write `<run>/ask.md`:
   ```
   # Ask — <short title>
   source: said at the time | recalled after the work | from <PR, issue or spec@sha> | reconstructed from <…>
   continues: <.council/asks/<file>.md>          ← only when this run continues earlier work
   ## In your words
   <the user's message(s) that make up the request, exactly as typed — typos, code and links kept>
   ## Later, in your words
   - <date>: "<words that add to, drop or change what gets built>"
   ```
   "Yes" or "go" isn't a request. A hand-off — plan to build, review to fix, a build or post-game to
   review, post-game to build or plan — continues the same request: `council state ask=<path>` from the
   input's "Your request" line, and `(no new words)` unless the user adds some. A new /command with new
   words starts a new one. **The request** is then the file `continues:` names plus ask.md's new words:
   read both. Pasted text — a PR, an issue — goes in as it is, headings and all.
9. **Get the go-ahead** if still needed. A `/command` or an instruction to proceed without further
   confirmation approves up to the config's `approve without asking` size (default Squad). Approval
   carries forward for the proposal's scope, size and budget. Full needs explicit size-and-cost
   approval. Never ask again for approval already given; record the user's authorizing words.

## The approval message

- What you'll deliver, and where it will be saved.
- Seats going: what each checks, in plain words with the name second, and its slice size.
- Seats not going, each with its reason: "Frontend (Dodds) — no UI files in this change".
- The war room, when it's on (council-plan): why, and what it adds to the cost.
- The estimated cost.
- End-of-run rulings and memory proposals.

## Rules

- After the go-ahead, work to the deliverable without check-ins, within the boundaries below.
- The user can say "stop — give me what you have" at any time; Collect handles a partial delivery.
- Record the go-ahead: `council state decision="<their words>"`.
- **Changed instructions:** current explicit user words supersede stored preferences for this
  request; record them and propose a memory update, never silently rewrite settled entries. A
  vague "go ahead" does not override a hard rule, authorize commits, pushes or side-effectful gates,
  or approve a different outcome. Ask for any unresolved conflict or additional permission.
- **Evidence changes the approach:** trace it first. A local correction can proceed within the
  approved scope, Done-when, public contracts and budget; log the evidence and verify affected tasks.
  A preference alone is insufficient. Changing an explicit user choice or hard rule, taking a
  destructive action, expanding scope or exceeding budget needs a ruling first.

## Done when

The run is open and approved, and its size is recorded. → `council state phase=prepare`
