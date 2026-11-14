# Stage 5 — Work

The seats work in parallel, each in its own window. You dispatch, then wait.

## Dispatch

- **All worker Agent calls go in one message**, with `subagent_type: small-council:council-worker`.
  The worker contract lives in that agent. If the type is unavailable, use `general-purpose` and paste
  the rules from `${CLAUDE_PLUGIN_ROOT}/agents/council-worker.md`.
- For a selected seat with a `seat/<slug>/model` row — a mapping or survey worker under `- seat
  models: on`, or a builder, review or verifier seat under `- models:` — pass that value as the
  Agent call's per-invocation `model` parameter; a verifier's too, wherever it is dispatched. Omit
  that parameter for `inherit` or when the plan has no model row. If dispatching through Workflow,
  pass the same value to its `agent()` call. Never put a seat on a model its plan row doesn't name:
  the run plan check judges the plan, but the `model` parameter isn't gated, so this rule is yours.
  A configured force-subagent-model environment setting may override the plan; report that if known.
- **Never pass `name`** on a council Agent call — with agent teams switched on, a named call becomes
  a teammate instead of a worker.
- **Keep the dispatch short** — the brief carries everything:

```
Seat: <slug> — <what it checks> · <mode> run
Brief: <abs>/brief.md
Context: <abs>/contexts/<slug>.md — if built, read it for selected evidence; the brief remains authoritative
Reference: <abs card or doc path(s)>
Doc: <abs path of the full doc behind each card>
Format: <your mode's per-item format>
Write <abs run>/seats/<slug>.md
```

- **A context pack supplements the orders.** Include the `Context:` line only if that seat's pack
  was built successfully for the current brief and code state. A failed rebuild can leave an old
  pack on disk; existence alone does not establish freshness. Do not imply that omitted paths are
  safe.

- The agent gate refuses a council agent with no open run or plan row.

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
  `council seat chair done agents=0`. It prints a progress line — relay it to the user as one short
  line: "3 of 5 seats in — Security, Structure, Tests · ~210k tokens so far".
- **A worker stopped at its turn limit:** context-core, Limits. `council seat … done` refuses
  without its file and names the resume.
- **A refused write:** the worker replies with its file under `UNWRITTEN <path>`; save it verbatim,
  `note="saved by the Chair"` on its seat.
- **The agent cap and the token ceiling:** when `council seat` says the run reached either,
  context-core, Limits (Agents).
- **Alerts:** context-core, Alerts.
- **A worker that died with its session sends nothing:** context-core, Resume.
- **Whatever dispatches the workers** (Agent tool, Workflow, background agents), the file contract
  holds: one file per seat in `seats/`. The seat-check hook covers only
  `council-worker` and `council-verifier` agents, never a Workflow's (their type is
  `workflow-subagent`), so give a Workflow's agents the worker's file rules in their prompt;
  `council collect` then checks every file in `seats/`, named in the brief or not.

## Done when

Every worker has reported, done or failed. → `council state phase=collect`
