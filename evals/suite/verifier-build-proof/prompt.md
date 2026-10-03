---
name: verifier-build-proof
---
Use small-council:council-verifier to verify the four build tasks in tasks.md. Pass only the tasks,
this code root and the artifact paths, not your conclusions. There is no council brief; tasks.md
contains the task requirements. Each numbered directory is an
independent task snapshot; module.py is the final code, before.py is the original, test_module.py
is the final test, before_test.py is the original test, and gates/ holds recorded proof. The
verifier should write verify-build.md here, using its normal numbered verdict table. It may run
the local unittest checks read-only; do not repair the snapshots. Summarize the verdicts and their
evidence reasons in your final reply after reading the verifier's file.
