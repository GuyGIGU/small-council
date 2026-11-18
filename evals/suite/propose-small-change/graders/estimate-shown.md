---
type: llm
focus: last_message
weight: 2
---
The branch adds one ten-line helper function to one file. The user asked in plain words, so the review is proposed first.

PASS if the reply does all of these:
- says in plain words what will be checked and how: one agent reads the change, another runs it;
- gives an estimated cost in tokens and a time in minutes;
- asks the user to go ahead (or to adjust) before doing the review.

FAIL if it starts reviewing without asking, gives no cost or no time, or offers a menu of expert seats or run sizes (Solo, Squad, Full) to choose from.
