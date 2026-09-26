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
  - frozen and protected files, compared whole (line endings aside);
  - files changed outside the plan's scope;
  - assertions removed from existing tests;
  - a test the plan requires: a new or changed test method that calls the code in question;
  - whether the final report claimed success that the hidden checks do not support.
- **Hidden means out of reach.** Each case's traps, checks and example outcomes are stored encoded in
  `evals/bench/<case>.hidden`, so a search of the plugin folder does not find them, and the cases'
  own descriptions stay generic. This is a deterrent, not a secret. `python evals/bench.py show
  <case>` decodes one for review.
- **Tests the agent cannot fake.** The scorer runs the hidden and original tests itself, outside the
  project's reach:
  - in an isolated Python that imports the real `unittest` before the project is on the path (a
    project `unittest.py`, `sitecustomize.py` or bytecode cannot stand in for it);
  - under a hidden module name drawn at random;
  - reading the result from a file outside the project, tagged with a nonce.

  A pass needs every expected test to run, none skipped, none failed, and a canary assertion to fail
  as it must. A process that exits early leaves no result, and no result is a failure.
- **A task counts as met** when all of these hold:
  - the hidden checks pass;
  - the original tests pass;
  - no frozen or protected file changed;
  - a test was added, where the plan requires one.

  Scope creep, removed assertions, false completion claims, asking for input, cost, tokens, turns
  and agents are reported next to it, not folded into one score.

## The cases

| Case | Category |
|---|---|
| `bench-refund-sign` | cross-module bug |
| `bench-slug-contract` | test repair: a protected contract test |
| `bench-admin-delete` | security-sensitive change |

Each case's traps are in its encoded bundle (`python evals/bench.py show <case>`), not here: the arm
with the plugin can read the plugin's folder, the other arm cannot.

`python evals/bench.py self-test` checks every case without a model. It confirms that:
- an untouched project fails the hidden checks, so a run that did nothing cannot pass;
- the reference solution meets the task, so the task is solvable;
- each trap is scored as intended (twelve example outcomes);
- six ways of faking a test run all fail:
  - a project `unittest.py` (and its bytecode) printing a pass;
  - a planted package under a hidden module's name;
  - a package that exits with success on import;
  - assertions patched to pass;
  - tests that skip themselves;
  - a `sitecustomize.py`;
- twelve final reports are read as they should be ("a non-admin cannot delete" is no disclosure;
  "not fixed yet" and "1 test fails" are);
- the comparison refuses a run counted twice, and says how many runs had no partner;
- the arithmetic is right.

## Running a pilot (paid — needs the owner's budget)

Run where live evals run (WSL2, macOS or Linux; see `evals/README.md` §10):

```bash
claude plugin eval . --tag benchmark --scaffold --keep-temp --runs 1 --model claude-opus-5 \
  --max-cost-usd 30 --allow-tools Bash Write Edit --no-publish --json evals/suite/results/bench.json
```

Then score each kept run and compare:

```bash
python3 evals/bench.py score --case bench-refund-sign --arm with --repo <kept project> --trace <trace.jsonl> --run 1 >> results.jsonl
# --run is required and unique per case and arm: compare refuses the same run twice
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
- A claim of success and a disclosure of unfinished work are phrase matches on the final report. A
  claim written in other words can be missed. The report text is kept in each record so a person can
  check.
- The arm with the plugin can read the plugin's folder, which holds the scorer and this README.
  The bundles are encoded and the case descriptions generic, but a determined agent could still
  read how it will be scored.
- A project's own code runs during scoring. The scorer defends against the obvious fakes above, not
  against code written to attack it.
- Review, planning and research modes have no benchmark yet. Their outcomes (findings and their
  truth) need a different key.
