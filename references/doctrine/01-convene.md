# Stage 1 — Convene

Decide whether to convene, whom, and at what cost — then get the user's go-ahead.

**Whether, first.** A request that is fully specified in one short message, and that you could
finish in one turn without questions — a typo, a rename, a one-line fix, a single lookup — doesn't
need the council. Do it or answer it directly, say in one line why no run was opened, and open none;
the user can still ask for one. This never applies to a protected subject (authorization, data
loss, injection, secrets, concurrency or ordering, public contracts), or to a review or post-game,
which exist to add a second look.

## Steps

1. **Open runs first.** `council run status`. An open run on this working tree → ask the user:
   resume it, close it, or run alongside it (`council run open <mode> --alongside`, then pass
   `--run <folder>` to every command). Never overwrite one; `council run open` refuses to without
   `--alongside`.
2. **No `council.config.md`?** Run council-init first — a post-game is the exception: it needs no roster. Never tailor a roster inline — it dies with
   the run. Otherwise `council fingerprint check`: if the stack moved since council-init, or the
   config has no stack-fingerprint yet (an older layout), say so in the approval message and offer a
   refresh first — the roster, cards and gates may be stale.
3. **Resolve the target.** Your mode's `## At Convene` says how: a diff, a plan, a question.
4. **Shape check** — from the map and file counts, without reading code:
   - Does the work split into independent slices, or is it one chain of dependent decisions?
   - Which seats have surface in it? Match the target's paths against each seat's Surface column in
     the config's roster.

   One chain → Solo, or one builder. Independent slices → seats.
5. **Size it.** Start with `council route recommend --task "<short task>"`, adding explicit
   `--risk`, `--complexity`, `--uncertainty`, or `--surface` inputs only when the known evidence
   warrants them. Treat its routing and budget as a recommendation, not an authorization or a
   dispatch order. Compare it with the actual roster, surfaces, project history, and task risks;
   record any override and why in the run plan. `--classic` shows a fixed comparison policy;
   manual sizing remains available regardless of either recommendation. If the route says
   `needs-rescope`, resolve the budget or verification shortfall with the user before opening or
   dispatching a run; a lower-cost Solo label does not waive required independent challenge.
   Solo: you, inline. Squad: 2–4 seats + 1–2 verifiers. Full: up to 7 seats + verifiers. Count
   the verifiers Challenge will need — one for each P1 or protected item you expect, one for the
   rest — and keep their agent runs within the agent cap (config `agent cap`, default 10): a seat run
   as a Workflow counts every agent it starts.
6. **Estimate from this project's history.** `council ledger` shows each seat's average tokens per
   run; `council run status --all` shows whole runs. With no history, assume ~60–100k tokens per
   worker. The route budgets with the config's `estimate per worker` when the user set one through
   `council tune`; otherwise with 80k.
7. **Open the run.** `council run open <mode>` prints the run folder and records this session's id,
   so a compaction resumes the right run. It also creates `<run>/run-plan.tsv`: fill its run size,
   risk, complexity, uncertainty, token estimate and verification level from the decision you just
   made. Assign completes its seat rows. A Solo run or a mode that skips Assign completes every seat
   row here too (the inline Chair plus any expected verifiers), then runs `council run plan check`.
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
9. **Get the go-ahead** with the message below — unless the user's `/command` already approved a
   run of this size (config `approve without asking`, default: up to Squad). A Full run always asks.

## The approval message

- What you'll deliver, and where it will be saved.
- Seats going: what each checks, in plain words with the name second, and its slice size.
- Seats not going, each with its reason: "Frontend (Dodds) — no UI files in this change".
- The war room, when it's on (council-plan): why, and what it adds to the cost.
- The estimated cost.
- What you'll ask at the end: rulings and memory proposals.

## Rules

- After the go-ahead, work to the deliverable without check-ins. Stop only for a destructive step,
  growth beyond the approved scope, or a ruling that belongs to the user.
- The user can say "stop — give me what you have" at any time; Collect handles a partial delivery.
- Record the go-ahead under `## Decisions so far` in session-state.md.

## Done when

The run is open and approved, and its size is recorded. → `council state phase=prepare`
