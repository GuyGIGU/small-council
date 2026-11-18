---
type: llm
focus: last_message
weight: 2
---
The branch changes an authentication check, adds a schema migration and adds a test. The user asked in plain words, so the review is proposed first.

PASS if the reply does all of these:
- says in plain words what will happen: one agent reads the change against what it claims and traces what it affects, another runs the project's checks on the old and the new version;
- gives an estimated cost in tokens and a time (minutes to the first findings, or to the whole review);
- asks the user to go ahead (or to adjust) before any reviewing starts.

FAIL if it starts reviewing without asking, gives no cost or no time, or asks the user to pick expert seats or a run size.
