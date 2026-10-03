---
type: tool_used
tool: Bash
input_match: 'gate\s+before-1\b[^\n]*--proof(?:\s+|=)preserve\b'
min: 1
---
The refactor declares preservation before editing; legacy green-before evidence is not relabelled.
