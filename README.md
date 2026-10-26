# Small Council

**A council of expert reviewers for Claude Code, where every finding is proved before you see it.**

[![CI](https://github.com/GuyGIGU/small-council/actions/workflows/ci.yml/badge.svg)](https://github.com/GuyGIGU/small-council/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.23.0-black.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-black.svg)](LICENSE)
[![Any stack](https://img.shields.io/badge/stack-any-black.svg)](references/roster/expert-catalog.md)

Fourteen domain experts, each in a clean context, read your change through their own lens. A blind
checker then tests every claim against the real code. Nothing ships on a reviewer's word: in the last
three branch reviews, 37 of 38 shipped findings were confirmed blind, one was re-cited, and **none
were refuted**. Your project keeps a memory and a map, so the tenth run knows what the first one learned.

Forked from Sam Hudson's [Carmack Council](https://github.com/SamJHudson01/Carmack-Council), which
gave Claude Code ten named experts and a philosophy. Small Council keeps the experts and adds the part
that was missing: **proof**.

---

## Why this one

Most multi-agent review skills give you more opinions. Small Council gives you fewer, and stands
behind each one.

| | Small Council | A typical council skill |
|---|---|---|
| **Findings are verified** | A blind verifier re-checks every kept finding against the code, without seeing the reviewer's reasoning. Refuted findings never reach you. | Ten reviewers, merged and ranked. You find out which ones were wrong. |
| **Nothing fakes a pass** | No checks configured? The report says **NOTHING WAS CHECKED**, in those words. | "Tests pass" with no test runner in sight. |
| **Every run is sized and billed** | Proposed first with seats and cost. A hook stops new agents at the cap. Estimate before, actual after. | Spawn all ten, every time. |
| **Builds leave proof** | Each task records a check that failed before the change and passed after, saved to disk. The receipt lists every shortcut taken. | An implementation log. |
| **Your project remembers** | Decisions, accepted patterns and observed failures, each with its evidence. A codebase map. A track record per expert. | A conventions file. |
| **Any stack** | Setup detects your stack and recasts the roster: a Godot game, a Python trading engine and a Swift app each get the experts they need. | One stack, hardcoded. |

## Install

```
/plugin marketplace add GuyGIGU/small-council
/plugin install small-council@small-council
```

Then run **`/council-init`** once in each project. It picks your experts, finds the checks you have,
offers the ones you lack, maps the code and writes `.council/`. Nothing is installed without your yes.

## Use

| Command | What you get |
|---|---|
| `/council-review` | Verified findings, ranked P1/P2/P3, handed to implement for fixing. |
| `/council-plan` | A plan in small, checkable tasks. Say "debate it" to have the experts argue the hard calls first. |
| `/council-implement` | Builds a plan or fixes review findings, with proof for each task and a blind check of every result. |
| `/council-research` | An answer backed by graded evidence, saved for next time. |
| `/council-postgame` | "Did we build what I asked?" Matches, drift and gaps against your request, word for word. |
| `/council-init` | Sets the council up for a project, or refreshes it when the stack moves. |
| `/spec-writer` | A short spec: job stories, acceptance criteria, boundaries. |
| `/test-architect` | Finds tests that only look like tests, and fixes them. |

**Typical flow:** plan → implement → postgame → review → implement (fixes).

**You stay in control.** Every multi-agent run is proposed first with its size and cost, and waits
for your go. At most 10 agents per run unless you raise it. You can say "stop, give me what you have"
at any point.

## What a run gives you

After every build, the same six lines, in the same order, whatever happened:

```
Built: 4 of 4 tasks — you can now export a report as CSV
Works?: ran `npm start` and exported a 12-row file; the 3 new tests pass
Checked by machine: gates: 3 ran — all pass (baseline: 1 FAIL)
Shortcuts I took: the export limit is hardcoded at 5,000 rows (src/export.ts) — streaming needs a design call
Not proved: nothing
Cost: helpers ~90k tokens across 3 agents; Chair usage unavailable · 2 of 2 fix(es) proved · 0 broken · log: .council/logs/2026-09-16-csv.md
```

"Shortcuts" and "Not proved" are never skipped. `none` is an answer; silence isn't.

After every review: findings with a file and line, an evidence grade (observed, reproduced, inferred),
the verifier's verdict, and a fix line the implement mode can take as its task. Ask "council status"
at any time for a status card in chat, or open the live terminal view.

While a run is open, a pane beside the chat shows the council hall: each seat a small pixel-art
critter at its desk, wearing its role's gear (the builder's hard hat, the verifier's glasses),
working under a lit lamp, done with a hop, or asleep in the queue. A line above the prompt says the
stage, who is working and the spend. `/council-view` opens the pane again if you close it.

## How the proof works

1. **Parallel readers, one writer.** Experts read side by side in isolated contexts. One builder
   changes code.
2. **Gather once, share with everyone.** The Chair builds a change index, runs your checks and selects
   the memory in scope. Every expert gets the same brief.
3. **Aggregate, then judge, then challenge.** The Chair merges by root cause and cuts what doesn't
   matter at your scale. Then verifiers who never saw the reasoning re-check each kept claim and
   every cut P1, and return CONFIRMED, REFUTED, UNCERTAIN or MISCITED with `path:line` evidence.
4. **Evidence or it didn't happen.** A claim carries a citation the helper checks. "Done" carries a
   gate's output file and exit code. A builder's explanation is a claim, not evidence.
5. **The disk is the memory.** Every decision a later stage needs is written to a file first, so a
   compaction or a new session picks the run up where it stopped.

Independent research has since found the same shape: a critic forced to cite code evidence beats
both a single reviewer and a larger panel, while a critic that merely agrees makes things worse.

## The experts

Security (Troy Hunt) · Structure (Martin Fowler) · Tests (Kent Beck) · Frontend (Kent C. Dodds) ·
Backend (Matteo Collina) · Data integrity (Brandur Leach) · UI (Karri Saarinen) · UX (Vitaly Friedman) ·
Accessibility (Heydon Pickering) · Concurrency (Brian Goetz) · Untrusted input (Meredith Patterson) ·
Operability (Michael Nygard) · LLM pipelines (Simon Willison) · Performance.

Each seat is a reference document of that expert's published principles, with a section on applying
it to another stack. Setup recasts seats to your project and drops the ones with nothing to check:
a trading engine gets a numerical-correctness seat in Willison's chair; a game gets a charter seat.
John Carmack chairs: simplicity over cleverness, concrete over abstract, economic over aesthetic.
See the [expert catalog](references/roster/expert-catalog.md).

## Compared with the Carmack Council

The original is a sharp set of five prompt files, tuned to one person's Next.js stack. Small Council
is what it became after three months of real runs.

| | Carmack Council | Small Council |
|---|---|---|
| Skills | 5 | 8, on a shared engine with ten stages |
| Stack | Next.js / tRPC / Prisma, hardcoded | detected per project, 14 seats recast |
| Checks on findings | none | blind verifiers, citation check, evidence grades |
| Records | one output folder per review | runs, ledger, usage, memory, map, every request word for word |
| Cost control | none | caps, estimates, a hook that stops at the limit |
| Machinery | none | a 7,000-line helper, 4 hooks, 28 eval jobs on Windows, macOS and Linux |
| Shared repos | commits conventions.md | a "just me" mode that keeps the council out of git, CLAUDE.md and commit messages |

The principles are the same. The difference is that this one can tell you when it was wrong.

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

On **just me**, all of `.council/` stays local.

## Honest limits

- Whether the council beats plain Claude Code on the same task is not yet measured. The run records
  show value and friction; they don't prove a margin.
- Reviews are the strongest mode. Big builds have overrun their estimates, and a light build tier is
  being added so the process matches how people actually work.
- The Chair's own token use is not yet recorded, so every cost line is a floor.
- All verifiers run the same model family as the reviewers. A cross-model check is on the list.

## Good to know

- `council doctor` finds drift (a moved file, a check that can't run) and says how to fix each item.
- Your requests are saved in `.council/asks/`, which git ignores.
- The status card, live terminal view, council pane and desktop pet need Python 3.8+. Everything else
  is bash 3.2. The pane and the line above the prompt are a Claude Code mod (Claude Code 2.1.287 or
  later; the desktop app from 2.1.286): they show in the terminal, the desktop app and VS Code, and
  never in `claude -p`.
- Update the plugin from `/plugin` → Installed → small-council → Update now, then `/reload-plugins`.
  Your projects need nothing re-run; `council doctor` tells you when a refresh is due.

## Under the hood

Two agents (an expert worker and a blind verifier), a bash helper called `council` that does the
bookkeeping, four hooks that enforce limits and pick runs back up after a compaction, and fourteen
expert seats tailored to each project.

More: [helper commands](references/helper-commands.md) · [reference docs](references/README.md) ·
[sharing](references/sharing.md) · [checks](references/guardrails.md) ·
[what's built and tested](docs/roadmap-status.md) · [CHANGELOG](CHANGELOG.md)

## Development

```bash
python evals/run_all.py   # every suite CI runs (Ubuntu, Windows and macOS)
claude plugin test .      # the council pane's tests (hooks/council-view.tsx)
```

To load a local checkout: `claude --plugin-dir <repo>`, or put the repo (or a junction to it) at
`~/.claude/skills/small-council/`. Details: [CONTRIBUTING.md](CONTRIBUTING.md),
[evals/README.md](evals/README.md).

## Credit and license

Derived from **[Carmack-Council](https://github.com/SamJHudson01/Carmack-Council)** by Sam Hudson
(MIT). The council hall's pixel style and its robot, cat and dragon follow
**[agent-avatars](https://github.com/vanyastaff/agent-avatars)** by vanyastaff (MIT). See
[NOTICE](NOTICE). MIT — see [LICENSE](LICENSE).
