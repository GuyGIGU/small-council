---
type: tool_used
tool: Agent
input_match: '"subagent_type"\s*:\s*"(?:[\w-]+:)?council-worker"'
max: 1
arm: with-only
---
A build dispatches verifiers and at most one diagnosis worker per stuck task, across gate and verifier failures. No second worker.
