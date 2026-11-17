---
name: verifier-second-way
---
Use small-council:council-verifier to verify the three build tasks in tasks.md as changes. Pass only
tasks.md (it quotes the recorded decisions in scope), this code root, the council home .council/ and
the artifact paths, not your conclusions. There is no council brief; tasks.md holds the task
requirements. Each numbered directory is an independent task's code root after the build, base/ is the
code before it, and gates/ holds recorded proof. The verifier should write verify-build.md here, using
its normal numbered verdict table. It may run the local unittest checks read-only; do not repair the
snapshots. Summarize the verdicts and their evidence in your final reply after reading the verifier's
file.
