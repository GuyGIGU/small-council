---
type: tool_used
tool: Agent
input_match: '(?:[\w-]+:)?council-worker[\s\S]*Seat: (?:reader|runner)|Seat: (?:reader|runner)[\s\S]*(?:[\w-]+:)?council-worker'
min: 2
max: 2
---
The build ends with the reader and the runner on the whole change (D56), once each: the fix round is proved by the gates, not by a second pair.
