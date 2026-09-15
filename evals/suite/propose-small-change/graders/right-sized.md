---
type: llm
focus: last_message
weight: 2
---
The branch adds one ten-line helper function to one file.

PASS if the reply does all of these:
- proposes a right-sized run for a change this small: Solo (the main session reviews it alone), or at most a small Squad of two seats (verifiers don't count as seats) — not a Full council;
- says in plain words what will be checked;
- says what it leaves out: for a Squad, at least one seat or lens not called, with a reason; for Solo, why no seats are needed, or which lenses have nothing to look at in this change;
- gives an estimated cost or effort;
- asks the user to go ahead (or to adjust) before doing the review.

FAIL if it proposes a Full council or more than two seats, starts reviewing without asking, or gives no size or cost.
