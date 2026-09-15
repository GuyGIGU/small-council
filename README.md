# Small Council

**A context-engineering council for Claude Code.** Named expert seats review, plan, build, and
research in isolated context windows; an adversarial verifier checks their work against the real code;
and your project keeps a durable memory and codebase map, so every session starts where the last one
ended.

It's built on one idea: **context is the scarce resource.** A single agent that reads everything
drowns — accuracy falls as the context grows. The council's Chair maps instead of ingesting, hands each
expert one slice and one reference doc in a clean window, and judges what comes back. Everything durable
lives on disk.

## What you get

| Skill | What it does |
|---|---|
| `council-init` | Tailors the council to a repo: detects the stack, recasts the expert roster, dry-runs the real check commands, builds the codebase map, writes `.council/`. Once per repo. |
| `council-review` | Multi-expert code review → verified P1/P2/P3 findings → fix hand-off. |
| `council-plan` | Scoping conversation → expert advice → a sequenced, attributed plan whose tasks each say how to tell they're done. |
| `council-implement` | Builds a plan, or fixes a review's findings, task by task — gates after every change, a verifier on every result, a running log. |
| `council-research` | Answers a question with graded evidence from code, history, docs, and the web; saves the answer as project knowledge; keeps the map true. |
| `spec-writer` | Short, structured specs — Job Stories, Gherkin acceptance criteria, three-tier boundaries. |
| `test-architect` | Audits tests for theatre, specifies shortcut-proof suites, fixes weak tests (Carmack × Beck). |
| `context-core` | The pipeline every council mode runs on. The modes invoke it; you don't. |

Plus two agents — **`council-worker`** (one seat, one slice, read-only, returns one line) and
**`council-verifier`** (adversarial: CONFIRMED / REFUTED / UNCERTAIN) — and a **SessionStart hook** that
orients council-enabled sessions, flags unfinished runs, and re-establishes the method after a
compaction. In projects without a council it prints nothing.

## Install

In Claude Code:

```
/plugin marketplace add GuyGIGU/small-council
/plugin install small-council@small-council
```

Then, in each project you want a council for, run **`/council-init`**.

**Working on the plugin itself?** Load your checkout with `claude --plugin-dir <path-to-repo>` and run
`/reload-plugins` after edits — or put the repo (or a directory junction to it) at
`~/.claude/skills/small-council/`, where Claude Code loads it automatically as `small-council@skills-dir`.

**Upgrading from Ultra Council 0.1** (standalone skills): remove the old copies from `~/.claude/skills/`
(`context-core`, `council-*`, `using-council`, `spec-writer`, `test-architect`) so the skill list isn't
doubled. Then run `council-init` in each existing project: it refreshes the config to the current
schema, migrates the `CLAUDE.md` block, adds `.council/.gitignore`, and builds the map. Old runs stay
where they are.

## How the modes fit together

- **A new feature:** `spec-writer` (optional) → `council-plan` → `council-implement` →
  `council-review` → `council-implement` in fix mode → …
- **Unknown territory:** `council-research` first, then plan from its answer.
- **Tests:** `test-architect` — audit a suite, specify tests from a spec, or fix weak ones.

Every multi-agent run is **proposed first**, with its size, seats, and estimated cost, and starts on
your go-ahead. From then on it runs to the deliverable by itself.

## What a council run does

1. **Scope & size** — the deliverable, the one question, what's out of scope; Solo, Squad, or Full,
   with the cost.
2. **Map** — config, memory, and the codebase map; refresh only what changed since the map's commit.
3. **Brief** — one brief on disk, with the question at the top and the hard rules at the bottom.
4. **Partition** — each seat gets only its slice; seats with nothing to look at are skipped, with the
   reason recorded.
5. **Dispatch** — one isolated worker per seat, in parallel; each writes a file and returns one line.
6. **Collect** — every seat file is present, with proof its reference doc was read.
7. **Synthesize** — aggregate everything before judging, dedupe by owner, cut to the cap.
8. **Verify** — gates judged by exit code; an adversarial verifier checks every item against the code.
9. **Deliver, remember, close** — the deliverable in a tracked file; memory proposals written down for
   your yes or no; the run marked complete.

**Cost:** real runs average **~100k tokens per worker** — a 7-worker run is about 0.75M tokens, a
14-worker run about 1.8M. Solo runs dispatch no workers; most reviews want a Squad.

## What it keeps in your repo

```
.council/
├── council.config.md     tailored roster, gates, hard rules                        tracked
├── conventions.md        memory: accepted patterns, conventions, your decisions,   tracked
│                         and proposals awaiting your yes/no
├── map.md                the codebase map every session orients from               tracked
├── plans/ reviews/ logs/ research/     deliverables                                tracked
├── runs/<date>-<mode>/   briefs, seat files, verification, run state               ignored
└── active-run            the run in flight, if any                                 ignored
```

The council home is always the **main** checkout's `.council/`, even when you work in a git worktree.

## Repo layout

```
.claude-plugin/        plugin.json + marketplace.json (this repo is its own marketplace)
skills/                the eight skills
agents/                council-worker, council-verifier
hooks/                 hooks.json + session-start.sh
references/            seat docs, spec and test docs, roster catalog, templates — shared by every skill
evals/                 run_structural.py · run_hook.py · behavioral-drills.md · fixtures/
scripts/               quick_validate.py
examples/              an illustrative council-init output
```

## Development

```bash
python scripts/quick_validate.py   # will it load? manifests, frontmatter, paths, hooks
python evals/run_structural.py     # is the method intact? phases, rules, budgets, paths
python evals/run_hook.py           # does the SessionStart hook behave? (needs bash + git)
```

CI runs all three on Ubuntu and Windows. Before a release, also run the behavioral drills in
[`evals/behavioral-drills.md`](evals/behavioral-drills.md) and, if you have the CLI,
`claude plugin validate . --strict`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Attribution

Small Council (formerly Ultra Council) is a derivative work of
**[Carmack-Council](https://github.com/SamJHudson01/Carmack-Council)** by **Sam Hudson** (MIT). It keeps
the named-expert council and several reference documents, and adds the context-core pipeline,
per-project tailoring, the codebase map and memory, the worker and verifier agents, the session hook,
council-research, and the evals. See [`NOTICE`](NOTICE).

## License

MIT — see [`LICENSE`](LICENSE).
