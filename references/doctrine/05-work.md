# Stage 5 — Work

If `council status` reports it needs optional Python 3.8+, relay `council run status` instead:
it gives the run's phase and cost line without Python.

The seats work in parallel, each in its own window. You dispatch, then wait.

## Dispatch

- **All worker Agent calls go in one message**, with `subagent_type: small-council:council-worker`.
  The worker contract lives in that agent. If the type is unavailable, use `general-purpose` and paste
  the rules from `${CLAUDE_PLUGIN_ROOT}/agents/council-worker.md`.
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

- **Right after dispatching:** `council seat <slug> running agent=<agentId>` for each worker — the id
  the Agent or Workflow tool returned, never a role name. The first time a run dispatches, show its
  status once (context-core, "Talking to the user").

## While they work

- Wait for the completion notifications. Never poll, and never open a subagent's transcript or
  output log.
- **On each notification:** `council seat <slug> done tokens=<the notification's figure, as given>`,
  or `failed note="…"` (with its tokens if it reported any). Once per finished agent run; a resumed
  worker's later figure is its running total, so record it as given. A Workflow's notification:
  `agents=<agent_count> tokens=<subagent_tokens>`. A seat you did yourself: `done agents=0`. It prints a progress line — relay it to the user as one short line: "3 of 5
  seats in — Security, Structure, Tests · ~210k tokens so far".
- **The agent cap.** If `council seat` says the run has used its cap, start no more agents — no
  re-dispatch, diagnosis worker or extra verifier — until the user says go. If it says the run is
  over its cap, tell the user in one line how many agent runs it used against the cap.
- **The token ceiling.** If `council seat` says the run passed the owner's token ceiling, start
  nothing more until the user says go. Report the known usage and ceiling in one short line.
- **Notify when the owner is needed.** Right after setting `council state waiting="…"`, or when an
  agent cap or token ceiling stops further work, run `council status --line`. If it prints a line
  and `PushNotification` is available, send that line once with the tool. Never notify for routine
  progress. A project can disable these alerts with `- notifications: off` in
  `.council/council.config.md`; then `--line` prints nothing.
- **No notification comes from a worker that died with its session.** After a compaction, keep
  waiting. In a new session, follow Resume in context-core.
- **Whatever dispatches the workers** — the Agent tool, a Workflow script, background agents — the
  file contract holds: one file per seat in `seats/`.

## Done when

Every worker has reported, done or failed. → `council state phase=collect`
