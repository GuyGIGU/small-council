---
type: tool_used
tool: Bash
input_match: 'repair record\W+[A-Za-z0-9][\w.-]*\W+(?:before|after)-'
min: 0
max: 0
arm: with-only
---
The intentionally failing before-<n> check, and the after-<n> check, are proof steps, not repair attempts: neither is ever recorded with `council repair record`.
