---
type: tool_used
tool: Bash
input_match: '(?:council(?:\\")?|\$\{?(?:C|COUNCIL)\}?)\s+run\s+close\b'
min: 1
arm: with-only
---
The Chair closes the run it opened with `council run close`: the close stamps the actual cost, records each seat's ledger row and reminds it to show the closing card. A run left open is still "in progress" for the next session.
