---
type: regex
target: { source: file, path: verify-1.md }
pattern: '\|\s*4\s*\|[^\n]*\bREFUTED\b'
---
Claim 4 is false: `total` is a local variable, created fresh on every call.
