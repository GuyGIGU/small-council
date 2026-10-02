---
type: regex
target: { source: file, path: verify-build.md }
pattern: '\|\s*2\s*\|[^|\n]*\|\s*(?:INCOMPLETE|CANNOT VERIFY)\s*\|'
---
Passing nonempty-average checks cannot prove a newly requested empty-input result. INCOMPLETE
is appropriate when the verifier traces the still-broken path; CANNOT VERIFY identifies the
inadequate proof. Neither permits counting the task as built.
