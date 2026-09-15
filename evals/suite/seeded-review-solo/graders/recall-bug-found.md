---
type: llm
focus: last_message
weight: 3
---
The change adds sample.py. Its `average(values)` divides by `len(values)` with no guard, so an empty list raises ZeroDivisionError. That is the one real bug in the change.

PASS if the reply reports this: average() fails (divides by zero, crashes, raises) on an empty list or has no empty-input guard, as a finding of real severity (P1 or P2, or described as a bug).

FAIL if the empty-input problem in average() is missing, or is mentioned only as a minor style note.
