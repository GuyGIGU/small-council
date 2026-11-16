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
  and agents are reported next to it, not folded into one score. So are tokens by role, read from
  the kept project's own build runs (see "Builder against Chair" below).

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
- the arithmetic is right;
- the build arms: a `builder` and a `chair` run scored from a fixture trace and a fixture run folder,
  tokens by role with a complete run, an incomplete one and none, the two arms paired, an old
  `results.jsonl` compared byte for byte as before (with build records beside it too), and the
  prompt swap below put on and taken off.

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

## Builder against Chair: the build arms

The second question, from the task tree (section 6): does a fresh builder agent per task build
better or worse than the Chair building every task itself, and what does each cost by role? Both
arms load the plugin; `compare --pair build` sets them side by side.

- **`builder`**: the prompt as committed. The council builds as it does by default, with a builder
  agent per task.
- **`chair`**: the same prompt with one sentence added after its first, by `python evals/bench.py
  arm chair`: "Build every task yourself, in this session: start no builder agent for it. Check the
  work as you otherwise would." `python evals/bench.py arm builder` takes it out again, leaving the
  prompts byte for byte as committed.

That sentence is the only difference. The scaffold, the plan, the council config, the model, the
tools and the limits are the same, and the sentence asks for the same checking, so the verifier
count should match. Two rows of `compare --pair build` show whether it held:
- **median verifier seats**: the `verify-…` seats that ran;
- **runs not built their arm's way**: a `chair` run with a build seat (`task-<n>`), or a `builder`
  run without one. Read such a run as off its arm, not as a result for it.

**Tokens by role.** `score` reads every `council-implement` run in the kept project's council home,
under the per-seat rule of `src/council/records/usage.py`:
- builder: the build seats, `task-<n>`;
- verifier: `verify-…` and `diagnose-…` seats (a diagnosis worker counts with the verifiers, as it
  does in the run's own totals);
- other: every other agent seat.

Each record holds them under `roles`, beside the session's own totals from the trace (`cost`). A
figure is blank, never 0, when the project has no build run or a seat's usage was never reported
(`roles.basis` says why). A `chair` run's builder tokens are a known 0. Whether the trace's session
total includes the agents' own usage is for the first pilot to establish; until then, read the
role figures and the session total side by side, not summed.

**What three small cases cannot say.** These are three small Python tasks of one plan each.
- A builder agent's expected gain is a Chair whose window stays small through a long build. A short
  build never fills the window, so these cases cannot show it. A Solo build stays with the Chair
  for that reason (the user, 2026-11-15).
- A builder agent reads the code again, so its total tokens will probably be higher here; that is
  not by itself a verdict on long builds.
- The sentence that makes the `chair` arm is a prompt, not a switch: a run can ignore it (the
  off-arm row counts that), and it may change more than who builds.
- Below 10 pairs `compare` says "a pilot, not a result". Even above it, the result is about these
  cases.

**Running it (paid, on the owner's go).** Where live evals run, in this order:

```bash
python3 evals/bench.py arm builder         # the prompts as committed
claude plugin eval . --tag benchmark --ablation none --scaffold --keep-temp --runs 1 --model claude-opus-5   --max-cost-usd 20 --allow-tools Bash Write Edit --no-publish --json evals/suite/results/bench-builder.json
python3 evals/bench.py score --case <case> --arm builder --repo <kept project> --trace <trace.jsonl> --run 1 >> results.jsonl
python3 evals/bench.py arm chair
claude plugin eval . --tag benchmark --ablation none --scaffold --keep-temp --runs 1 --model claude-opus-5   --max-cost-usd 20 --allow-tools Bash Write Edit --no-publish --json evals/suite/results/bench-chair.json
python3 evals/bench.py score --case <case> --arm chair --repo <kept project> --trace <trace.jsonl> --run 1 >> results.jsonl
python3 evals/bench.py arm builder         # put the prompts back
git diff --exit-code evals/suite           # nothing left changed
python3 evals/bench.py compare results.jsonl --pair build
```

`--ablation none` runs the plugin arm only. Score each kept run once per case and arm, with its own
`--run`. Never run the two arms at once: the swap edits the prompts in place. The kept folders'
layout is still to be established by the first pilot, as above.

**Cost.** One run per arm per case is 6 council builds, about $3–6 each on Opus: about $18–36, with
`--max-cost-usd 20` stopping each arm before a further case. Ten pairs (4 runs per arm per case) is
24 builds, about $72–144.

A `with` run of the plugin pair is the same setup as a `builder` run. Score a run under the label of
the comparison it is for; the same run scored under both labels is counted in both.

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
