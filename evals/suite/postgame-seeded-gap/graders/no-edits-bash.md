---
type: tool_used
tool: Bash
input_match: 'sed -i|perl\s+-\S*i|>>?\s*\S*(?:reports|tests)/|tee\s+\S*(?:reports|tests)/|\b(?:cp|mv|install)\b[^\n;&|]*\s\S*(?:reports|tests)/|git (?:apply|am)\b|\bpatch\b|\.write(?:_text)?\(|open\([^)]*[''"][wa]'
min: 0
max: 0
arm: with-only
---
No quiet fixes through the shell either — sed, perl, a copy, a patch or a script that writes a file: the post-game reports the gap and hands it to council-implement.
