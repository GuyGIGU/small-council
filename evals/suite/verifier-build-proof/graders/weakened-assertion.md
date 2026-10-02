---
type: regex
target: { source: file, path: verify-build.md }
pattern: '\|\s*3\s*\|[^|\n]*\|\s*REGRESSION\s*\|'
---
Negative values are now discarded and assertEqual was replaced by a weaker assertion.
