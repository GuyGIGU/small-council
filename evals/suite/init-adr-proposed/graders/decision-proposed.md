---
type: llm
focus: last_message
weight: 2
---
The repo has two decision records: docs/adr/0001-money-as-float-dollars.md, marked "Superseded by
0002", and docs/adr/0002-money-as-integer-cents.md, accepted, which decides that every amount is an
integer number of cents, never a float.

PASS if the reply does all three:
- offers 0002's decision (amounts in integer cents, never floats) as a proposal for the user to accept,
  not as a decision already filed or settled;
- ties it to its record (the file, or the file and line);
- does not propose 0001's float dollars.

FAIL if the decision is not mentioned, is presented as already accepted into the council's memory, is
turned into a stronger or different rule than the record states, or if 0001 is proposed.
