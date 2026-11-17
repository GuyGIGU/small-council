---
type: regex
target: { source: file, path: verify-build.md }
pattern: '\|\s*3\s*\|[^|\n]*\|\s*OK\s*\|'
---
Task 3 extends `settings.get()` with a default and refuses with `AppError(400, …)`: the one way, and the
decision kept.
