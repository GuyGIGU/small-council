---
type: tool_used
tool: Agent
input_match: '"subagent_type"\s*:\s*"(?:[\w-]+:)?council-worker"'
min: 1
max: 1
arm: with-only
---
The second failure calls for exactly one independent diagnosis worker, and a build dispatches no other council-worker. Whether it came after the second failure and stayed read-only is checked from the trace by evals/check_repair_trace.py.
