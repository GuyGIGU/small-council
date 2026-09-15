# Stage 3 — Assign

Give each seat exactly its slice, and each worker a budget.

## Steps

1. **Match surfaces.** For each roster seat, match its Surface markers (the config's roster column:
   globs and greps in this repo's idioms) against the in-scope files from the index or the scope
   inventory. The match is the seat's slice. A config without markers yet → judge by the seat's
   lens, and suggest a council-init refresh.
2. **No orphans.** Every in-scope file belongs to at least one seat; an unowned file is a coverage
   gap. Leftovers go to the closest lens — structure takes what nobody else claims.
3. **Thin seats pair up.** A seat with an empty slice is not called, with its reason recorded. A seat
   with a thin slice (one or two files) shares one worker with a neighbour — UI with UX, backend with
   data — rather than getting its own agent.
4. **Big slices split.** Over ~25 files → two workers (`hunt-a`, `hunt-b`), each with half.
5. **Budgets from slice size:** ~15 tool calls for up to 5 files, ~30 for up to 15, ~45 for up to 25.
6. **Count agents.** Workers + the verifiers Challenge will need must fit the agent cap (default
   10). Over → pair more seats, or ask the user. A re-dispatch or a diagnosis worker counts too.
7. **Record it.** `council seat <slug> queued` for every worker; `council seat <slug> skipped
   note="<reason>"` for every seat not called.

## Rules

- Mechanical first, judgment second: start from the marker match and adjust only for a reason you
  can state in one line.
- When in doubt, keep the seat. Seats dropped for "zero surface" have gone on to produce a quarter of
  a review's findings once recast.

## Done when

Every in-scope file has an owner and every worker has a slice and a budget. → `council state phase=brief`
