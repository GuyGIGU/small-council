---
type: llm
focus: last_message
weight: 2
---
The branch changes an authentication check, adds a schema migration and adds a test. No UI template changed.

PASS if the reply does all of these:
- proposes a multi-seat run (a Squad of about 2–4 seats, verification included or mentioned);
- includes a security lens (for the auth change) and a data-integrity or migration lens (for the schema change);
- names the frontend or UX lens as not going, with a reason such as "no UI files changed";
- gives an estimated cost or effort;
- asks the user to go ahead (or to adjust) before any reviewing starts.

FAIL if it proposes a Solo run, leaves out security or data integrity, calls every seat regardless of what changed, or starts reviewing without asking.
