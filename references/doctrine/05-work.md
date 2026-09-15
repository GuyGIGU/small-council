# Stage 5 — Work

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
Reference: <abs path(s)> — copy each one's first heading into its own ref: line, from line 2
Format: <your mode's per-item format>
Write <abs run>/seats/<slug>.md, then return one line.
```

- **Right after dispatching:** `council seat <slug> running agent=<agentId>` for each worker.

## While they work

- Wait for the completion notifications. Never poll, and never open a subagent's transcript or
  output log.
- **On each notification:** `council seat <slug> done tokens=<total from the notification>`, or
  `failed note="…"`. It prints a progress line — relay it to the user as one short line: "3 of 5
  seats in — Security, Structure, Tests · ~210k tokens so far".
- **No notification comes from a worker that died with its session.** After a compaction, keep
  waiting. In a new session, follow Resume in context-core.
- **Whatever dispatches the workers** — the Agent tool, a Workflow script, background agents — the
  file contract holds: one file per seat in `seats/`.

## Done when

Every worker has reported, done or failed. → `council state phase=collect`
