---
type: tool_used
tool: Agent
input_match: '"subagent_type"\s*:\s*"(?:[\w-]+:)?council-verifier"'
min: 1
arm: with-only
---
The auth bypass is a P1 on a protected subject, so it gets a blind verifier of its own at Challenge.
