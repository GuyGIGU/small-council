# A model per role

Which model each role's agents run on (D37). The run plan check enforces it
(`references/run/run-plan.md`); council-init proposes it; the Chair passes it at dispatch
(`references/doctrine/05-work.md`).

## The line

```
- models: builder=<name>, review=<name>, verifier=<name>
```

In `council.config.md`'s `## Run preferences`. A name is `inherit` (the session's model), `fable`,
`opus`, `sonnet` or `haiku`: what the Agent tool's `model` parameter takes, never a versioned model id,
which goes stale. A role the line leaves out is `inherit`, and so is every role without the line, so
nothing changes until a project opts in. A word the helper can't read (an unknown role or model, a
role named twice) makes `council run plan check` refuse until the line is fixed; the refusal says
what to write.

| Role | Whose agents | Notes |
|---|---|---|
| `builder` | A build's builder agents (council-implement workers) | A build's builder today is the Chair, in its own window: the line names the model of builder agents a build dispatches (#63) |
| `review` | A review's seat workers (council-review) | Mapping and survey workers keep `- seat models:` |
| `verifier` | Every verifier seat, in every mode | Never weaker than the builder it checks |

The Chair stays on the session's model. Plan, research and post-game seats, diagnosis workers, and
mapping or survey workers are not roles of this line: they inherit, or take `- seat models:`'s
`sonnet` or `haiku` for a mapping or survey purpose, exactly as before.

## A verifier never below its builder

The order is haiku < sonnet < opus < fable. The helper can't see the session's model, so `inherit`
is judged as the session's: a verifier on `inherit` passes against any builder, and a named verifier
below `fable` is refused against a builder on `inherit`. In a build the Chair builds, on the
session's model, so a build's verifier is `inherit` or `fable`. A review has no builder: its verifier
may be cheaper than its seats.

## Proposing a split (council-init)

Propose from the model you are running on, in one line, and write it only on the user's yes:
- the review seats one step below your model, never below `sonnet` (`fable` → `opus`, `opus` →
  `sonnet`; on `sonnet` or `haiku`, `inherit`);
- the verifier on `inherit`; `sonnet` only when the user wants cheaper review checks (a build's
  verifier row stays `inherit` or `fable` whatever the line says);
- the builder on `inherit`.

> Models: review seats on sonnet, verifier and builder on your model (opus). Cheaper reviews; builds
> unchanged. Keep, change, or all inherit?

On "all inherit", write `- models: builder=inherit, review=inherit, verifier=inherit`.

## The size-and-cost line

When the line names any model other than `inherit`, the approval message's cost says which model
each role runs on: "~400k tokens: 3 review seats on sonnet, the verifier on your model". Tokens are
counted, not priced: a token on haiku costs less than one on opus, and the helper never claims a
saving.

## Limits

- The plan check judges what the plan asks for, not what ran: the Agent call's `model` parameter
  isn't gated, and a force-subagent-model setting can override it.
- `council history` groups tokens by each seat's planned model (`seat/<slug>/model`); for `inherit`
  it can't know which model ran.
- A closed run's role models are not rechecked against today's line.
