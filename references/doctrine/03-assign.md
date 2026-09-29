# Stage 3 — Assign

Give each seat exactly its slice, and each worker a budget.

## Steps

1. **Match surfaces.** Use the Convene routing recommendation as a starting point, then map its
   archetypes to the project's actual roster; a recommendation is never a substitute for the
   project's Surface markers. For each roster seat, match its Surface markers (the config's roster
   column: globs and greps in this repo's idioms) against the in-scope files from the index or the scope
   inventory. The match is the seat's slice. A config without markers yet → judge by the seat's
   lens, and suggest a council-init refresh. A lens with several roster rows (`dodds-web`,
   `dodds-admin`) is several seats, each with its own surface. If `impact.tsv` exists, consider its
   direct importers and likely tests as additional scope, but inspect them before assigning an
   owner; low-confidence name/path hints are not proof of behavior.
2. **No orphans.** Every in-scope file belongs to at least one seat; an unowned file is a coverage
   gap. That includes the files the index names past the 80-file cap (listed at its end, with no
   hunks): they are in scope, just not indexed. Leftovers go to the closest lens — structure takes
   what nobody else claims.
3. **Thin seats pair up.** A seat with an empty slice is not called, with its reason recorded. A seat
   with a thin slice (one or two files) shares one worker with a neighbour — UI with UX, backend with
   data — rather than getting its own agent.
4. **Big slices split.** Over ~25 files → two workers (`hunt-a`, `hunt-b`), each with half.
5. **Budgets from slice size:** ~15 tool calls for up to 5 files, ~30 for up to 15, ~45 for up to 25.
6. **Count agents.** Workers + the verifiers Challenge will need must fit the agent cap (default
   10). Count agent runs, not seats: a seat you will run as a Workflow counts every agent it starts —
   give it `budget/<slug>/agent-runs` in the plan. Give each of its agents a group of small,
   same-kind parts (files, tasks, items), never one small part each. Over → pair more seats, or ask
   the user. A re-dispatch or a diagnosis worker counts too; a resumed worker (SendMessage to its
   agent id) doesn't.
7. **Finish the run plan.** In `<run>/run-plan.tsv`, give every considered seat a `disposition`
   (`selected` or `skipped`) and `role`, with the reason. Every selected seat gets a context level;
   every selected seat gets a tool-call budget. Include the Chair as a selected
   `chair` for Solo. Copy the recommendation's compatible risk, complexity band, uncertainty,
   cap, and verification level only after checking them against what Prepare uncovered. If a
   recommendation changed, record the evidence and reason in the plan. Run
   `council run plan check`; fix every error before going on.
   If `- seat models: on` is set in `council.config.md`, a selected mapping or survey worker may get
   `seat/<slug>/purpose = mapping` or `survey` and `seat/<slug>/model = sonnet` or `haiku`;
   otherwise omit the model row (`inherit`). Keep the Chair and
   verifier at `inherit`. A model choice is a request for dispatch, not proof of which model ran.
8. **Record it.** `council seat <slug> queued` for every worker; `council seat <slug> skipped
   note="<reason>"` for every seat not called. The helper refuses to queue or start a seat the valid
   plan does not mark selected.

## Rules

- Mechanical first, judgment second: start from the marker match and adjust only for a reason you
  can state in one line.
- When in doubt, keep the seat. Seats dropped for "zero surface" have gone on to produce a quarter of
  a review's findings once recast.

## Done when

Every in-scope file has an owner, every worker has a slice and a budget, and `council run plan check`
is clean. → `council state phase=brief` (the helper refuses this transition while the plan is invalid)
