# Phase 10 — baseline-versus-council benchmark

## What changed

- **Three benchmark cases** in `evals/suite/bench-*` (tag `benchmark`) for `claude plugin eval`:
  - a cross-module bug (`bench-refund-sign`);
  - a protected contract test (`bench-slug-contract`);
  - a security-sensitive change (`bench-admin-delete`).

  Both arms get the same plain prompt, model, tools and scaffolded project, and each project has a
  written plan and one trap. The in-run graders are mechanical and score both arms: the frozen or
  protected file still holds its content, and the report says how the change was checked.
- **`evals/bench.py`**:
  - `score` judges one kept run on hidden checks, restored original tests, frozen and protected
    files, scope, removed assertions, a required test and false completion claims;
  - `compare` puts the arms side by side with a sign test and a ten-pair bar;
  - `self-test` checks the whole harness without a model;
  - `show`, `pack` and `unpack` maintain the encoded hidden bundles.
- **Documentation:** the protocol and costs are in `evals/bench/README.md`, the design in
  `docs/design/benchmark-adr.md`. CI runs the self-test.

## Why

Nothing showed that the council beats the same model working alone. Every later phase that "learns"
or "tunes" needs that measurement first, or it optimises for the council's steps instead of outcomes.

## Architecture and compatibility

The harness is evaluation tooling only: nothing in the plugin, the helper or the doctrine changed.
The new cases carry the `benchmark` tag, so a tagged run leaves them out. A whole-suite run without
`--tag` now includes them — 6 more sessions at `runs: 1`.

## Tests

`python evals/bench.py self-test`: 25/25, about 7 s, no model. It checks that:
- each case's untouched project fails its hidden checks, so a dead run cannot pass;
- each reference solution meets its task, so each task is solvable;
- all twelve example outcomes are scored as intended. These are three ideal fixes, a symptom-only
  fix, a frozen file touched, a do-nothing "all tests pass", an honest stop, an edited contract, an
  overfit, a missing required test, a self-delete hole, and a frozen module reformatted;
- the comparison arithmetic is right: one pair is "a pilot, not a result", twelve straight wins give
  p < 0.001, and the sign test gives exactly 2/1024 for 10–0.

Checked by hand as well: an untouched refund case runs 5 hidden tests and fails 4, with an
`AssertionError: 2.5 != -2.5`; the ideal fix passes all 5, the 3 restored original tests and the
agent's own 4.

Structural checks: 617/617, including three new benchmark checks:
- every case has a spec and a bundle;
- the cases are tagged `benchmark` and their graders score both arms;
- the prompts contain no council command.

## Evidence / metrics

No model has run the benchmark: a pilot needs the owner's budget. Estimated costs:
- a pilot (one run per arm per case): about $12–25, capped with `--max-cost-usd 30`;
- a first comparison that `compare` will call a result (at least 10 pairs): about $50–90.

## Known limitations

- The sample is three small Python tasks.
- Claims in the report are phrase-matched.
- The hidden bundles deter a search; they do not stop a determined reader.
- The eval tool's kept-folder layout is undocumented, so the first pilot must establish it before
  scoring is scripted end to end.
- A council may still ask before a Full-size run. That is scored as asking for input, not as failure.

## Deferred

- A review-mode benchmark (planted defects and accepted patterns).
- An end-to-end pilot script.
- Per-subagent token accounting (the trace may carry it; unverified).

## Not verified

- Any live run of these cases, in either arm.
- The scorer on a real kept folder and trace, rather than a synthetic one.
- macOS and Linux (CI runs the self-test on all three once pushed).
