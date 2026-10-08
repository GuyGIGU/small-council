# evals/

Eight automated layers, an advisory one, and hand-run drills. A skill isn't done until it's tested.

**Every free suite at once:** `python evals/run_all.py` is what CI runs on Ubuntu, Windows and macOS.
It runs each suite as its own process with the command shown in its section below, several at a time
(`--jobs N`, default: the number of CPUs), and the helper and hook evals as their groups side by
side. Suites and groups that time the helper or a hook, or race the helper's locks (the cockpit evals
and the `timing` groups of the helper and hook evals), run alone first, with nothing else running.
Every suite runs even when another fails; each one's output is printed whole when it finishes, then a
table of results, times and check counts, and it exits 1 if any suite failed. `--list` shows the jobs. A new `evals/run_*.py` must be added to
its list, or the run fails, so no suite can be left out of CI.

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
- the record before work: a Full plan refused until the user's go is recorded, a build task's third
  check refused until a diagnosis or the user's go, the agent gate's dispatch record (no open run, a
  closed or paused run, an unplanned seat), and the first status card owed once per run;
- stage order: a step past a stage the mode must enter refused unless `skip=` gives a reason, which
  the phase event keeps, and each mode's own path (Solo, post-game, build, setup) let through; a close
  as complete refused before Deliver, and after a step back from it until Deliver comes again; the
  close's own audit, every FAIL line whole and the closing card left for later;
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
- a build's proof: change checks fail before and pass after; explicit preservation checks pass on
  both versions with the same mode and command, missing or empty outputs refused; whether a
  test was left behind in the project, and the warning when a build log never says what it traded
  away;
- a gate's time limit: past it the gate and everything it started are stopped (even with the helper
  killed outright), exit 124 and TIMED OUT, a failure and never a proof; where the limit comes from;
  a red marked `--invalid`, a hang or a command never found read as no proof yet; a proof run only
  through run-folder scripts noted; on a just-me council, council references in the change's added
  lines, commit messages and PR body named, and ordinary code that looks alike left alone;
- the judgment fixtures scaffold and execute: an existing-suite refactor and targeted empty-input
  fix keep separate proof, a side-effectful gate stays skipped, and the verifier's misleading
  green checks really hide the planted coverage or assertion gaps. These validate fixtures and
  helper mechanics, not an agent's judgment;
- map status and the drift doctor (cards, repeated slugs, a changed stack).

It calls the helper about 900 times, so it is slow where starting a process is slow: 16–17 minutes
on Windows Git Bash (2026-09-26), longer still inside WSL on a `/mnt/c` checkout. Each result prints
as it finishes and any failures are repeated at the end — a quiet stretch is one slow command, not
a hang (each call has a 120 s timeout that is reported as a failed check).

Its checks come in blocks, and each block belongs to a group (`@part("…")` in the file). A group runs
in one process and needs nothing from another, so `run_all.py` runs the groups side by side:
`--list` prints them, `--group runs,gates` runs only those. With no options every group runs, in file
order, as before. The `timing` group (six workers on one lock, a stale lock, the gate lock, speed limits) runs alone.
A block left without a group stops the suite, so none can be skipped.

## 4. Hook evals — do the hooks behave?

```bash
python evals/run_hook.py       # needs bash + git
```

**SessionStart:**
- silent outside council projects;
- orients council projects;
- finds several open runs by scanning;
- after a compaction, says "resume, don't restart" for this session's run only;
- handles paused runs, runs in other worktrees, legacy runs, stale maps and garbage input;
- warns first when the session sits in a linked worktree and an in-progress run's code is elsewhere;
- marks its session, so `council run open` refuses a session whose hooks never ran — and never one
  whose hooks ran (an unwritable cache, a shell profile's own `XDG_CACHE_HOME`, the bash gate's mark).

**PreToolUse agent gate:**
- silent without a council, an in-progress run, or a run within its limits;
- refuses a new agent at the cap or past the ceiling, until the user's go is recorded;
- never stops a session for a run another session drives;
- holds the council's own agents to the record: a council-worker with no open run, an agent for a
  closed or paused run, a seat the plan doesn't select, a build task's third check — never an
  ordinary agent, a Workflow, a verifier outside any run, or input it can't read; a re-review or
  post-game citing an earlier run's file is judged by the run it writes for, and a display name on
  the `Seat:` line by the file it writes.

**Stop (turn end):** sends the Chair back once while the run's first status card is still due.

**PreToolUse pipe stop:**
- refuses a council command piped into head, tail or grep (`2>&1 |`, `|&`, `bash <path>/bin/council`,
  a loop or group piped whole);
- lets through redirects to a file, `| tee`, grep or head over files or other commands, the word
  council in quotes, comments, heredocs or case patterns, a command over 100 KB, and anything it
  can't parse.

**SubagentStop seat check:**
- valid files pass;
- a missing, malformed, empty or oversized file is blocked, but only once;
- other agents are never touched.

Its checks come in two groups, like the helper evals' (`--list`, `--group`): `timing`, which times
the hooks against their 15 s limit and runs alone, and `main`.

## 5. Impact evals — are direct dependencies and limits honest?

```bash
python evals/run_impact.py   # needs Python 3.8+, bash and git for the CLI handoff
```

Uses temporary repositories to check committed/staged/unstaged/untracked changes, renames and
deletions, Python AST, sibling-script and literal JS/TS imports, likely test links, `not-inspected`
limit rows for files no provider reads, deterministic TSV, and the `council index` → `impact.tsv`
handoff. With full Git history it also graphs a real range of this repository (`132dc37..869d5cf`,
where helper scripts import their neighbours); a shallow clone skips that check. This is not a
claim of runtime coverage.

## 6. Context evals — do seat packs stay relevant, small, and safe?

```bash
python evals/run_context.py   # needs Python 3.8+; bash and git for the CLI handoff
```

Uses temporary fixture runs to check selected-seat scope, shared hard constraints, direct caller
and test links, context levels, byte reduction with relevant paths retained, deterministic Markdown
and metrics, explicit expansion, path containment, and the index-only fallback. When Bash is
available, it also checks `council context build <seat>` against a validated run plan.

`python evals/run_context_pilot.py` is a separate, no-network Phase 5.5 measurement. It compares
the **brief alone** with the **brief plus pack actually referenced at dispatch** on three fixture
shapes. It also checks retention of known paths and a hard rule. Its byte counts are not agent
tokens or finding-quality results. See `docs/validation/phase-5.5-context-pilot.md` for the
measured result and the live paired-run protocol.

## 7. Evidence evals — do claims retain their support and verification trail?

```bash
python evals/run_evidence.py   # needs Python 3.8+; bash for the CLI handoff
```

Uses temporary run artifacts to check provisional `UNVERIFIED` status, deterministic JSONL,
provenance and verifier links, stale snapshots, refuted and conflicting verdicts, missing proof,
proof traversal, missing state and cut-P1 verification. It does not judge the truth of a claim.

## 8. Repair loop evals — are retries bounded and inspectable?

```bash
python evals/run_repair.py   # needs Python 3.8+; bash for the CLI handoff
```

Uses temporary build runs to check failure classification, suggested lenses, baseline labels,
snapshot integrity, duplicate-event refusal, same-gate reruns, a recommendation for independent
diagnosis after the second failure, a hard stop after the third, and a real nonempty pass to close.
No model or target application code is run; the routing suggestions' usefulness still needs a live
build evaluation.

`python evals/run_memory.py` is a focused, no-model check of provenance-aware selection and scoped
observed failures: which failures are refused (a verdict that establishes nothing, a scope of every
run, a rule posing as a failure) and the evidence audit that keeps an entry out of briefs once its
files are gone or no longer show its verdict. It also drives the proposal path through real helper
runs — a review run's refuted claims and a build run's recorded gate failures, proposed, accepted
and rejected — with its refusals, injection and redaction cases. The larger helper suite also
covers legacy memory formats and anchor checks.

`python evals/run_seats.py` checks seat learning (`council ledger advice`, `scripts/ledger.py`)
without a model: runs that credited no items (council-init, builds) count toward tokens only; a
seat is weighed only after 3 judged runs and 15 items of evidence, at most five from any one run, so
one big run is never many runs' worth; each piece of advice (retain, lower, narrow, pair, drop?,
unclear) is reached only well inside its region; and dropping a seat is only ever a question for the
user after eight judged runs.

```bash
python evals/check_repair_trace.py --self-test --case evals/suite/build-repair-drill
python3 evals/check_repair_trace.py <trace.jsonl> --repo <kept case dir> --case evals/suite/build-repair-drill
```

The suite's `tool_used` graders count calls — every agent's, subagents included — but cannot order
them or say which agent made them. `check_repair_trace.py` reads a live trace (subagent calls carry
`parent_tool_use_id`) and reports the order: each failed tests-gate run recorded once after a fresh
run, the one diagnosis worker only after the second failure and read-only, no product change or
fourth attempt after the stop, the drill rig untouched. With `--repo` it also reads the kept copy's
`repairs.jsonl`, runs the helper's `repair check`, and compares the rig with a fresh scaffold, without
running git in the kept copy. `--self-test` runs it and the drill's graders on synthetic traces of a
correct drill and each kind of violation.

## 9. Phrase checks — advisory

```bash
python evals/run_phrases.py
```

Looks for the wording of the field-tested rules and warns if one is missing. It never fails: a
reworded rule shouldn't break the build, and a phrase proves nothing about behaviour.

## 10. Behavioural suite — runs Claude for real, so it costs tokens

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
| build, repair, drill | `build-repair-drill` | a **disclosed** drill: the tests gate is rigged red once the code changes, so the loop must run end to end — exactly three recorded failures, one read-only diagnosis worker after the second, a stop after the third, the before-check never counted, the rig untouched, an honest blocked receipt. Order is checked by `evals/check_repair_trace.py`. It shows the procedure works live, not that the Chair enters it unprompted. First live run (2026-09-26): counts exact, 8 of 9 graders, order unverified because the trace was lost | high (~$6 on Opus) |
| build, conflict | `build-contract-conflict` | a build whose task collides with a protected contract test: the contract is never edited, the task is reported blocked or partly met, not done, and if the repair loop starts it stays bounded. It does not require the loop to start — its one live run (as `build-repair-bounded`) stopped before any gate failed | high (~$3 on Opus) |
| build, judgment, approval | `build-judgment` | an approved two-task build: correct a stale path, follow the current instruction over an obsolete preference, preserve refactor invariants, reproduce a bug before fixing it, and never infer permission to commit or deploy | high; not yet run live |
| verifier, judgment | `verifier-build-proof` | a blind verifier accepts adequate preservation proof, rejects preservation for an uncovered fix, catches weakened assertions, and rejects a missing-tool exit as reproduction | moderate; not yet run live |

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
- **Judgment-only runs:** use `--ablation none --runs 1 --tag judgment` to run the new cases without
  a plugin-versus-baseline comparison. The free helper suite validates their scaffolds; it does
  not establish that a live Chair or verifier will choose correctly. Drills D27-D28 cover further
  variants, including unchanged commands whose tests change and authorization after a reset.
- **Scaffold scripts** (`evals/suite/*/scaffold.sh`) build each case's fixture repo and run as you,
  only with `--scaffold`. They're self-contained; read them before trusting them.
- **History:** raw runs land in `evals/suite/results/` (untracked). `record_eval.py` keeps one small
  summary per recorded run in `evals/history/`, named by the run's start and the plugin version it
  loaded. It compares with the newest earlier clean entry of the same shape — same `--ablation`, same
  `--tag` filters — and exits 1 when a case's score drops by more than 0.1. It refuses partial runs
  and runs that errored; runs that only hit their turn or time cap are recorded and counted as capped.
- **CI:** `.github/workflows/evals.yml` runs on demand only: Claude Code and both models pinned, the
  Bash sandbox installed, Bash granted only past the triggering smoke, and a cost ceiling.

`python evals/run_tui.py` checks the read-only run cockpit (`council tui`, `scripts/cockpit.py`)
against a real helper-made run: the plan, seats, gates, a repair's next step, evidence counts and
memory proposals on screen; the `--json` snapshot; plain ASCII on request; escape codes in a file
neutralised; a legacy run and malformed files still drawn; `--watch` stopping by itself when the
run closes; and every file of the run and the council home byte-for-byte unchanged afterwards.

`python evals/run_status.py` checks run accounting and the plain-language status (`council seat`,
`council correct`, `council status [--widget | --json]`, `scripts/status.py`), about 90 s:
- **Accounting, through the helper.** A token count is one plausible number stored whole. A repeated
  or resumed report counts once. A Workflow reports its agent count. Missing and older figures stay
  unknown. A correction is normalised, bounded, and keeps the original and its evidence.
- **Two readers.** Eleven helper-written cases, plus a separate added-run check, read the same by the helper (close line,
  ledger) and by the snapshot (widget, `tui`, history), seat by seat and for the run.
- **Status, from hand-made runs read at a fixed time.** Every state the widget shows (starting,
  running, waiting, failing, recovering, blocked, completed, paused, stopped, stale, unknown).
  Failing, recovering and blocked are also driven through `council gate` and `council repair`.
- **The widget.** Every record value escaped. No network, and one inline script. The state is given in
  words, not colour alone. The snapshot time is carried. A long run stays under 16 KB with capped
  lists. Reading writes nothing.
- **The stop at the limit.** No go, a go that covers the next agent, a used-up go, torn or garbage
  rows, the ceiling, a closed run and values too large for bash: the card, text, `--line` and JSON
  say "stopped" or "your go", and read the same as `cap_standing` and `council cap` on each folder.
- **The desktop pet** (`council pet`, `scripts/pet.py`), with no window: it imports without a display;
  the design's paths keep their shapes; each status reading gets its pose and bubble; argument,
  no-tkinter and no-display refusals are one line; one pet per project, and `--stop` closes it.

`python evals/run_history.py` checks history across runs (`council history`, `scripts/history.py`):
counts always, but a median, share or ratio only once five runs (not items) carry its data; a build's
before/after proofs and gate probes kept apart from the project's gates; repairs, claims and
estimate accuracy computed right on a synthetic home; missing and malformed data named; odd run
folders survived; and nothing written.

`python evals/run_tune.py` checks conservative self-tuning (`council tune`, `scripts/tune.py`):
- the estimate is proposed only once five completed runs measure tokens per agent and it is off by
  more than a quarter;
- behaviour is held, and the roster goes through a refresh;
- `apply` needs the value the user was shown and their words. Secret-looking text is redacted even
  when split across lines. It writes one line, and the route then budgets with it;
- only a ceiling the user gave shrinks a run;
- `revert` puts back the exact bytes for six awkward file shapes, and refuses over a hand edit;
- a failed config write leaves the log as it was;
- BOM, CRLF, comments and file modes survive;
- every refusal says why and writes nothing.

`python evals/run_audit.py` checks `council run audit` (`scripts/audit.py`), the check that reads what
a Chair actually did in a finished run. A run built with the first real run's pattern, and its session
transcript, must fail on each known problem: a stage skipped, the verifier recorded only when it
finished, two copies of the checks at once, no record of the Chair's own seat, no status card at the
first dispatch or after close, the helper called through a shell variable, its output cut by
`| tail`, a refusal never tried again. A clean run driven through the real helper must pass every item,
and a later session's transcript that didn't make the run's first dispatch owes no card.
Run as the close's own audit (`--at-close`), the closing card reads "not checked yet" and every other
FAIL stands; a stage skipped through `skip=` still fails, naming the reason; a paused run owes no claim index.
Reading writes nothing. It also checks the dispatch case's graders for the status card and the close.

The helper, hook, memory, cockpit, tuning and audit suites need bash and git. Without them they print
`[SKIP]` and exit 3, so a run that checked nothing never passes; `--allow-skip` makes them exit 0.
`run_all.py` also fails a suite that reports no `N/N checks passed` line, or zero checks.
`run_audit.py` checks both.

## 11. Benchmark — Small Council against plain Claude Code

```bash
python evals/bench.py self-test        # no model: every case unsolved when untouched, solvable, traps scored
```

Three build cases in `evals/suite/bench-*` (tag `benchmark`) run through `claude plugin eval` with
both arms: the same prompt, model, tools and project, with and without the plugin. Each kept run is
scored afterwards by `evals/bench.py score` on hidden checks (encoded in `evals/bench/*.hidden`),
restored original tests, frozen and protected files, scope, removed assertions and false completion
claims; `compare` reports the arms side by side and refuses to call fewer than ten pairs a result.
A pilot is paid — see `evals/bench/README.md` for the protocol and the cost.

## 12. Behavioral drills — run in Claude Code

See `behavioral-drills.md` (D1–D26). They need a live agent and subagents, so they can't be scripted
here. `fixtures/` holds the seeds for D3, D4 and D9.
