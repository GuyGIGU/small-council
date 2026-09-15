---
type: regex
target: { source: file, path: verify-1.md }
pattern: '\|\s*2\s*\|[^\n]*\bREFUTED\b'
---
Claim 2 is false: `if items else None` guards the empty list, so there is no IndexError.
