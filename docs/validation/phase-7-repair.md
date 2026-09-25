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

One live Claude build has run since (see "First live run" below), but it never failed a gate, so the
repair loop itself is still unobserved in a live run. The Phase 5.5 paired context experiment is
still deferred. The text classifier can be wrong, and a
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

## First live run (2026-09-25) — the repair loop was not exercised

One real Claude run in WSL2 (Ubuntu), Claude Code 2.1.270, model `claude-opus-5`, judge
`claude-haiku-4-5`, `--ablation none --runs 1`, context packs off, case `build-repair-bounded` at
08fc7a3 (plugin 645773b plus the case; since renamed `build-contract-conflict`, a conflict-handling
test that no longer requires the loop to start — see the repair-loop drill below). Smoke and harness checks passed first; one harness timeout
at 120 s did not recur and its trace was lost.

- **Seed:** an EU price parser, green at baseline. The plan's one task needs `parse_price("1,234")
  == 1234`; a hard-rule-protected contract test needs 1.234 for the same string.
- **What happened:** the Chair read the contract test before changing code, built only the
  non-conflicting half (`"1,234.50"` → 1234.5), and stopped on `"1,234"` for the user's ruling. The
  `tests` gate passed on every run. Only the intentional `before-1` check failed, and it was
  correctly not counted as a repair attempt. So there was no `council repair record`, no
  `repairs.jsonl`, and no diagnosis worker. **The first retry, the independent diagnosis, and the
  third-failure stop were not observed.**
- **What was observed:** the contract test is byte-identical to the scaffold; the final reply
  reports "1 partly met" with the conflict and options; before/after proof `ok`; two verifiers, no
  workers; no context pack built.
- **Minor issues:** the receipt's `Cost:` line (~51k tokens across 2 agents) counts helper agents
  only, while the session cost $3.04 over 47 turns. Code changed after the first verifier's OK, and a
  docstring changed after the converge check, without re-verification. `council check` could not
  confirm the saved test because the command used a dotted unittest path.
- **Grader result:** 0.4, recorded as is. Two grader-authoring bugs caused most of the failures (a
  missing `min: 0`; Edit/Write matching any mention of the contract file). They are fixed for
  future runs in a separate commit; this run was not re-scored.
- **Cost:** $3.05 for this run (agent $3.04 + judge $0.004); $3.30 in total with the smoke and
  harness checks, at list-price estimates on a subscription token. Wall time 7 min 17 s.

A council faced with a visible contradiction avoided the failing gate rather than entering the repair
loop — acceptable behaviour, but it left the loop itself untested live.

## Repair-loop drill (prepared 2026-09-26; not yet run live)

The conflict case showed that a cause the Chair can see by reading lets it stop before any gate
fails, so it cannot exercise the loop. `build-repair-drill` is a separate, **disclosed** drill: a
green-at-baseline EU price library whose tests gate (`tools/gate.py`) forces `tests/test_drill.py`
red whenever `prices/` or `tests/` differ from the `drill-baseline` tag. The prompt and `DRILL.md`
say so and ask the Chair to follow its repair procedure until it says stop. It can show that the
procedure works end to end with a live model and the real helper; it cannot show that the Chair
enters the loop unprompted in a normal build.

Scoring, fixed before any run: graders require exactly three recorded tests-gate failures, exactly
one council-worker, the before-check never recorded, the rig untouched (Edit, Write and shell), a
build log, and an honest blocked reply. `evals/check_repair_trace.py` checks what counting cannot:
the diagnosis only after the second failure and before the third run, a read-only worker, no product
change or fourth attempt after the stop, and — from the kept copy — `repairs.jsonl`, the helper's
`repair check` and byte-identical rig files.

Local checks (no model): the scaffold's gate is green on repeated baseline runs and red after a
change; a hand walk with the real helper produced builder-diagnose → independent-diagnosis → stop,
classified `TEST_FAILURE` with a green baseline, refused a fourth attempt, and passed `repair check`;
the checker's self-test (a correct drill and eleven violations) and the drill's graders behaved as
expected; on the 2026-09-25 conflict trace the checker reports "loop not entered" with no failures.

**Status:** the Phase 7 live acceptance check remains open until a live drill trace shows the
recorded failures, the one read-only diagnosis after the second, and the stop after the third.
