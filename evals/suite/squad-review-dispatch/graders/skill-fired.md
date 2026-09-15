---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?(?:council-review|context-core)"'
---
The review runs through council-review. A typed /council-review may load the skill without a Skill call; its first step invokes context-core, so either counts.
