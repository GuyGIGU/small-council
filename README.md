# Ultra Council

**A context-engineering pipeline for Claude Code, with a multi-expert council that tailors itself to your repo.**

Most "skill packs" are a library of prompts you copy into a project and hand-edit. Ultra Council is
different in two ways:

1. **One shared pipeline.** Every mode — code review, planning, implementation, spec-writing, test
   design — runs on the same context-handling core (`context-core`). Map the territory, write one
   edge-ordered brief, dispatch isolated workers with just-in-time references, aggregate before you
   judge, verify against reality, and remember what was settled. Improve the pipeline once and every
   mode gets better.
2. **Per-project auto-tailoring.** You install the skills once. Then `council-init` reads *your* repo,
   detects the stack and the real check commands, recasts the expert roster to fit, and writes a
   `.council/council.config.md`. One install behaves like a bespoke council per project — no forking,
   no hand-editing personas.

## The 8 skills

| Skill | Role |
|---|---|
| **context-core** | The reusable context-handling pipeline (phases 1–10) that every other mode runs on. Not usually invoked on its own. |
| **using-council** | Session bootstrap — keeps the council active at session start and re-establishes the method after a context compaction. |
| **council-init** | Run once per repo: detects the stack and gates, recasts the expert roster, writes `.council/council.config.md`. |
| **council-review** | Multi-expert code review; merges each expert's isolated pass into prioritised P1/P2/P3 findings. |
| **council-plan** | Interactive feature discovery → parallel expert fan-out → a sequenced, attributed implementation plan (no code). |
| **council-implement** | Executes a council plan task by task, loading the relevant expert's reference per task and running the gates between tasks. |
| **spec-writer** | Writes structured, adaptive-complexity specs — Job Stories, Gherkin acceptance criteria, three-tier boundaries. |
| **test-architect** | Audits existing tests for quality and specifies shortcut-proof test suites (Carmack × Beck). |

## How it fits together

```
install context-core + using-council   (once, globally)
        │
        ▼
run council-init                        (once per repo → writes .council/council.config.md)
        │
        ▼
use the modes                           (council-review / council-plan / council-implement / …)
   modes read .council/council.config.md → tailored roster, seat→reference map, and gates
```

- **context-core** owns the pipeline; a **mode** is a thin skill that hands the core five inputs
  (personas + reference docs, output schema, gates, memory namespace, synthesis cap).
- **council-init** produces the per-project `.council/council.config.md`. If it is present, every mode
  uses *its* roster and gates; if not, modes fall back to a generic default roster.
- **Memory** lives in a `conventions.md` at the project root (accepted patterns / enforced
  conventions), read before a run and updated after — so the council stops re-flagging what you've
  already decided.

## Quickstart

Prerequisites: **Claude Code**, plus **bash** and **python3** to build the packages. On Windows, use
**Git Bash** (ships with Git for Windows) — it provides both `bash` and `python3`.

```bash
git clone <your-repo-url> ultra-council
cd ultra-council

# 1) validate + package every skill into dist/*.skill
bash scripts/build.sh

# 2) install the packages via Claude Code's skill install (start with these two)
#      dist/context-core.skill
#      dist/using-council.skill
#    then the modes you want (council-review, council-plan, …)

# 3) run council-init ONCE in each project you want a council for
#      → writes <project>/.council/council.config.md

# 4) use the modes — e.g. ask for a "council review", or run /council-plan
```

The reference docs are committed to this repo, so a fresh clone builds with no network step.

> **Optional — refresh the domain docs from upstream.** `scripts/fetch-references.sh` re-pulls the
> canonical domain references from the upstream Carmack-Council repo, **overwriting your local
> copies**. You do not need it for a normal build; run it only when you want to re-sync the committed
> docs with upstream.

## Repo layout

```
council/
├── README.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── CHANGELOG.md
├── LICENSE                       # MIT
├── NOTICE                        # attribution to Carmack-Council
├── .gitattributes                # eol=lf so builds are byte-identical
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml                # runs the evals on ubuntu + windows
├── skills/                       # the 8 skills, each = SKILL.md + manifest.json
│   ├── context-core/             #   the pipeline
│   ├── using-council/            #   session bootstrap
│   ├── council-init/             #   per-project tailoring
│   ├── council-review/           #   review mode
│   ├── council-plan/             #   planning mode
│   ├── council-implement/        #   implementation mode
│   ├── spec-writer/              #   spec mode
│   └── test-architect/           #   test mode
├── references/                   # shared reference docs, bundled into skills at build
│   ├── context-engineering.md    #   the context-core doctrine
│   ├── security.md refactoring.md quality-*.md   #   domain expert docs
│   ├── feature-spec.md product-spec.md anti-patterns.md …   #   spec-writer docs
│   └── roster/
│       └── expert-catalog.md     #   seats + "applies when" + recast rules (council-init)
├── scripts/
│   ├── build.sh                  # validate + package → dist/*.skill
│   ├── quick_validate.py         # hard-fails a build with a broken skill/manifest/ref
│   ├── package_skill.py          # zips one skill + its declared references (LF-normalised)
│   └── fetch-references.sh       # OPTIONAL: refresh domain docs from upstream
├── evals/
│   ├── run_structural.py         # framework invariants, no LLM
│   ├── run_package.py            # every skill packages into a valid, safe .skill
│   ├── behavioral-drills.md      # live-agent drills (run in Claude Code)
│   └── fixtures/
├── examples/
│   ├── README.md
│   └── chrollo/
│       └── council.config.md     # illustrative council-init output
└── dist/                         # built .skill packages (git-ignored)
```

## Attribution

Ultra Council is a derivative work of **[Carmack-Council](https://github.com/SamJHudson01/Carmack-Council)**
by **Sam Hudson**, released under the MIT License. It keeps the named-expert council idea and several
of the domain reference documents, and adds the `context-core` pipeline, per-project auto-tailoring
(`council-init`), the session bootstrap (`using-council`), and the evals harness. See
[`NOTICE`](NOTICE) for the full statement of what is derived and what is new.

## License

MIT — see [`LICENSE`](LICENSE). The domain reference documents that originate from Carmack-Council
remain under its MIT license, preserved in `LICENSE` as the terms require.
