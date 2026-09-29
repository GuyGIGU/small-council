# Small Council

**A context-engineering council for Claude Code.** Named expert seats review, plan, build, and
research in isolated context windows; a blind verifier checks their work against the real code; and
your project keeps a durable memory and codebase map, so every session starts where the last one
ended.

It's built on one idea: **context is the scarce resource.** A single agent that reads everything
drowns, because accuracy falls as the context grows. The council's Chair maps instead of ingesting,
hands each expert one slice and one reference doc in a clean window, and judges what comes back.
Everything durable lives on disk, and everything mechanical is done by a script, so nothing gets
skipped under load.

## What you get

| Skill | What it does |
|---|---|
| `council-init` | Summons the council for a repo: detects the stack, recruits and recasts the expert roster (with the paths each seat watches), writes each seat a card that translates its doctrine to your project, dry-runs the real check commands and records their side effects, **lists the checks your project is missing** — formatter, linter, type check, test runner, dependency audit — builds the codebase map, writes `.council/`. Once per repo, and again when the stack moves. |
| `council-review` | Multi-expert code review → verified P1/P2/P3 findings → fix hand-off. |
| `council-plan` | Scoping conversation → expert advice → a plan built as vertical slices, each task saying what it touches and how to tell it's done. For a big or tough feature — or when you say "debate it" — a **war room** first: the experts read each other's proposals and argue them out with evidence, and you rule on the real forks. |
| `council-implement` | Builds a plan, fixes a review's findings, or finishes a post-game's next tasks, task by task: a saved test as before-and-after evidence, gates after every change, a verifier on every result, a converge pass at the end — and the same six-line receipt every time, shortcuts included. |
| `council-research` | Answers a question with graded evidence from code, history, docs and the web; saves the answer as project knowledge; keeps the map true. |
| `council-postgame` | After the work: checks what was built against your original request, word for word — what matches, what drifted, what's missing — and hands the next move to plan or implement. Offered after a build when it's worth it; works on work done without the council too. |
| `spec-writer` | Short, structured specs: Job Stories, Gherkin acceptance criteria, three-tier boundaries. |
| `test-architect` | Audits tests for theatre, specifies shortcut-proof suites, fixes weak tests (Carmack × Beck). |
| `context-core` | The engine every council mode runs on: the laws, the ten stages, the helper. The modes invoke it; you don't. |

**Supporting pieces:**
- **Two agents.**
  - **`council-worker`**: one seat, one slice, read-only; it returns one line.
  - **`council-verifier`**: blind and adversarial — CONFIRMED / REFUTED / UNCERTAIN / MISCITED for
    claims, OK / INCOMPLETE / REGRESSION / SCOPE-CREEP for changes.
- **The `council` helper** (bash + git, on PATH while the plugin is enabled). It does the
  bookkeeping: opening and closing runs, validating the run plan before fan-out, the change index,
  optional seat-specific context packs (`council context build <seat>`), gates judged by exit code, checking seat
  files and citations, an optional evidence ledger (`council evidence build|check`) linking claims
  to their sources and verifier rows, a bounded repair trail (`council repair record|show|check`) for
  failed build gates, the memory entries in scope — an observed failure only while the evidence it
  cites still shows it — and memory proposals drafted from a run's verified record, filed only with
  the user's own words (`council memory propose|accept|reject`), earlier council work on the same
  files, each seat's track record (the ledger) and how much it can support (`council ledger advice`:
  advice only past a stated bar), history across runs (`council history`: a rate only once five
  runs carry its data), conservative tuning (`council tune`: the estimate per worker from your own
  runs, changed only on your words and undoable; behaviour held until a benchmark shows it helps),
  and finding follow-up (`council outcomes`: whether cited lines changed after a closed run; timing
  does not establish cause),
  the stack fingerprint, a drift doctor, a plain-language status for a run (`council status`: a
  snapshot card in chat where the app can show one, text elsewhere), and a read-only run cockpit
  (`council tui --watch`) you can leave open in a terminal while a council works.
- **Fourteen expert seats** in the catalog, each with a doc that says how to apply it to any stack:
  security, structure, tests, frontend, backend, data integrity, performance, LLM pipelines, UI, UX,
  accessibility, concurrency, untrusted input and operability — recast or dropped per project.
- **Two hooks.**
  - **SessionStart**: orients council-enabled sessions, lists open runs, and after a compaction says
    "resume from disk, don't restart". It prints nothing in other projects.
  - **SubagentStop**: a council agent can't finish without the file its contract requires.

## Install

In Claude Code:

```
/plugin marketplace add GuyGIGU/small-council
/plugin install small-council@small-council
```

Then, in each project you want a council for, run **`/council-init`**.

**Working on the plugin itself?** Either:
- load your checkout with `claude --plugin-dir <path-to-repo>`, and run `/reload-plugins` after edits; or
- put the repo, or a directory junction to it, at `~/.claude/skills/small-council/`. Claude Code then
  loads it automatically as `small-council@skills-dir`.

**Upgrading from 0.6:** run a council-init refresh in each project, for two reasons. It lists the
checks the project is missing (nothing is installed without a yes). And it replaces the permission rule
earlier versions offered: `Bash(council *)` also covered `council gate <name> -- '<any command>'`,
which runs whatever it is given — so it allowed every command on the machine. The refresh reads your
settings, offers to replace that rule with a narrow list, and explains why the checks themselves keep
asking each time (say yes each time; never pick "don't ask again" for them). Reports on a project with no checks configured now
say NOTHING WAS CHECKED where they used to read clean.

**Upgrading from 0.5:** nothing to do — `.council/asks/` and `.council/postgames/` appear on first
use, and the first filed request adds `asks/` to `.council/.gitignore`, so your words stay on your
machine.

**Upgrading from 0.3:** run a council-init refresh in each project. It writes the seat cards, adds
Probe, Needs and Side effects to the gates, and records the stack fingerprint. Memory keeps working
as it is, and the refresh offers to add Scope and Anchor to existing entries.

**Upgrading from 0.2:** re-run `council-init` in each project. It adds the roster's Surface column and
the run preferences, and offers the helper's permission rule.

**Upgrading from Ultra Council 0.1** (standalone skills):
1. Remove the old copies from `~/.claude/skills/` so the skill list isn't doubled: `context-core`,
   `council-*`, `using-council`, `spec-writer`, `test-architect`.
2. Run `council-init` in each existing project. Old runs stay where they are.

## How the modes fit together

- **A new feature:** `spec-writer` (optional) → `council-plan` → `council-implement` →
  `council-postgame` (when offered) → `council-review` → `council-implement` in fix mode → …
- **"Did we build what I asked?"** `council-postgame`, on any finished work.
- **Unknown territory:** `council-research` first, then plan from its answer.
- **Tests:** `test-architect` — audit a suite, specify tests from a spec, or fix weak ones.

**Every multi-agent run is proposed first**, with its seats (and the seats not going), its size and
its estimated cost. A `/command` starts runs up to your approved size (default: Squad) straight away;
bigger runs always ask. After the go-ahead it runs to the deliverable on its own.

## What you see after every build

The same six lines, in the same order, whatever happened:

```
Built: 4 of 4 tasks — you can now export a report as CSV
Works?: ran `npm start` and exported a 12-row file; the 3 new tests pass
Checked by machine: gates: 3 ran — all pass (baseline: 1 FAIL)
Shortcuts I took: the export limit is hardcoded at 5,000 rows (src/export.ts) — streaming needs a design call
Not proved: nothing
Cost: helpers ~90k tokens across 3 agents; Chair usage unavailable · 2 of 2 fix(es) proved · 0 broken · 2 left a test behind · log: .council/logs/2026-09-16-csv.md
```

"Shortcuts I took" and "Not proved" are never left out — `none` and `nothing` are answers, silence
isn't — and every shortcut also lands in the log, which git keeps, so the pile stays visible months
later. A shortcut is defined rather than left to taste: a hardcoded value, a skipped case, a swallowed
error, a loosened check, a test that asserts less than the behaviour, a TODO, or a fix whose only proof
was a throwaway command.

## The checks behind a green report

A council report is only as honest as the commands behind it. With nothing configured to run,
`council gate --all` says **NOTHING WAS CHECKED** and fails — it never reports a pass when nothing ran.

`council-init` lists what your project is missing, one plain line each on what it would catch, and on
your yes writes a small plan that `council-implement` fits the same way it builds anything else. A
newly fitted linter or type checker judges **only the files a change touches** — including the code
just written and not yet committed — so it is green on day one and can only get stricter; the problems
that were already there are counted once and written down as "not yours". Every fitted check is proved
both ways before it counts: red on a deliberate mistake, green once it's fixed, because a check that
can only pass is worse than none. Nothing is installed without a yes, there is no commit hook, and
there is no coverage number to game. The per-stack commands live in `references/guardrails.md`.

## What a council run does

Each stage has its own short doctrine file, which the Chair reads as it enters that stage:

1. **Convene** — check open runs, check the work's shape, size the run, save your request word for
   word, and get the go-ahead.
2. **Prepare** — gather shared facts once: the map, memory in scope, the change index, earlier
   findings, grounding gates.
3. **Assign** — match each seat's surface markers to the change; pair thin seats; set budgets.
4. **Brief** — one set of orders on disk: the question at the top, the hard rules at the bottom;
   if the project opts in, build a plan-sized evidence pack for each selected seat.
5. **Work** — one isolated worker per seat, in parallel; each writes a file and returns one line.
6. **Collect** — the helper checks every seat file and its proof of reading; stuck workers are resumed.
7. **Judge** — a raw ledger of every finding before merging, a conflict pass, the cut — all written to
   `synthesis.md`.
8. **Challenge** — a mechanical citation check, then a blind verifier per serious finding.
9. **Deliver** — a tracked deliverable, a plain-language summary, the actual cost, then your rulings.
10. **Learn** — memory proposals with evidence (rejected ones never come back); each seat's record goes
    into the ledger; the run is closed.

**Limits:** at most 10 agents per run, verifiers included; a war room adds tokens, not agents. Past runs averaged ~100k tokens per worker;
estimates come from your own project's ledger once there is some.

**Seeing how a run is going.** In the Claude desktop app, the council shows a small status card in
the chat once, when it first sends out its experts: what is happening, whether it is moving, what
needs you, and — under "Details and evidence" — the seats, checks, cost and where the records are.
Ask "how's the council run going?" (or "council status") any time for a fresh card. A card is a
snapshot: it shows when it was taken, counts its age up in the page, and says so when it is over an
hour old; it never updates itself, and nothing on it can stop or change a run. Where the app can't
show cards, text provides the same reading (reported, not verified, for IDE extensions), ending
with the exact command for the live terminal view below. Cost appears only when the run's records
support it (see `references/run-accounting.md`). Both the card and text need optional Python 3.8+;
without Python, `council run status` gives the phase and cost line.

Two times show on every card:
- **the snapshot** — when the card was drawn, with its age counting up;
- **last activity** — the newest thing the run recorded.

If an open run has recorded nothing for an hour, the card says **No recent activity**. That can mean
a long job is still running, or that the session stopped; the card says both.

**Watching a run live.** In a terminal of your own, in the project, run the helper's cockpit. Outside
Claude Code the helper is not on your PATH, so give its full path: `bin/council` inside the plugin's
folder. For the `~/.claude/skills/small-council/` install described under Install, that is:

```bash
bash ~/.claude/skills/small-council/bin/council tui --watch
```

For a marketplace install, use the folder Claude Code installed the plugin into instead.

It redraws the plan, seats, gates, repairs, evidence and recent events every two seconds, and it
stops when the run closes. It only reads: leaving it open changes nothing. It needs Python 3.8+. Add
`--run <folder>` when more than one run is open. Set `COUNCIL_ASCII=1` if your console shows boxes
as garbage.

## Precision context (0.12)

After writing `<run>/brief.md`, `council context build <seat>` uses that selected seat's validated
`minimal`, `focused` or `full` run-plan level to build `<run>/contexts/<seat>.md`. The companion
`<seat>.md.metrics.tsv` accounts for what was included and omitted; `council context show <seat>`
prints both paths and the metrics. Repeated `--expand PATH` requests more evidence when inspection
shows a gap. This is an inspectable, optional selection aid, not a new dispatcher or a substitute for
the brief, reference docs, or project rules. Python 3.8+ is required only for building a pack; if it
is unavailable, the existing complete brief is the fallback. Packs are **off by default** until
their value is measured: set `- context packs: on` under `## Run preferences` in
`.council/council.config.md`, or ask for them in a run. See
[`references/precision-context.md`](references/precision-context.md) for the contract and limits.

## What it keeps in your repo

```
.council/
├── council.config.md     roster (with surface markers), gates, hard rules, run preferences    tracked
├── conventions.md        memory: accepted patterns, conventions, your decisions,              tracked
│                         scoped observed failures, proposals and rejected proposals
├── map.md                where things live, hot spots, vocabulary                             tracked
├── cards/<slug>.md       each seat's doctrine translated to this project                      tracked
├── ledger.tsv            each seat's record: items raised, kept, refuted, tokens per run      tracked
├── plans/ reviews/ logs/ research/ postgames/ refs/   deliverables · project-local seat docs tracked
├── asks/                 your requests, word for word; every deliverable points at its own    local
└── runs/<date-time>-<mode>/   state, run plan, events, brief, seat files, synthesis, checks     ignored
```

Your requests are yours: `asks/` is gitignored, so nothing you typed is committed — write `!asks/` in
place of that line if you'd rather your team saw them. (Since 0.7.1 a missing `asks/` line is put
back when a run opens, so that a fresh council home can't file your words into git by accident;
`!asks/` is how you say you meant it.)

The council home is always the **main** checkout's `.council/`, even when you work in a git worktree.
`council run status` shows open runs; `council doctor` finds anything that has drifted.
New runs also keep a versioned `events.tsv` for CLI actions. `council run events show` displays its
history and `council run events check` validates it; the [event contract](references/event-stream.md)
defines the rows for tools that read the file directly.

Before opening a run, `council route recommend --task "<work to do>"` gives an advisory council
size, risk/complexity/uncertainty assessment, seat archetypes, verification level and estimated
budget, with a reason for each choice. `--classic` shows the static baseline; explicit assessment,
surface and cap flags let you test a different shape. The command only prints a proposal: the Chair
maps archetypes to the project's real roster, makes any needed judgment calls, and records the final
choice in the checked run plan. See the [adaptive routing contract](references/adaptive-routing.md).

For a run with code changes, `council index` also builds `impact.tsv` when Python 3.8+ is available.
It separates changed files from direct static importers and likely tests, with confidence and scan
limits visible; `council impact` refreshes it after more edits. This is a scope aid, not proof of
runtime coverage or an automatic routing decision. The Bash/Git index still works without Python.
See the [impact graph contract](references/impact-graph.md).

## Repo layout

```
.claude-plugin/        plugin.json + marketplace.json (this repo is its own marketplace)
skills/                the nine skills
agents/                council-worker, council-verifier
hooks/                 hooks.json · session-start.sh · seat-gate.sh
bin/council            the helper
references/            stage doctrine · seat docs · spec and test docs · roster catalog · templates
evals/                 17 CI checks (see evals/README.md) · behavioral drills · benchmark and paid-suite fixtures
scripts/               quick_validate · impact · context · evidence · repair · memory · ledger · cockpit · status · history · tune
docs/design/           the design behind the current doctrine
docs/validation/       automatic checks, real-use evidence and limits
docs/roadmap-status.md implemented, tested, used and deferred work
examples/              an illustrative council-init output
```

## Development

```bash
python scripts/quick_validate.py   # will it load? manifests, frontmatter, paths, scripts, doctrine
python evals/run_structural.py     # is the design intact? laws, stages, commands, modes, budgets
python evals/run_cli.py            # does the helper work? (needs bash + git)
python evals/run_impact.py         # does the optional impact graph resolve direct relationships?
python evals/run_hook.py           # do the hooks behave? (needs bash + git)
python evals/run_status.py         # run accounting and the status widget (needs bash + git)
python evals/run_phrases.py        # advisory: are the field-tested rules still worded in?
```

These are selected local checks. The full 17-step list is in [CI](.github/workflows/ci.yml)
and [evals/README.md](evals/README.md), run on Ubuntu, Windows and macOS. Before a release:
- run the behavioral drills in [`evals/behavioral-drills.md`](evals/behavioral-drills.md);
- if you have the CLI, run `claude plugin validate . --strict`.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Attribution

Small Council (formerly Ultra Council) is a derivative work of
**[Carmack-Council](https://github.com/SamJHudson01/Carmack-Council)** by **Sam Hudson** (MIT).
- **It keeps** the named-expert council and several reference documents.
- **It adds:**
  - the context-core engine and its stage doctrine;
  - per-project tailoring;
  - the codebase map and memory;
  - the worker and verifier agents;
  - the helper and the hooks;
  - council-research;
  - the evals.

See [`NOTICE`](NOTICE).

## License

MIT — see [`LICENSE`](LICENSE).
