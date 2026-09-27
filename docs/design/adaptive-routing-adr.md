# ADR: advisory deterministic routing before dispatch

## Problem

Manual Solo/Squad/Full sizing can be inconsistent, yet fully automatic seat selection would make
project-specific judgment and cost hard to inspect. Phase 3 needs a routing foundation without
changing the run-plan contract or assuming that keyword heuristics are validated outcomes.

## Constraints

- Keep current commands, manual sizing, old runs and run-plan v1 working.
- Run without a model, service, database or new runtime dependency.
- Respect the configured agent cap and make budget assumptions visible.
- Preserve the Chair's responsibility for user approval, actual roster mapping and dispatch.

## Options

1. Keep sizing entirely manual. Smallest change, but no reproducible recommendation to compare.
2. Automatically fill run plans and dispatch seats. Faster in theory, but unsafe before impact and
   outcome signals are reliable, and would bypass project-specific roster decisions.
3. Emit a deterministic, read-only recommendation with reasons, then let the Chair adopt or override
   it in the checked plan.

## Decision

Choose option 3. `council route recommend` emits a versioned, five-column TSV recommendation. It
assesses risk, complexity and uncertainty; suggests size, generic seat archetypes, verification
and an estimated budget; and explains consequential choices. Explicit inputs can correct the
heuristic. A classic fixed policy remains available for comparison. The command does not mutate a
run, launch agents or claim to meter actual tokens. Convene reviews the advice before opening the
run; Assign maps archetypes to the real roster and writes the final run plan.

## Tradeoffs

The policy is inspectable and reversible, but coarse. Text and surface hints can miss hidden impact
or overstate it. A token estimate is not a provider-enforced spending limit. The result is a
planning aid, not proof of better quality or lower cost.

## Alternatives rejected

Automatic dispatch and historical self-tuning are deferred until impact signals, reliable outcome
metrics and benchmark comparisons exist. A new database or orchestration server would add more
mechanism than this foundation needs.

## Revisit when

Representative benchmark tasks and per-run outcome/cost measurements can show where this policy
helps or harms, or when a runtime can enforce actual agent and token budgets without misleading
the user. Preserve the policy version for comparison before changing its behavior.
