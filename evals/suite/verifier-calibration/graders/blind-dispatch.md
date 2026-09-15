---
type: tool_used
tool: Agent
input_match: 'if items|is guarded|local variable|is local'
min: 0
max: 0
arm: with-only
---
The verifier gets the claims and nothing else — never the session's own view of which ones are true (claim 2's guard, claim 4's local variable).
