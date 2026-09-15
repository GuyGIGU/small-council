---
type: regex
target: trace
flags: i
arm: with-only
pattern: 'reviews/[^"\\]+\.md[^\n]*(?:bypass|if not given|(?:empty|missing|blank|falsy|no) (?:token|string)|without (?:a |any )?token)'
---
The deliverable written under .council/reviews/ reports the bypass: token_ok() now returns True when no token is given. Checked on the trace line that writes the file.
