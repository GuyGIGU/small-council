---
type: regex
target: trace
flags: i
arm: with-only
pattern: 'reviews/[^"\\]+\.md[^\n]*(?:ZeroDivision|divi(?:de|sion) by zero|empty (?:list|input|sequence))|(?:ZeroDivision|divi(?:de|sion) by zero|empty (?:list|input|sequence))[^\n]*reviews/[^"\\]+\.md'
---
The deliverable under .council/reviews/ carries the planted bug: average() divides by zero on an empty list. Checked on the trace line that writes the file, so it doesn't depend on what the last message says.
