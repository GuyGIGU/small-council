# Model routing

Optional per-seat model requests are recorded in the run plan and are disabled by default in the
config template. The plan checker accepts `inherit`, `sonnet`, or `haiku`, and rejects non-inherited
choices for the Chair or verifier. An override requires a declared mapping or survey purpose;
Assign/Work requires the Chair to make sure the assignment actually matches that declaration.
History splits exact recorded token counts by the planned model and labels them as tokens rather than
money; inherited seats' actual model is unknown.

Automated checks cover plan validation, the disabled default, declared-purpose restrictions, protected
Chair/verifier roles, plan display, and history totals. These checks do not verify a real Claude Code
dispatch, actual model selection, answer quality, or cost savings. No paid benchmark or live session
was run.
