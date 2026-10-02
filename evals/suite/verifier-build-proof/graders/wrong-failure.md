---
type: regex
target: { source: file, path: verify-build.md }
pattern: '\|\s*4\s*\|[^|\n]*\|\s*CANNOT VERIFY\s*\|'
---
Exit 127 was a missing tool, not a reproduction of the empty-average defect.
