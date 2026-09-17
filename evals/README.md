# evals/

Four automated layers, an advisory one, and hand-run drills. A skill isn't done until it's tested.

## 1. Validation — will the plugin load?

```bash
python scripts/quick_validate.py
```

Checks:
- the plugin and marketplace manifests;
- every skill's and agent's frontmatter;
- hook commands pointing at real scripts;
- every `${CLAUDE_PLUGIN_ROOT}/…` and `references/…` path a skill names existing on disk;
- the helper and hook scripts being bash with LF endings;
- the ten stage doctrine files;
- seat docs opening with the `# Title` that workers echo, and numbering principles "Principle N";
- the helper, hook and scaffold scripts tracked in git as executable.

## 2. Structural evals — is the design intact? (blocking)

```bash
python evals/run_structural.py
```

Checks:
- the kernel's eleven laws and its stage index;
- each stage's doctrine handing off to the next;
- every `council …` command a text mentions existing in the helper;
- the modes' `## At <Stage>` sections and deliverable paths;
- the agents' contracts and the hooks' wiring;
- the templates' schemas and the catalog;
- size budgets that keep skills whole after compaction;
- bash 3.2 portability;
- the rename;
- version agreement across plugin.json, the CHANGELOG and the helper;
- the behavioural suite's cases: a prompt and a grader each, scaffolds that exist, tools the graders
  count that the run can call, regexes that compile, near-misses that can't pass on a dead run.

## 3. Helper evals — does `bin/council` do its job?

```bash
python evals/run_cli.py        # needs bash + git
```

Runs the helper against scaffolded git repos:
- the council home, from the main checkout, a worktree, and outside git;
- opening, updating and closing runs: a second in-progress run refused without `--alongside`,
  commands that never guess between runs, paused runs, session ids, init creating the home;
- the change index: files, symbols (code only), callers, tests;
- gates judged by exit code (optional vs mandatory), with commands passed intact; a project with
  nothing configured, or nothing that can run at a stage, reported as NOTHING WAS CHECKED and never
  as a pass; the verdict line's pass, FAIL and skipped counts;
- seat-file collection: `ref:` proof of reading (paired seats too), item caps, broken citations,
  empty or unreadable indexes, failed and re-dispatched workers;
- citation and origin checks: single lines, ranges and comma lists of both; introduced vs
  pre-existing;
- gate side effects: what `--all` never runs;
- the stack fingerprint, scoped memory and stale anchors (line lists too), earlier council work,
  the seat ledger;
- the user's request: filing it word for word and out of git, redaction, continuing it, the quote
  check; a war room's round-2 files; post-game runs without a council home;
- a build's proof: a before-check that really failed, an after-check that really passed, whether a
  test was left behind in the project, and the warning when a build log never says what it traded
  away;
- map status and the drift doctor (cards, repeated slugs, a changed stack).

## 4. Hook evals — do the hooks behave?

```bash
python evals/run_hook.py       # needs bash + git
```

**SessionStart:**
- silent outside council projects;
- orients council projects;
- finds several open runs by scanning;
- after a compaction, says "resume, don't restart" for this session's run only;
- handles paused runs, runs in other worktrees, legacy runs, stale maps and garbage input.

**SubagentStop seat check:**
- valid files pass;
- a missing, malformed, empty or oversized file is blocked, but only once;
- other agents are never touched.

## 5. Phrase checks — advisory

```bash
python evals/run_phrases.py
```

Looks for the wording of the field-tested rules and warns if one is missing. It never fails: a
reworded rule shouldn't break the build, and a phrase proves nothing about behaviour.

## 6. Behavioural suite — runs Claude for real, so it costs tokens

`evals/suite/` holds cases for `claude plugin eval` (plugin.json → `experimental.evals`). Each case runs
with and without the plugin, and the report shows what the plugin adds (Δ). Graders are the answer
keys; the agent under test can't read them.

| Tag | Cases | What they check | Cost |
|---|---|---|---|
| triggering, near-miss | `trigger-review`, `trigger-plan`, `trigger-research`, `trigger-postgame`, `near-miss-question`, `near-miss-small-edit`, `near-miss-postgame` | the right mode starts; none starts for a question, a one-line edit in a council project, or a git question that sounds like "are we done?" — and the ask still gets handled | cheap — a few turns each |
| postgame | `postgame-seeded-gap` | a finished build whose plan dropped part of the request: the gap is found and blamed on planning, only blind verifiers check the code, nothing unasked is proposed | high |
| war-room | `plan-war-room-proposal` | "debate it" stays in council-plan, names the war room and its cost, and dispatches nothing before the go | moderate |
| sizing | `propose-small-change`, `propose-risky-change` | a right-sized proposal, seats not going with reasons, nothing dispatched before the go-ahead | moderate |
| dispatch | `squad-review-dispatch` | a `/council-review` inside the approved size runs end to end: 2–4 workers, a blind verifier for the auth bypass, the bypass in the deliverable | the priciest |
| fixture | `seeded-review-solo` | recall (the planted bug) and precision (the accepted pattern left alone), in the reply and in the deliverable | high |
| calibration | `verifier-calibration` | the verifier's verdicts on two true and two false claims, from a blind dispatch | moderate |
| resume | `resume-unfinished-run` | an open run is offered for resume; no seat is dispatched again | moderate |
| adaptation | `init-godot-roster` | council-init fits a non-web stack and asks before writing | moderate |

```bash
claude plugin eval . --model claude-opus-5 --scaffold --ablation none --runs 1 --tag triggering   # a quick smoke — no shell needed
claude plugin eval . --model claude-opus-5 --scaffold --max-cost-usd 40 --allow-tools Bash Write   # the whole suite — WSL2, macOS or Linux
python evals/record_eval.py                                                                       # add the run to evals/history/ and compare
```

- **Credentials:** every case runs in a fresh `claude -p` child with a throwaway config, so your normal
  sign-in doesn't reach it. Give it one in the environment you run from: `CLAUDE_CODE_OAUTH_TOKEN`
  (from `claude setup-token` — it draws on your Claude subscription's usage, no separate bill), or
  `ANTHROPIC_API_KEY` (billed per token). In CI, add either as a repository secret. Without one, every
  run errors ("Not logged in") and `record_eval.py` refuses to record the result.
- **Cost:** `--max-cost-usd` is a stop switch, not a charge: once the run's list-price estimate passes
  it, no further case starts (and the partial result isn't recorded). With a subscription token the
  runs draw on your plan's usage rather than a bill. A default full run is 84 sessions (42 per arm);
  `--runs 1` makes it 32.
- **The shell sandbox:** every case past the smoke runs the `council` helper, so it needs
  `--allow-tools Bash Write`, and Claude Code runs granted Bash only inside its OS sandbox. Native
  Windows has none, so there every such run is refused. Run the whole suite under WSL2, on macOS, on
  Linux with `bubblewrap` and `socat` installed, or in CI.
- **The war room's round 2** has no suite case: an eval run can't grant SendMessage, which resuming a
  seat needs. Drill D18 covers it.
- **Scaffold scripts** (`evals/suite/*/scaffold.sh`) build each case's fixture repo and run as you,
  only with `--scaffold`. They're self-contained; read them before trusting them.
- **History:** raw runs land in `evals/suite/results/` (untracked). `record_eval.py` keeps one small
  summary per recorded run in `evals/history/`, named by the run's start and the plugin version it
  loaded. It compares with the newest earlier clean entry of the same shape — same `--ablation`, same
  `--tag` filters — and exits 1 when a case's score drops by more than 0.1. It refuses partial runs
  and runs that errored; runs that only hit their turn or time cap are recorded and counted as capped.
- **CI:** `.github/workflows/evals.yml` runs on demand only: Claude Code and both models pinned, the
  Bash sandbox installed, Bash granted only past the triggering smoke, and a cost ceiling.

## 7. Behavioral drills — run in Claude Code

See `behavioral-drills.md` (D1–D26). They need a live agent and subagents, so they can't be scripted
here. `fixtures/` holds the seeds for D3, D4 and D9.
