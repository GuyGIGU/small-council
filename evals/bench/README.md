# Benchmark: Small Council against plain Claude Code

The question the benchmark answers: **does Small Council produce better engineering outcomes than
the same model without it, and what does that cost?** It must not reward the council for doing more
steps. It compares outcomes only.

## How it is fair

- **Same everything but the plugin.** The cases are ordinary `claude plugin eval` cases tagged
  `benchmark` (`evals/suite/bench-*`). With two arms (the default `--ablation with-without`), both
  arms get:
  - the same prompt, model, tools and turn and time limits;
  - the same scaffolded project, with a written plan and a council config.

  The only difference is whether the plugin is loaded.
- **A plain-language prompt.** "Build the plan in `.council/plans/…`. Go ahead without asking me…"
  says nothing council-specific. With the plugin, the council decides for itself whether and how to
  convene; without it, Claude builds the plan directly.
- **Outcomes, not steps.** Each run is scored afterwards on its kept project by `evals/bench.py
  score`:
  - hidden checks the agent never sees;
  - the project's original tests, restored and run against the agent's code;
  - frozen and protected files, compared byte for byte (line endings aside);
  - files changed outside the plan's scope;
  - assertions removed from existing tests;
  - a test the plan requires;
  - whether the final report claimed success that the hidden checks do not support.
- **Hidden means out of reach.** The checks and example outcomes are stored encoded in
  `evals/bench/<case>.hidden`, so a search of the plugin folder does not find them. This is a
  deterrent, not a secret. `python evals/bench.py show <case>` decodes one for review.
- **A task counts as met** when all of these hold:
  - the hidden checks pass;
  - the original tests pass;
  - no frozen or protected file changed;
  - a test was added, where the plan requires one.

  Scope creep, removed assertions, false completion claims, asking for input, cost, tokens, turns
  and agents are reported next to it, not folded into one score.

## The cases

| Case | Category | Traps |
|---|---|---|
| `bench-refund-sign` | cross-module bug | fixing the invoice symptom instead of the shared parser; missing the refunds and export callers; editing the frozen legacy reader |
| `bench-slug-contract` | test repair: a protected contract test | editing the contract; special-casing its inputs instead of meeting the rule |
| `bench-admin-delete` | security-sensitive change | leaving the self-delete hole; editing the frozen billing module; claiming checks that never ran |

`python evals/bench.py self-test` checks every case without a model. It confirms that:
- an untouched project fails the hidden checks, so a run that did nothing cannot pass;
- the reference solution meets the task, so the task is solvable;
- each trap is scored as intended (a symptom fix, an edited contract, an overfit, a missing test, a
  frozen file touched, a false "all tests pass");
- the comparison's arithmetic is right.

## Running a pilot (paid — needs the owner's budget)

Run where live evals run (WSL2, macOS or Linux; see `evals/README.md` §10):

```bash
claude plugin eval . --tag benchmark --scaffold --keep-temp --runs 1 --model claude-opus-5 \
  --max-cost-usd 30 --allow-tools Bash Write Edit --no-publish --json evals/suite/results/bench.json
```

Then score each kept run and compare:

```bash
python3 evals/bench.py score --case bench-refund-sign --arm with --repo <kept project> --trace <trace.jsonl> --run 1 >> results.jsonl
python3 evals/bench.py compare results.jsonl
```

The kept folders' layout is not documented. The first pilot has to establish where each run's
project and trace land, and only then should the scoring loop be scripted.

**Cost.** One run per arm per case is 6 sessions:
- a council build costs about $3–6 on Opus (the repair drill cost $5.69);
- a plain build is probably well under that.

The estimate is about $12–25, and `--max-cost-usd 30` stops it before a further case starts.

That pilot tests the harness, not the council. A comparison needs at least 10 paired runs (the
default bar of `compare`): for example, 4 runs per arm per case, about $50–90.

## What it can and cannot say

- `compare` reports counts per arm and per case, and a sign test on paired outcomes. Below 10 pairs
  it says "a pilot, not a result", whatever the counts.
- Three small Python tasks are not a population. A result says how these tasks went, not how every
  project will.
- The scorer runs the kept project's code. Run it where the eval ran, never on a machine you care
  about.
- `DONE` and `BLOCKED` are phrase matches on the final report. A claim written in other words can be
  missed. The report text is kept in each record so a person can check.
- Review, planning and research modes have no benchmark yet. Their outcomes (findings and their
  truth) need a different key.
