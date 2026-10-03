# Small Council

**TL;DR:** a team of expert reviewers for Claude Code. Each expert works in its own clean context,
a blind checker tests their claims against the real code, and your project keeps a memory and a
map, so the next session starts where this one ended.

## Install

```
/plugin marketplace add GuyGIGU/small-council
/plugin install small-council@small-council
```

Then run **`/council-init`** once in each project.

## Update

- **The plugin:** `/plugin` → Installed → small-council → Update now, then `/reload-plugins`.
  Or `claude plugin update small-council@small-council`.
- **Your projects:** nothing to re-run. `council doctor` tells you when a project needs a
  `/council-init` refresh (a changed stack, an older setup), and so do the release notes in
  [CHANGELOG.md](CHANGELOG.md).
- **On a version before 0.7?** Run a `/council-init` refresh in each project.

## Use

| Command | What you get |
|---|---|
| `/council-init` | Sets the council up: picks the experts for your stack, lists the checks you're missing, maps the code, writes `.council/`. |
| `/council-plan` | A plan in small, checkable tasks. Say "debate it" to have the experts argue the hard calls first. |
| `/council-implement` | Builds a plan or fixes review findings, with proof for each task and a blind check of every result. |
| `/council-review` | Verified findings, ranked P1/P2/P3, handed to implement for fixing. |
| `/council-research` | An answer backed by graded evidence, saved for next time. |
| `/council-postgame` | "Did we build what I asked?" — matches, drift and gaps. |
| `/spec-writer` | A short spec: job stories, acceptance criteria, boundaries. |
| `/test-architect` | Finds tests that only look like tests, and fixes them. |

**Typical flow:** plan → implement → postgame → review → implement (fixes).

**You stay in control.** Every multi-agent run is proposed first with its size and cost, and
waits for your go. At most 10 agents per run.

## After every build: six lines

```
Built: 4 of 4 tasks — you can now export a report as CSV
Works?: ran `npm start` and exported a 12-row file; the 3 new tests pass
Checked by machine: gates: 3 ran — all pass (baseline: 1 FAIL)
Shortcuts I took: the export limit is hardcoded at 5,000 rows (src/export.ts) — streaming needs a design call
Not proved: nothing
Cost: helpers ~90k tokens across 3 agents; Chair usage unavailable · 2 of 2 fix(es) proved · 0 broken · log: .council/logs/2026-09-16-csv.md
```

"Shortcuts" and "Not proved" are never skipped: `none` is an answer, silence isn't.

## Good to know

- **No fake passes.** With no checks set up, reports say **NOTHING WAS CHECKED**. Init offers the
  missing ones (linter, tests, type check…) and installs nothing without your yes.
- **Shared repo?** Pick **just me** at setup (or `council sharing just-me`): the council stays out
  of git, CLAUDE.md and your commit messages. Teammates never see it.
- **Your words stay private.** Your requests are saved in `.council/asks/`, which git ignores.
- **How's it going?** Ask "council status" for a status card in chat. For a live view in your own
  terminal: `bash <plugin folder>/bin/council tui --watch`. Ask for "the pet" for a desktop ghost
  that follows the run.
- **Something off?** `council doctor` finds drift and says how to fix each item.
- Status card, live view and pet need Python 3.8+.

## What it keeps in your repo

```
.council/
├── council.config.md   experts, checks, rules, preferences      tracked
├── conventions.md      memory: your decisions and patterns       tracked
├── map.md              where things live                         tracked
├── cards/  ledger.tsv  each expert's brief and track record      tracked
├── plans/ reviews/ logs/ research/ postgames/                    tracked
├── asks/               your requests, word for word              local only
└── runs/               working files of each run                 local only
```

On **just me**, all of `.council/` is local only.

## Under the hood

Two agents (an expert worker and a blind verifier), a bash helper called `council` that does the
bookkeeping, four hooks that enforce limits and pick runs back up after a compaction, and fourteen
expert seats (security, tests, performance, UX and more), tailored to each project.

More: [helper commands](references/helper-commands.md) · [reference docs](references/README.md) ·
[sharing](references/sharing.md) · [checks](references/guardrails.md) ·
[what's built and tested](docs/roadmap-status.md) · [CHANGELOG](CHANGELOG.md)

## Development

```bash
python evals/run_all.py   # every suite CI runs (Ubuntu, Windows and macOS)
```

To load a local checkout: `claude --plugin-dir <repo>`, or put the repo (or a junction to it) at
`~/.claude/skills/small-council/`. Details: [CONTRIBUTING.md](CONTRIBUTING.md),
[evals/README.md](evals/README.md).

## Credit and license

Derived from **[Carmack-Council](https://github.com/SamJHudson01/Carmack-Council)** by Sam Hudson
(MIT). See [NOTICE](NOTICE). MIT — see [LICENSE](LICENSE).
