---
type: tool_used
tool: Agent
input_match: '^(?![\s\S]*Seat: (?:reader|runner))[\s\S]*"subagent_type"\s*:\s*"(?:[\w-]+:)?council-worker"'
min: 0
max: 1
arm: with-only
---
A build dispatches at most one diagnosis worker per stuck task. The reader and the runner at the end (D56) are not diagnosis workers.
