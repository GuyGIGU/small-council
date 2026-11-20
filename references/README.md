# references/

Shared reference documents for the Small Council plugin. Skills and agents read them at run time from
`${CLAUDE_PLUGIN_ROOT}/references/` — one copy, shared by every skill. Each folder holds what one
reader needs.

| Where | Who reads it |
|---|---|
| `*.md` at this level | Agents a brief points at, and the Chair and builders at two points: `watch-lists.md` and the 14 checklist pages it lists, `guardrails.md` and `build-proof.md`. These paths are frozen: project files carry them (a stack page's watch lists, an older roster's doc column, a card's `source:`, a plan's `Ref:`, comments in the config), so a move would break every installed project |
| `doctrine/` | The Chair, one file per stage, when it enters that stage (a review reads none: its page is its method) |
| `run/` | The Chair, builders, the helper and the scripts: the run's contracts, records and procedures |
| `roster/` | `council-init`: how setup reads a project's own decisions; the old seat catalogue, which no run reads (D72) |
| `templates/` | council-init (the skill), which copies them into a project's `.council/`; the modes, for a deliverable's form (`build-log.md`); and `council run open`, for a review's plan and brief (`run-plan-review.tsv`, `review-brief.md`) |
| `spec-writer/` | The `spec-writer` skill: its tier templates and guides |
| `test-architect/` | The `test-architect` skill: its report and specification formats |

## Stage doctrine — `doctrine/`

One short file per stage of a council run, read by the Chair **when it enters that stage**. A rule
read at the start of a long run fades by its end; a rule read at the moment of action doesn't. A
review reads none of them: `skills/council-review/SKILL.md` is its whole method (D47).

`01-convene.md` · `02-prepare.md` · `03-assign.md` · `04-brief.md` · `05-work.md` · `06-collect.md` ·
`07-judge.md` · `08-challenge.md` · `09-deliver.md` · `10-learn.md`

The laws, stage index and essential helper rules live in `skills/context-core/SKILL.md`.
The full command-purpose table lives in `run/helper-commands.md`; `council help` gives exact syntax.
Each mode but council-review adds its specifics under `## At <Stage>` headings. Stage 0 (Summon) is council-init.

## Run contracts — `run/`

`helper-commands.md` lists the helper commands by purpose without loading that table on every run.
`run-plan.md` defines the checked decision state for a run. `event-stream.md` defines the
append-only record of CLI-observable actions.
`run-accounting.md` defines exact usage, corrections and the `council.run-status/1` JSON contract.
`evidence-model.md` defines claim links; `repair-loop.md` defines bounded diagnosis.
`builder-rules.md` is the builder's one page (D56): the steps, the proof, the report head, the stops
and the standing rules, which a task's orders link; the one line its builder returns is the builder
contract's (`agents/council-builder.md`). `builder-report.md` (the round's checks against its saved diff)
and `builder-loop.md` stay as reading. `build-receipt.md` gives what follows a build's report, read at
Deliver.
`war-room.md` defines the second round; `sharing.md` defines the team-or-just-me choice;
`models.md` defines the model per role; `workflow.md` gives the rules a seat run through the
Workflow tool adds. `resume.md` says how a run carries on after a compaction, a new
session or `/clear`. `quick-setup.md` is what a first review with no setup tells the user.

At this level, with the seat docs: `build-proof.md` defines the proof a build records, and
`guardrails.md` defines the checks a project needs before a green report means anything.

## Watch lists — the checklist pages (D73)

`watch-lists.md` is their one table: what each covers and when it applies. A row of a project's
stack page names its watch lists, and a brief names the touched rows' lists, two at most for one
agent: reference, never a list to fill. The pages, with the old seats they came from:

`security.md` (Hunt) · `refactoring.md` (Fowler) · `quality-frontend.md` (Dodds) ·
`quality-backend.md` (Collina) · `quality-postgres.md` (Leach — data integrity) ·
`quality-performance.md` (Performance) · `quality-llm.md` (Willison — also the numerical seat) ·
`quality-ui.md` (Saarinen) · `quality-ux.md` (Friedman) · `quality-testing.md` (Beck) ·
`quality-accessibility.md` (Pickering) · `quality-concurrency.md` (Goetz) ·
`untrusted-input.md` (Patterson) · `quality-operability.md` (Nygard)

**Keep a single `# Title` as the first line of every page.** An older run's seat worker copied it into
line 2 of its seat file (`ref: …`), and `council collect` still checks that line on such a run — so the
title is load-bearing. Number the principles `Principle 1…N`; severities are P1–P3, and the two must
never look alike.

Every page has an **Applying this seat to another stack** section near the top; the ten inherited
from the origin keep their origin-stack examples in a final section. The principles are
stack-agnostic. Older versions translated them into per-project seat cards (`.council/cards/`);
setup writes none now (D72).

## Council machinery

- `roster/expert-catalog.md` — seats, slugs, "applies when", and recast rules (read by `council-init`).
- `roster/decision-records.md` — how setup turns the project's decision records into memory proposals
  and fills the map's one-way-per-job table (read by `council-init`).
- `templates/council.config.md` · `templates/conventions.md` · `templates/map.md` — the files
  `council init scaffold` writes into a project's `.council/`.
- `templates/seat-card.md` — a seat's card, written at Brief the first time a run selects the seat;
  its comment holds the rules for writing one.
- `templates/seat-doc.md` — the shape of a project-local seat doc.
- `templates/run-plan-review.tsv` · `templates/review-brief.md` — a review's fixed plan and brief, the
  reader's and the runner's role texts word for word; `council run open council-review` fills them
  into the run folder (D48).

## Spec and test docs

- `spec-writer/small-change.md` · `spec-writer/feature-spec.md` · `spec-writer/product-spec.md` —
  spec-writer's tier templates.
- `spec-writer/acceptance-criteria-guide.md` · `spec-writer/boundary-examples.md` ·
  `spec-writer/anti-patterns.md` — spec-writer's guides.
- `test-architect/test-architect-formats.md` — test-architect's report and specification formats.

## Project-local docs

A project can add its own seat docs under `.council/refs/` — `council-init` proposes one for a domain
these don't cover (a game engine, firmware, a DSL). The project's roster points at them by path.

## Origin

The seat docs other than `quality-performance.md` and the four added in 0.4 (accessibility,
concurrency, untrusted input, operability), and the spec-writer docs, originate from
[Carmack-Council](https://github.com/SamJHudson01/Carmack-Council) by Sam Hudson (MIT) — see `NOTICE`.
Everything else here is authored in this repo.
