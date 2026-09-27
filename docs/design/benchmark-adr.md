# ADR: baseline-versus-council benchmark

## Problem

Nothing yet shows that the council beats the same model working alone. The behavioural suite checks
that the council behaves as designed — it triggers, sizes, verifies, stops — not that its builds come
out better. Without a fair comparison, every later "learning" or "self-tuning" step would optimise
for doing the council's steps, not for outcomes.

## Constraints

- No paid run without the owner's budget; the harness must be testable for free.
- Reuse `claude plugin eval` rather than a second runner: it already isolates each run, handles
  sign-in and the Bash sandbox, and runs a without-plugin arm.
- Its graders cannot run code, and its report does not document per-run tokens.
- Score outcomes, never the number of steps.

## Options

1. **Graders only.** Put regex and LLM graders on the final message and files. This is cheap, but
   it cannot tell whether the code works, and LLM judgement of code is noisy.
2. **A separate runner** that drives `claude -p` itself, with and without the plugin. This gives
   full control, but it duplicates isolation, sign-in and sandbox handling the eval tool already
   does.
3. **Post-hoc scoring.** Run cases through `claude plugin eval` with both arms, keep each run's
   project, and score it afterwards with hidden checks and file comparisons.

## Decision

Option 3.
- **Cases.** Three build cases (`evals/suite/bench-*`, tag `benchmark`) each carry a written plan
  and one trap.
- **Hidden checks** and each case's traps live encoded in `evals/bench/<case>.hidden`, where a search
  of the plugin tree does not find them.
- **Tests run where the project cannot reach them.** An isolated Python imports the real `unittest`
  first, runs the tests under a random module name, and writes a nonce-tagged result outside the
  project. A pass needs:
  - the exact test count;
  - no skips and no failures;
  - a canary assertion that fails as it must.
- **Scoring.** `evals/bench.py score` judges each kept run on:
  - hidden checks;
  - restored original tests;
  - frozen and protected files;
  - scope;
  - removed assertions;
  - a required test;
  - false completion claims.
- **Comparison.** `compare` reports counts per arm and a sign test, and refuses to call fewer than
  ten pairs a result.
- **The self-test** proves each case is unsolved when untouched, solvable, and scored as intended
  on every trap. It runs in CI.

## Tradeoffs

- Three small Python tasks are a narrow sample.
- The prompt says "Go ahead without asking me", which may not stop a Full-size council from asking
  anyway. Asking is scored as human effort, not as failure.
- Claims are read by phrase matching.
- Encoding hides the checks from a search, not from a determined reader.
- The kept-folder layout must be learned from the first pilot before scoring can be scripted end to
  end.

## Alternatives rejected

- LLM-judged correctness.
- A single composite score.
- Rewarding the council for convening, dispatching or verifying.
- A benchmark service or dashboard.

## Revisit when

- The first paid pilot shows the kept layout and real per-run costs.
- Review-mode outcomes need a key (planted defects and accepted patterns, as in
  `seeded-review-solo`).
- There are enough pairs to justify more cases instead of more runs.
