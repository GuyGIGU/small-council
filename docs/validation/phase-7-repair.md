# Phase 7 — bounded repair validation

The Phase 7 helper is deliberately a recorder and adviser, not an autonomous repair engine. It
snapshots the output of a gate already run by the Chair, classifies a textual failure signal,
suggests a reference lens, and caps one task's same-gate failure trail at three. The build mode
continues to own code changes, side-effect approvals, verifier dispatch, and the final receipt.

## Local checks (2026-09-24)

`python evals/run_repair.py` exercises temporary build runs: a test failure, second-failure
independent-diagnosis recommendation, third-failure stop, duplicate-event refusal, same-gate
requirement, a nonempty passing rerun, stale proof, category tampering, red baseline, unknown and
environment categories, and the Bash CLI handoff. These fixtures test mechanics, not model judgment.
The wider structural, helper, hook, evidence, impact and context suites remain the regression gates.

## What is not established

No live Claude build was run for this phase on this machine. The `claude` command is unavailable;
the Phase 5.5 paired context experiment is still deferred. The text classifier can be wrong, and a
matched failure line can be a symptom rather than a cause. A red baseline is labelled but not
automatically separated into old and new failing cases. The helper does not prove that the chosen
expert, diagnosis, or repair is effective, and does not make context packs default.

## Live acceptance check when a runtime is available

In disposable worktrees, use a small seeded build with a known failing test, a case where the
failure is environmental, and a case whose first two repairs are deliberately insufficient. Keep
model, task, gates, repository snapshot and approval conditions fixed. Check whether the Chair
records each distinct gate execution, inspects the output and baseline, routes an independent
read-only diagnosis after the second failure, stops after the third, and only calls a task fixed
after the same nonempty gate passes and a verifier agrees. Score correctness and unauthorized
extra changes before time or token cost. Save the run artifacts and note any human interventions;
do not infer a benefit from the local fixture pass count.
