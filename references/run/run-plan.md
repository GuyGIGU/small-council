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
- optional `budget/run/chair-tokens`, the Chair's own share of `estimated-tokens` (its reading and
  judging, which no seat records); agents' tokens are compared with the rest, never with the whole
- optional `budget/run/token-ceiling`, a positive whole-token limit the owner gave; copy it from
  `route recommend --budget-tokens` when that flag was used
- `verification/run/level` (`self`, `independent`, or `adversarial`)

Every considered seat has `seat/<slug>/disposition` (`selected` or `skipped`) and
`seat/<slug>/role` (`chair`, `worker`, `verifier`, or `diagnosis` — a read-only worker on a stuck
build task, counted as a worker's agent run). Every selected seat has a context level
(`minimal`, `focused`, or `full`) and a positive tool-call budget. The selected Chair is budgeted but
does not count as an agent. Skipped seats receive neither context nor budget.

The cap counts agent runs, not seats: a seat run as a Workflow starts one agent per part, so it
declares `budget/<slug>/agent-runs` (1 to 1000; 1 when absent). The selected workers' and verifiers'
agent runs must fit both the plan's agent cap and the project's configured cap — or, after the
user's go past the cap (`council cap allow`), the count their go allows. During the run the helper
counts the larger of the agent runs recorded and the agent starts the hook let through
(`references/run/run-accounting.md`): once they reach the
cap, `council seat` tells the Chair to ask the user before starting more; the first time they pass
it, it records `run.cap_passed` and the status card says so. From the cap on, a hook refuses the next
agent until the user's go is recorded with `council cap allow` (`references/run/run-accounting.md`).

An optional `seat/<slug>/model` row is `inherit`, `sonnet`, or `haiku`. Missing means `inherit`.
Overrides require `- seat models: on` in `council.config.md`, and only selected worker seats may use
`sonnet` or `haiku`; keep the Chair and verifier on `inherit`. A worker requesting an override must
also declare `seat/<slug>/purpose = mapping` or `survey`. `other` cannot receive an override.
A `mapping` seat charts an area of the code for `map.md` (what is where, how it connects); a `survey`
seat gathers facts, files or candidates for others to judge; `other` is anything that judges,
advises or builds. The checker verifies this declared purpose; the Chair must ensure the dispatched
task actually fits it. These rules are checked in the run plan only: the Agent call's `model`
parameter isn't gated, so the Chair keeps to the plan. A closed run (complete or abandoned) is not rechecked against today's `seat models` setting.

Exactly one Chair must be selected. Solo selects no delegated agents; Squad selects at least one,
and Full selects at least four. An open run's Full plan also needs the user's explicit size-and-cost
go on record: a decision since the run opened (`council state decision="…"`); a closed run's plan is
read as it was. Independent or adversarial verification requires a selected
`verifier`; a plan marked `self` cannot also select one. The Chair receives a context level but
does not count as an agent. A plan that cannot fit its required verifier or run size must be
resized or given a higher cap before Brief or dispatch.

## Lifecycle

`council run open` instantiates the template and binds its run id, mode, and configured agent cap.
The remaining placeholders make the starter deliberately invalid. Convene fills the run-level
decisions; Assign records all considered seats and runs `council run plan check`.

A `council-init` run is the exception. Setup follows its own phases and is the Chair's own work, so it
opens from `references/templates/run-plan-init.tsv`, already valid: solo, the Chair only, self-verified, each
default saying so in its reason. A large repo's mapping squad makes it a squad, one mapping worker
per area (council-init Phase D).

The helper refuses to enter Brief, Build, or a later standard stage while the plan is invalid. It also
refuses to queue or start a worker not marked selected. `council run plan show` renders the checked
contract in plain language for briefing and review. `council doctor` checks the plans of open runs
too; an incomplete plan is expected during Convene, Prepare, or Assign and is a warning there, but
invalid after that is an error. A closed run's plan is the record of what was decided then: doctor
never judges it by today's settings, and nobody rewrites it after the fact.

When routing changes, edit the plan, state the reason, and check it again before acting on the new
decision. The file is the current contract, not an event history; `log.md` remains the history.

## Plan tasks

A council-plan run's tasks are its deliverable, not this file, but the same check judges them: once
`council state deliverable=<path>` names the plan, `council run plan check` also reads every task under
its `## Task Sequence` (`### <n>. <title>` and its table), prints a `tasks:` line, and refuses the next
stage while a task breaks a rule below. Beside `Depends on` and `Done when`, every task has three rows:

| Row | What it holds | Refused when |
|---|---|---|
| **Serves** | the part of the request it serves, in quotes, word for word from ask.md's `## In your words` (and the filed request it continues). A support task (a test, a changelog line) quotes the part its parent serves | the row is missing, quotes nothing, quotes under three words, or quotes words the request never said |
| **Owner** | the module or folder, and the job it extends: a row of `map.md`'s `## One way per job` table, named by its job. Or `New way: <why no existing way fits>`, which goes to the user as a ruling (Deliver, step 6) and, once they rule, into memory as a decision. A probe or research task says `Probe: <the question>` or `Research: <the question>` | the row is missing, `New way:` gives no why, or the map has the table and the row names none of its jobs |
| **Rests on** | the facts the task takes as given, split by `;`, each ending with its evidence state (`references/run/evidence-model.md`) and `outside` when it is about something outside the repo: `the provider retries for 3 days (ASSUMED, outside); orders are keyed by id (OBSERVED)`. `—` when it rests on nothing | the row is missing, or a fact has no state |

**An unknown becomes its own task.** A task resting on an `ASSUMED` or `INFERRED` fact marked `outside`
(a tool, a platform, an API) depends on a probe or research task, directly or through other tasks, so
the fact is measured or read before anything is built on it. A probe or research task needs none itself.

A map with no `## One way per job` table, or one with no rows yet, skips the owner check and says so in
one line, so older projects keep working. A closed run's plan is read as it was, and another mode's
deliverable is not a plan.

## Compatibility

New runs carry `plan-schema: 1` in `session-state.md`. A stamped run whose plan is missing is an
error. Runs created by older versions have neither the stamp nor the file and remain valid legacy
runs: no migration is required, and all existing commands continue to work on them.
