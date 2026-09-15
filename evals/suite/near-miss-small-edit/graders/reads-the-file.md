---
type: tool_used
tool: Read
input_match: 'utils\.py'
min: 1
arm: both
---
The rename is handled directly — the file gets opened — so a run that never started can't pass by starting nothing.
