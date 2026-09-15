# Stage 1 — Convene

Decide whether to convene, whom, and at what cost — then get the user's go-ahead.

## Steps

1. **Open runs first.** `council run status`. An open run on this working tree → ask the user:
   resume it, close it, or run alongside it (`council run open <mode> --alongside`, then pass
   `--run <folder>` to every command). Never overwrite one; `council run open` refuses to without
   `--alongside`.
2. **No `council.config.md`?** Run council-init first. Never tailor a roster inline — it dies with
   the run. Otherwise `council fingerprint check`: if the stack moved since council-init, say so in
   the approval message and offer a refresh first — the roster and cards may be stale.
3. **Resolve the target.** Your mode's `## At Convene` says how: a diff, a plan, a question.
4. **Shape check** — from the map and file counts, without reading code:
   - Does the work split into independent slices, or is it one chain of dependent decisions?
   - Which seats have surface in it? Match the target's paths against each seat's Surface column in
     the config's roster.

   One chain → Solo, or one builder. Independent slices → seats.
5. **Size it.** Solo: you, inline. Squad: 2–4 seats + 1–2 verifiers. Full: up to 7 seats +
   verifiers. Count the verifiers Challenge will need — one for each P1 or protected item you
   expect, one for the rest — and keep seats + verifiers within the agent cap (config `agent cap`,
   default 10).
6. **Estimate from this project's history.** `council ledger` shows each seat's average tokens per
   run; `council run status --all` shows whole runs. With no history, assume ~60–100k tokens per
   worker.
7. **Open the run.** `council run open <mode>` prints the run folder and records this session's id,
   so a compaction resumes the right run. Record the size:
   `council state size="squad — 3 seats + 1 verifier, est. ~300k tokens"`.
8. **Get the go-ahead** with the message below — unless the user's `/command` already approved a
   run of this size (config `approve without asking`, default: up to Squad). A Full run always asks.

## The approval message

- What you'll deliver, and where it will be saved.
- Seats going: what each checks, in plain words with the name second, and its slice size.
- Seats not going, each with its reason: "Frontend (Dodds) — no UI files in this change".
- The estimated cost.
- What you'll ask at the end: rulings and memory proposals.

## Rules

- After the go-ahead, work to the deliverable without check-ins. Stop only for a destructive step,
  growth beyond the approved scope, or a ruling that belongs to the user.
- The user can say "stop — give me what you have" at any time; Collect handles a partial delivery.
- Record the go-ahead under `## Decisions so far` in session-state.md.

## Done when

The run is open and approved, and its size is recorded. → `council state phase=prepare`
