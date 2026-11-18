# Stage 5 — Work

The seats work in parallel, each in its own window. You dispatch, then wait.

## Dispatch

- **All worker Agent calls go in one message**, with `subagent_type: small-council:council-worker`.
  The worker contract lives in that agent. If the type is unavailable, use `general-purpose` and paste
  the rules from `${CLAUDE_PLUGIN_ROOT}/agents/council-worker.md`. Through the Workflow tool:
  `${CLAUDE_PLUGIN_ROOT}/references/run/workflow.md` first.
- A seat with a `seat/<slug>/model` row in the plan — a verifier's too, wherever it is dispatched —
  gets that value as the Agent call's `model` parameter; omit it for `inherit` or no row. Never put
  a seat on a model its plan row doesn't name: the plan check judges the plan, but the `model`
  parameter isn't gated, so this rule is yours. A force-subagent-model setting may override the
  plan; report that if known.
- **Never pass `name`** on a council Agent call — with agent teams switched on, a named call becomes
  a teammate instead of a worker.
- **Keep the dispatch short** — the brief carries everything:

```
Seat: <slug> — <what it checks> · <mode> run
Brief: <abs>/brief.md
Reference: <abs card or doc path(s)>
Doc: <abs path of the full doc behind each card>
Format: <your mode's per-item format>
Write <abs run>/seats/<slug>.md
```

- **Right after dispatching, two steps, in order:**
  1. **Record each worker:** `council seat <slug> running agent=<agentId>` — the id the Agent or
     Workflow tool returned, never a role name.
  2. **Show the user the run's status — at the run's first dispatch, once,** as the helper's
     reminder on that first record says. Later dispatches show nothing.

## While they work

- Wait for the completion notifications. Never poll, and never open a subagent's transcript or
  output log.
- **On each notification:** `council seat <slug> done tokens=<the figure, as given> tools=<tool_uses>`,
  or `failed note="…"` (with its tokens if it reported any). Once per finished agent run; a resumed
  worker's later figure is its running total, so record it as given. A Workflow's notification:
  `agents=<agent_count> tokens=<subagent_tokens>`. Seat work you did yourself:
  `council seat chair done agents=0`. It prints a progress line — relay it as one short
  line: "3 of 5 seats in — Security, Structure, Tests · ~210k tokens so far".
- **A refused write:** the worker replies with its file under `UNWRITTEN <path>`; save it verbatim,
  `note="saved by the Chair"` on its seat.
- **A turn limit, the agent cap or token ceiling, alerts, a worker that died with its session (it
  sends nothing):** context-core, Limits, Alerts and Resume.

## Done when

Every worker has reported, done or failed. → `council state phase=collect`
