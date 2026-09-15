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
| `council-init` | Summons the council for a repo: detects the stack, recruits and recasts the expert roster (with the paths each seat watches), writes each seat a card that translates its doctrine to your project, dry-runs the real check commands and records their side effects, builds the codebase map, writes `.council/`. Once per repo, and again when the stack moves. |
| `council-review` | Multi-expert code review → verified P1/P2/P3 findings → fix hand-off. |
| `council-plan` | Scoping conversation → expert advice → a plan built as vertical slices, each task saying what it touches and how to tell it's done. |
| `council-implement` | Builds a plan, or fixes a review's findings, task by task: before-and-after evidence, gates after every change, a verifier on every result, a converge pass at the end. |
| `council-research` | Answers a question with graded evidence from code, history, docs and the web; saves the answer as project knowledge; keeps the map true. |
| `spec-writer` | Short, structured specs: Job Stories, Gherkin acceptance criteria, three-tier boundaries. |
| `test-architect` | Audits tests for theatre, specifies shortcut-proof suites, fixes weak tests (Carmack × Beck). |
| `context-core` | The engine every council mode runs on: the laws, the ten stages, the helper. The modes invoke it; you don't. |

**Supporting pieces:**
- **Two agents.**
  - **`council-worker`**: one seat, one slice, read-only; it returns one line.
  - **`council-verifier`**: blind and adversarial — CONFIRMED / REFUTED / UNCERTAIN / MISCITED for
    claims, OK / INCOMPLETE / REGRESSION / SCOPE-CREEP for changes.
- **The `council` helper** (bash + git, on PATH while the plugin is enabled). It does the
  bookkeeping: opening and closing runs, the change index, gates judged by exit code, checking seat
  files and citations, the memory entries in scope, earlier council work on the same files, each
  seat's track record (the ledger), the stack fingerprint, and a drift doctor.
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
  `council-review` → `council-implement` in fix mode → …
- **Unknown territory:** `council-research` first, then plan from its answer.
- **Tests:** `test-architect` — audit a suite, specify tests from a spec, or fix weak ones.

**Every multi-agent run is proposed first**, with its seats (and the seats not going), its size and
its estimated cost. A `/command` starts runs up to your approved size (default: Squad) straight away;
bigger runs always ask. After the go-ahead it runs to the deliverable on its own.

## What a council run does

Each stage has its own short doctrine file, which the Chair reads as it enters that stage:

1. **Convene** — check open runs, check the work's shape, size the run, and get the go-ahead.
2. **Prepare** — gather shared facts once: the map, memory in scope, the change index, earlier
   findings, grounding gates.
3. **Assign** — match each seat's surface markers to the change; pair thin seats; set budgets.
4. **Brief** — one set of orders on disk: the question at the top, the hard rules at the bottom.
5. **Work** — one isolated worker per seat, in parallel; each writes a file and returns one line.
6. **Collect** — the helper checks every seat file and its proof of reading; stuck workers are resumed.
7. **Judge** — a raw ledger of every finding before merging, a conflict pass, the cut — all written to
   `synthesis.md`.
8. **Challenge** — a mechanical citation check, then a blind verifier per serious finding.
9. **Deliver** — a tracked deliverable, a plain-language summary, the actual cost, then your rulings.
10. **Learn** — memory proposals with evidence (rejected ones never come back); each seat's record goes
    into the ledger; the run is closed.

**Limits:** at most 10 agents per run, verifiers included. Past runs averaged ~100k tokens per worker;
estimates come from your own project's ledger once there is some.

## What it keeps in your repo

```
.council/
├── council.config.md     roster (with surface markers), gates, hard rules, run preferences    tracked
├── conventions.md        memory: accepted patterns, conventions, your decisions,              tracked
│                         proposals awaiting your yes/no, and rejected proposals
├── map.md                where things live, hot spots, vocabulary                             tracked
├── cards/<slug>.md       each seat's doctrine translated to this project                      tracked
├── ledger.tsv            each seat's record: items raised, kept, refuted, tokens per run      tracked
├── plans/ reviews/ logs/ research/ refs/     deliverables · project-local seat docs          tracked
└── runs/<date-time>-<mode>/   state, brief, change index, seat files, synthesis, checks       ignored
```

The council home is always the **main** checkout's `.council/`, even when you work in a git worktree.
`council run status` shows open runs; `council doctor` finds anything that has drifted.

## Repo layout

```
.claude-plugin/        plugin.json + marketplace.json (this repo is its own marketplace)
skills/                the eight skills
agents/                council-worker, council-verifier
hooks/                 hooks.json · session-start.sh · seat-gate.sh
bin/council            the helper
references/            stage doctrine · seat docs · spec and test docs · roster catalog · templates
evals/                 run_structural · run_cli · run_hook · run_phrases · behavioral-drills · fixtures
scripts/               quick_validate.py
docs/design/           the design behind the current doctrine
examples/              an illustrative council-init output
```

## Development

```bash
python scripts/quick_validate.py   # will it load? manifests, frontmatter, paths, scripts, doctrine
python evals/run_structural.py     # is the design intact? laws, stages, commands, modes, budgets
python evals/run_cli.py            # does the helper work? (needs bash + git)
python evals/run_hook.py           # do the hooks behave? (needs bash + git)
python evals/run_phrases.py        # advisory: are the field-tested rules still worded in?
```

CI runs all of them on Ubuntu and Windows. Before a release:
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
