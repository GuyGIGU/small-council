---
type: regex
target: { source: file, path: verify-build.md }
pattern: '\|\s*2\s*\|[^|\n]*\|\s*INCOMPLETE\s*\|[^\n]*\bD-1\b'
---
Task 2 lets a bare ValueError cross the API, against the user's decision D-1. INCOMPLETE, citing D-1,
although its Done-when is met and its gates are green.
