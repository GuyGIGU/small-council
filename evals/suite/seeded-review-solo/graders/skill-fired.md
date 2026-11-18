---
type: tool_used
tool: Bash
input_match: '(?:council(?:\\")?|\$\{?(?:C|COUNCIL)\}?)\s+run\s+open\s+council-review\b'
min: 1
---
The review runs through council-review's page, whose run opens with `council run open council-review`. A typed /council-review may load the page without a Skill call, and the page invokes no other skill, so the run's opening is the sign.
