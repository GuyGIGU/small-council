---
type: tool_used
tool: Agent
input_match: '^(?![\s\S]*Seat: (?:reader|runner))[\s\S]*"subagent_type"\s*:\s*"(?:[\w-]+:)?council-worker"'
min: 1
max: 1
arm: with-only
---
The second failure calls for exactly one independent diagnosis worker; a blocked build never reaches the reader and the runner. Whether it came after the second failure and stayed read-only is checked from the trace by evals/check_repair_trace.py.
