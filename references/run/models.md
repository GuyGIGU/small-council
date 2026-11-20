# A model per role

Which model each role's agents run on (D37, as D42, D51, D74 and D78 amend it). The run plan check
enforces it (`references/run/run-plan.md`); council-init proposes it; the Chair passes it at dispatch.

## The line

```
- models: builder=<name>, review=<name>, verifier=<name>, map=<name>
```

In `council.config.md`'s `## Run preferences`. A name is `inherit` (the session's model), `fable`,
`opus`, `sonnet` or `haiku`: what the Agent tool's `model` parameter takes, never a versioned model id,
which goes stale. A role the line leaves out is `inherit`, and so is every role without the line, so
nothing changes until a project opts in. A word the helper can't read (an unknown role or model, a
role named twice) makes `council run plan check` refuse until the line is fixed; the refusal says
what to write.

| Role | Whose agents | Notes |
|---|---|---|
| `builder` | A build's builder agents (council-implement workers) | One per task, on its build seat `task-<n>`; in a Solo build the Chair builds instead, on the session's model (D42) |
| `review` | None since 1.3.0: a review's reader and runner run on the session's model, and its plan gives them no model row (D51) | Still read, so an older line stays valid |
| `verifier` | Every verifier seat, in every mode | Never weaker than the builder it checks |
| `map` | Setup's mapping workers on a large repository (`map-<area>`, council-init Phase D) | `inherit`, `sonnet` or `haiku` only: the session's model or a cheaper one (D78) |

The Chair stays on the session's model, and so do the reader, the runner, the designer and a
diagnosis worker: they are not roles of this line. An older config's `- seat models:` line is no
longer read (D74).

## A verifier never below its builder

The order is haiku < sonnet < opus < fable. The helper can't see the session's model, so `inherit`
is judged as the session's: a verifier on `inherit` passes against any builder, and a named verifier
below `fable` is refused against a builder on `inherit`. The Chair counts as a builder only in a Solo
build, which the helper reads as a run plan that selects no build seat: the Chair builds on the
session's model, so that build's verifier is `inherit` or `fable`. Otherwise a build's verifier is
judged against its builder agents' model. A review has no builder: its verifier may be cheaper than
the session's model.

## Proposing a split (council-init)

Propose from the model you are running on, in one line, and write it only on the user's yes:
- the builder on `inherit`;
- the verifier on `inherit`; `sonnet` only when the user wants cheaper checks (a Solo build's
  verifier row stays `inherit` or `fable` whatever the line says);
- `review=` stays `inherit`: no lower model for a review, whose reader and runner always run on the
  session's model (D51);
- `map=` only on a large repository, before the mapping workers start: `inherit`, or `sonnet` for a
  cheaper map (charting what is where needs less than judging it). The owner confirms it.

> Models: builder and verifier on your model (opus). Keep, or a cheaper verifier?

On "all inherit", write `- models: builder=inherit, review=inherit, verifier=inherit, map=inherit`.

## The size-and-cost line

When the line names any model other than `inherit`, the approval message's cost says which model
each role runs on: "~900k tokens: the builders on sonnet, the verifier on your model". Tokens are
counted, not priced: a token on haiku costs less than one on opus, and the helper never claims a
saving.

## Limits

- The plan check judges what the plan asks for, not what ran: the Agent call's `model` parameter
  isn't gated, and a force-subagent-model setting can override it.
- A closed run's role models are not rechecked against today's line.
