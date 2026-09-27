---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?(?:council-implement|context-core)"'
---
The build runs through council-implement. A typed /council-implement may load the skill without a Skill call; its first step invokes context-core, so either counts.
