---
type: tool_used
tool: Bash
input_match: '(?:council(?:\\")?|\$\{?(?:C|COUNCIL)\}?)\s+status\b'
min: 2
max: 6
arm: with-only
---
The user is shown the run's status twice: at the first dispatch, and the closing card after `council run close`. With no show_widget tool here, the Chair relays `council status` (the card's text) each time; the alert line (`council status --line`) and one retry may add calls. Fewer than two means a card was skipped; more than six means a card per progress line. `council run status` and `council tui` are not the card. A call through a shell variable still counts here: `council run audit` judges the call form.
