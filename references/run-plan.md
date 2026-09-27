# Run plan contract v1

`run-plan.tsv` is the small, machine-checked decision contract for a council run. It records the
choices that used to live only in the Chair's prose before any context is distributed or worker is
started. It is run-local and ignored by git with the rest of `.council/runs/`.

`council route recommend --task "<summary>"` can suggest those decisions before a run opens. Its
output is advisory and never writes this file or dispatches seats. The Chair maps suggested seat
archetypes to the project's actual roster and records the final choices and their reasons here.
The route's numeric complexity input is converted to a `low`, `medium`, or `high` band for this v1
contract; do not put the numeric score in `assessment/run/complexity`.

## Shape

The file has exactly five tab-separated columns:

```
kind    id    field    value    reason
```

Blank lines and lines beginning with `#` are ignored. Every data cell is required. A
`kind/id/field` identity may occur only once, and v1 rejects unknown kinds and fields so misspelled
decisions cannot silently disappear.

The required run rows are:

- `schema/plan/version = 1`
- `run/run/id`, `mode`, and `size` (`solo`, `squad`, or `full`)
- `assessment/run/risk`, `complexity`, and `uncertainty` (`low`, `medium`, or `high`)
- `budget/run/agent-cap` and `estimated-tokens`
- `verification/run/level` (`self`, `independent`, or `adversarial`)

Every considered seat has `seat/<slug>/disposition` (`selected` or `skipped`) and
`seat/<slug>/role` (`chair`, `worker`, or `verifier`). Every selected seat has a context level
(`minimal`, `focused`, or `full`) and a positive tool-call budget. The selected Chair is budgeted but
does not count as an agent. Skipped seats receive neither context nor budget. The selected workers and verifiers must
fit both the plan's agent cap and the project's configured cap.

Exactly one Chair must be selected. Solo selects no delegated agents; Squad selects at least one,
and Full selects at least four. Independent or adversarial verification requires a selected
`verifier`; a plan marked `self` cannot also select one. The Chair receives a context level but
does not count as an agent. A plan that cannot fit its required verifier or run size must be
resized or given a higher cap before Brief or dispatch.

## Lifecycle

`council run open` instantiates the template and binds its run id, mode, and configured agent cap.
The remaining placeholders make the starter deliberately invalid. Convene fills the run-level
decisions; Assign records all considered seats and runs `council run plan check`.

The helper refuses to enter Brief, Build, or a later standard stage while the plan is invalid. It also
refuses to queue or start a worker not marked selected. `council run plan show` renders the checked
contract in plain language for briefing and review. `council doctor` checks plans too; an incomplete
plan is expected during Convene, Prepare, or Assign and is a warning there, but invalid after that
is an error.

When routing changes, edit the plan, state the reason, and check it again before acting on the new
decision. The file is the current contract, not an event history; `log.md` remains the history.

## Compatibility

New runs carry `plan-schema: 1` in `session-state.md`. A stamped run whose plan is missing is an
error. Runs created by older versions have neither the stamp nor the file and remain valid legacy
runs: no migration is required, and all existing commands continue to work on them.
