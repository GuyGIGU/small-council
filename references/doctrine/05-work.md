# Stage 5 — Work

The seats work in parallel, each in its own window. You dispatch, then wait.

## Dispatch

- **All worker Agent calls go in one message**, with `subagent_type: small-council:council-worker`.
  The worker contract lives in that agent. If the type is unavailable, use `general-purpose` and paste
  the rules from `${CLAUDE_PLUGIN_ROOT}/agents/council-worker.md`.
- For a selected worker seat planned as mapping or survey, pass its `seat/<slug>/model` value as the
  Agent call's per-invocation `model` parameter when `- seat models: on` is configured. Omit that
  parameter for `inherit` or when the plan has no model row. If dispatching through Workflow,
  pass the same value to its `agent()` call. Never override the Chair or verifier: the run plan
  check refuses it, but dispatch itself isn't gated, so this rule is yours to keep.
  A configured force-subagent-model environment setting may override the plan; report that if known.
- **Never pass `name`** on a council Agent call — with agent teams switched on, a named call becomes
  a teammate instead of a worker.
- **Keep the dispatch short** — the brief carries everything:

```
Seat: <slug> — <what it checks> · <mode> run
Brief: <abs>/brief.md — read the top, your "### <slug>" block, and the bottom
Context: <abs>/contexts/<slug>.md — if built, read it for selected evidence; the brief remains authoritative
Reference: <abs card or doc path(s)> — copy each one's first heading into its own ref: line, from line 2
Doc: <abs path of the full doc behind each card> — open it for the principles you cite
Format: <your mode's per-item format>
Write <abs run>/seats/<slug>.md, then return one line.
```

- **A context pack supplements the orders.** Include the `Context:` line only if that seat's pack
  was built successfully for the current brief and code state. A failed rebuild can leave an old
  pack on disk; existence alone does not establish freshness. It does not override the brief's
  objective, slice, hard constraints or reference docs.
  With no pack, dispatch still uses the complete brief. Do not imply that omitted paths are safe.

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
- **A worker stopped at its turn limit** (60 turns) may have left no file: `council seat … done`
  refuses without it and names the resume (SendMessage); never re-dispatch it.
- **The agent cap and the token ceiling.** When `council seat` says the run reached either, start no
  more agents — no re-dispatch, diagnosis worker or extra verifier — until the user says go; the
  hook refuses the next one until `council cap allow <n> --user-said "<their words>"` records it.
- **Alerts:** context-core, Alerts — the helper and the turn-end hook say when. Never for progress.
- **No notification comes from a worker that died with its session.** After a compaction, keep
  waiting. In a new session, follow Resume in context-core.
- **Whatever dispatches the workers** — the Agent tool, a Workflow script, background agents — the
  file contract holds: one file per seat in `seats/`. The seat-check hook covers only
  `council-worker` and `council-verifier` agents, never a Workflow's (their type is
  `workflow-subagent`), so give a Workflow's agents the worker's file rules in their prompt;
  `council collect` then checks every file in `seats/`, named in the brief or not.

## Done when

Every worker has reported, done or failed. → `council state phase=collect`
