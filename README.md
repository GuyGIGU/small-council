# Small Council

**A council for Claude Code that reviews, plans and builds, where every finding is checked before you see it.**

[![CI](https://github.com/GuyGIGU/small-council/actions/workflows/ci.yml/badge.svg)](https://github.com/GuyGIGU/small-council/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-1.2.0-black.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-black.svg)](LICENSE)
[![Any stack](https://img.shields.io/badge/stack-any-black.svg)](references/roster/expert-catalog.md)

A review sends two agents at once: one reads your change against what it claims and traces its
callers, the other runs the project's checks on the old and the new version in a scratch copy. The
main session then checks every serious finding against the code before you see it, and a finding on a
sensitive subject also gets an independent check. Nothing reaches you on an agent's word. Your project
keeps a memory and a map, so the tenth run knows what the first one learned.

Forked from Sam Hudson's [Carmack Council](https://github.com/SamJHudson01/Carmack-Council), which
gave Claude Code ten named experts and a philosophy. Small Council keeps the experts and adds the part
that was missing: **proof**.

---

## Why this one

Most multi-agent review skills give you more opinions. Small Council gives you fewer, and stands
behind each one.

| | Small Council | A typical council skill |
|---|---|---|
| **Findings are verified** | The main session checks every serious finding against the code before you see it; a finding on a sensitive subject also gets an independent check that never saw the reviewer's reasoning. Refuted findings never reach you. | Ten reviewers, merged and ranked. You find out which ones were wrong. |
| **Nothing fakes a pass** | No checks configured? The report says **NOTHING WAS CHECKED**, in those words. | "Tests pass" with no test runner in sight. |
| **Every run is sized and billed** | Proposed first with seats and cost. A hook stops new agents at the cap. Estimate before, actual after. | Spawn all ten, every time. |
| **Builds leave proof** | Each task records a check that failed before the change and passed after, saved to disk. The receipt lists every shortcut taken. | An implementation log. |
| **Your project remembers** | Decisions, accepted patterns and observed failures, each with its evidence. A codebase map. A track record per expert. | A conventions file. |
| **Any stack** | Setup detects your stack and recasts the roster: a Godot game, a Python trading engine and a Swift app each get the experts they need. | One stack, hardcoded. |

## Quick start

**Needs:** Claude Code, git, bash (Git Bash on Windows) and **Python 3.8 or newer** on PATH. Every
`council` command runs in Python; without it each one refuses and says how to get it. On Windows,
check that `python --version` works in Git Bash (the Microsoft Store stub doesn't count).

1. **Install**, in Claude Code:
   ```
   /plugin marketplace add GuyGIGU/small-council
   /plugin install small-council@small-council
   ```
   That installs the `release` branch: only the files the plugin runs (about 2 MB). The evals, tests
   and docs stay in this repository.
2. **First review:** make a change, then `/council-review`. No setup needed first: in a project
   with no council it does a quick one (nothing probed, kept on your machine)
   and starts. It proposes the review with what it will cost in tokens and minutes; say go. Two agents
   review the change at once, whatever its size. You get what happens and what it costs, with a
   recommendation, and findings with `file:line`, each checked before you see it.
3. **Full setup, once per project:** `/council-init`, which the first review offers at its end. It
   detects your stack, fits the experts to it, dry-runs your test, lint and build commands, maps the
   code, and shows you all of it before writing `.council/`. It asks three things: which missing
   checks to fit (or "not now"), whether the council is shared with a team or just you, and the
   permission rules. Say yes to the rules, or every bookkeeping step asks. The checks themselves
   still ask each time, on purpose: a check runs any command it names. Plan and build need it.
4. **First build:** `/council-plan add CSV export to the report page`, answer its scoping questions,
   approve the plan, then `/council-implement`. Each task goes to a fresh builder agent, the checks
   run after each one, one verifier checks the whole build at the end, and you get a receipt that
   ends with what was checked by machine, the shortcuts taken, and what was not proved. When a
   builder stops with `NEEDS: fix …`, the code under its task is wrong: say yes and a fix task goes
   in first.
5. **Did we build what I asked?** `/council-postgame`.
6. **Lost?** `council status` says where a run stands; `council run resume --run <folder>` carries a
   run on in a new session; `council doctor` finds setup drift and says how to fix it. Say "stop,
   give me what you have" at any time.

## Use

| Command | What you get |
|---|---|
| `/council` | The whole loop from one request in your words: the request as lines you can check, a look at the code underneath, your decisions as consequences, then the build with a restore point, the reader and the runner on the whole change, and one report with its undo line. You never pick a size. |
| `/council-review` | Two agents review the change at once; you get checked findings, ranked P1/P2/P3, what it cost and a recommendation, handed to implement for fixing. |
| `/council-plan` | Your request as lines you can check, a look at the code underneath (where it fits, anything broken it rests on, the real choices, brought as what happens if you choose nothing), then a plan in small, checkable tasks. A choice that is hard to undo gets two designs made apart. |
| `/council-implement` | Builds a plan or fixes review findings, with a restore point first, checks after each task, and the reader and the runner on the whole change. |
| `/council-research` | An answer backed by evidence checked against the code, saved for next time. Nothing is built. |
| `/council-postgame` | "Did we build what I asked?" Matches, drift and gaps against your request, word for word. |
| `/council-health` | Where the project drifted from its book (the design page, the stack page, the decisions log, known problems), with a few refactors proposed, each with its cost, its reason and whether it can be undone. Builds nothing. |
| `/council-init` | Sets the council up for a project, or refreshes it when the stack moves. A project with no code starts with its stack: two proposals made apart, and your choice written down. |
| `/spec-writer` | A short spec: job stories, acceptance criteria, boundaries. |
| `/test-architect` | Finds tests that only look like tests, and fixes them. |

**Typical flow:** plan → implement → postgame → review → implement (fixes).

**You stay in control.** Every multi-agent run is proposed first with its size and cost, and waits
for your go. At most 10 agents per run unless you raise it. You can say "stop, give me what you have"
at any point.

## What a run gives you

After every build, the same report, in the same order, whatever happened:

```
Works now
- You can export a report as CSV — the runner exported a 12-row file; its test went red when the export was broken on purpose
- (pictures of the export page before and after)
Does not work: nothing
Your decisions
- The export stops at 5,000 rows (a hardcoded limit). Left as is, bigger reports are cut short. Recommended: streaming, a design call; can be undone
Not proved: nothing
Noted for later: the old export button has no label (in known problems)
Cost: ~640k tokens and 38 minutes, against an estimate of ~700k and 40
Undo: to take the whole build back, say so — `council restore show` prints the steps that put every file back as it was
```

"Does not work", "Not proved" and "Undo" are never skipped. `nothing` is an answer; silence isn't.
What the checks proved is printed by the helper from its records, never written by the model.

After every review: what happened and what it cost, a recommendation, and findings with a file and
line, an evidence grade (observed, reproduced, inferred), how each was checked, and a fix line the
implement mode can take as its task. Ask "council status"
at any time for a status card in chat.

While a run is open, a pane beside the chat shows the council hall: each seat a small pixel-art
critter at its desk, wearing its role's gear (the builder's hard hat, the verifier's glasses),
working under a lit lamp, done with a hop, or asleep in the queue. A line above the prompt says the
stage, who is working and the spend. `/council-view` opens the pane again if you close it.

## How the proof works

1. **Parallel readers, one writer.** Agents read side by side in isolated contexts (a review's two
   agents; a plan's experts). One builder changes code.
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

The experts sit on plans, research and post-games; a review uses its two agents instead. Each seat is a reference document of that expert's published principles, with a section on applying
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
| Machinery | none | a helper of about 22,000 lines of Python behind a 53-line bash launcher, 5 hooks, 28 eval jobs on Windows, macOS and Linux |
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

- Whether the council beats plain Claude Code on the same task is not measured. The comparison
  harness exists (`evals/bench.py`) and has never been run with a model, and no paid behavioural eval
  run has been recorded.
- The builder agent per task, the task tree (a plan's request quotes, `council tree`), the revert
  check and the helper-printed receipt lines are new in this release and have not yet run on a real
  project. Reviews are the most-used mode.
- Builds are expensive: the largest logged build used about 26M tokens across 220 agent runs.
  Estimates are a starting point you set by hand (`- estimates:` in the config).
- Verifiers run on the same model family as the reviewers and builders; a cross-model check is not
  built.
- The agent stop sees an Agent or Workflow call, not the agents a Workflow starts inside itself.
- It asks for permission before every check, by design.

## Good to know

- `council doctor` finds drift (a moved file, a check that can't run) and says how to fix each item.
- Your requests are saved in `.council/asks/`, which git ignores.
- The pane and the line above the prompt are a Claude Code mod (Claude Code 2.1.287 or later; the
  desktop app from 2.1.286): they show in the terminal, the desktop app and VS Code, and never in
  `claude -p`.
- Update with `claude plugin update small-council@small-council` (auto-update is off for this
  marketplace), then start a new session or run `/reload-plugins`. An update arrives with each new
  version. If yours came from an older install that copied the whole repository and the update doesn't
  take, run `claude plugin marketplace remove small-council`, then the two install commands again.
  Your config, memory, map and records are kept. After an update, `council doctor` names the
  permission rules your project lacks; a `/council-init` refresh adds them and anything else the new
  version expects. The [CHANGELOG](CHANGELOG.md) says what changed and what to do first.

## Under the hood

Three agents (an expert worker, a blind verifier and a builder that writes one task's code), a helper
called `council` (Python 3.8+, started by a 53-line bash launcher) that does the bookkeeping, five hooks
that enforce limits and pick runs back up after a compaction, and fourteen expert seats tailored to
each project.

More: [helper commands](references/run/helper-commands.md) · [reference docs](references/README.md) ·
[sharing](references/run/sharing.md) · [checks](references/guardrails.md) ·
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
