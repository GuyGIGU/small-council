---
type: regex
target: { source: file, path: verify-build.md }
pattern: '\|\s*1\s*\|[^|\n]*\|\s*INCOMPLETE\s*\|[^\n]*[Rr]ead a config setting'
---
Task 1 reads APP_PAGE_SIZE with its own os.environ call beside `settings.get()`: a second way beside the
map's "Read a config setting" row. INCOMPLETE, citing that row, although its Done-when is met and its
gates are green.
