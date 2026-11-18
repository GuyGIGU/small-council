---
type: tool_used
tool: Agent
input_match: '"subagent_type"\s*:\s*"(?:[\w-]+:)?council-worker"'
min: 2
max: 2
arm: with-only
---
A review's two fixed agents, the reader and the runner, go out as council-worker agents without a second approval — the /command and the config's "approve without asking: up to squad" already cover it. A worker stopped at its turn limit is resumed, never dispatched again, so there is no third.
