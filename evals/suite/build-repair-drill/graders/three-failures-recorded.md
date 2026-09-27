---
type: tool_used
tool: Bash
input_match: 'repair record\W+[A-Za-z0-9][\w.-]*\W+tests\b'
min: 3
max: 3
arm: with-only
---
Every failed run of the tests gate during the task is recorded with `council repair record`, and the loop ends at the third: exactly three records for the tests gate — not fewer (an attempt went unrecorded or the loop stopped early) and never a fourth. Counts every agent's calls, so a diagnosis worker that records an attempt also fails this.
