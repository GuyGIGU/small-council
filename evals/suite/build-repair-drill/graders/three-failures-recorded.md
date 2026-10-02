---
type: tool_used
tool: Bash
input_match: 'council\W+gate\W+tests\b'
min: 3
max: 3
arm: with-only
---
The tests gate runs exactly three times once the change is in, and the loop ends at the third: `council gate tests` records each failed run as an attempt itself (0.19), so three runs are the three records — not fewer (the loop stopped early) and never a fourth (the helper refuses a fourth run, but trying it is a failure of the procedure). The baseline runs as `council gate --all`, which this does not count. Counts every agent's calls, so a diagnosis worker that runs the gate also fails this.
