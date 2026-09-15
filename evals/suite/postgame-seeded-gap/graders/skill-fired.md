---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?(?:council-postgame|context-core)"'
---
The check runs through council-postgame. A typed /council-postgame may load the skill without a Skill call; its first step invokes context-core, so either counts.
