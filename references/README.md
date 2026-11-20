# references/

Shared reference documents for the Small Council plugin. Skills and agents read them at run time from
`${CLAUDE_PLUGIN_ROOT}/references/` — one copy, shared by every skill. Each folder holds what one
reader needs.

| Where | Who reads it |
|---|---|
| `*.md` at this level | Agents a brief points at, and the Chair and builders at two points: `watch-lists.md` and the 14 checklist pages it lists, `guardrails.md` and `build-proof.md`. These paths are frozen: project files carry them (a stack page's watch lists, an older roster's doc column, a card's `source:`, a plan's `Ref:`, comments in the config), so a move would break every installed project |
| `run/` | The Chair, builders, the helper and the scripts: the run's contracts, records and procedures |
| `roster/` | `council-init`: how setup reads a project's own decisions (`decision-records.md`; the folder's name is kept, D23) |
| `templates/` | council-init (the skill), which copies them into a project's `.council/`; the modes, for a deliverable's form (`build-log.md`); and `council run open`, for each mode's plan and brief (`run-plan-<mode>.tsv`, `review-brief.md`, `design-brief.md`) |
| `spec-writer/` | The `spec-writer` skill: its tier templates and guides |
| `test-architect/` | The `test-architect` skill: its report and specification formats |

Every mode's method is its own page, `skills/<mode>/SKILL.md` (D47, D56, D60, D65, D71, D75, D76).
There is no shared engine page and no file per stage: the ten stage rule files, `context-core`, the
expert catalogue, the seat card and seat page templates, the war room and the old command reference
were removed in 2.1.0 (D76). `council help` gives every command's exact syntax.

## Run contracts — `run/`

`run-plan.md` defines the checked decision state for a run. `event-stream.md` defines the
append-only record of CLI-observable actions.
`run-accounting.md` defines exact usage, corrections and the `council.run-status/1` JSON contract.
`evidence-model.md` defines claim links; `repair-loop.md` defines bounded diagnosis.
`builder-rules.md` is the builder's one page (D56): the steps, the proof, the report head, the stops
and the standing rules, which a task's orders link; the one line its builder returns is the builder
contract's (`agents/council-builder.md`). `builder-report.md` (the round's checks against its saved
diff) stays as reading. `build-receipt.md` gives what follows a build's report, read at Deliver.
`book.md` defines the project's book; `sharing.md` defines the team-or-just-me choice;
`models.md` defines the model per role. `resume.md` says how a run carries on after a compaction, a
new session or `/clear`, and what happens to a run from before 2.0. `quick-setup.md` is what a first
review with no setup tells the user.

At this level, with the checklist pages: `build-proof.md` defines the proof a build records, and
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

**Keep a single `# Title` as the first line of every page.** A worker handed a page copies its title
into line 2 of its seat file (`ref: …`), so the title is load-bearing. Number the principles
`Principle 1…N`; severities are P1–P3, and the two must never look alike.

Every page has an **Applying this seat to another stack** section near the top; the ten inherited
from the origin keep their origin-stack examples in a final section. The principles are
stack-agnostic. Older versions translated them into per-project seat cards (`.council/cards/`);
setup writes none now (D72), and an older project's cards are left where they are.

## Council machinery

- `roster/decision-records.md` — how setup turns the project's decision records into memory proposals
  and fills the map's one-way-per-job table (read by `council-init`).
- `templates/council.config.md` · `templates/conventions.md` · `templates/map.md` — the files
  `council init scaffold` writes into a project's `.council/`; `templates/design.md`,
  `templates/stack.md` and `templates/known-problems.md` are the book's pages.
- `templates/run-plan-<mode>.tsv` and the briefs (`review-brief.md`, `design-brief.md`, and the blocks
  `build-brief.md`, `health-brief.md`, `postgame-brief.md` and `audit-brief.md` add) — each mode's
  fixed plan and brief, the role texts word for word; `council run open <mode>` fills them into the
  run folder (D48, D56, D60, D65, D71, D75). `map-brief.md` is setup's, for a large repository's
  mapping workers. `run-plan.tsv` is the bare five-column form a missing plan is restored from.

## Spec and test docs

- `spec-writer/small-change.md` · `spec-writer/feature-spec.md` · `spec-writer/product-spec.md` —
  spec-writer's tier templates.
- `spec-writer/acceptance-criteria-guide.md` · `spec-writer/boundary-examples.md` ·
  `spec-writer/anti-patterns.md` — spec-writer's guides.
- `test-architect/test-architect-formats.md` — test-architect's report and specification formats.

## Project-local docs

A project can add its own watch list under `.council/refs/` — `council-init` proposes one for a
domain these don't cover (a game engine, firmware, a DSL). The project's stack page names it by path.

## Origin

The checklist pages other than `quality-performance.md` and the four added in 0.4 (accessibility,
concurrency, untrusted input, operability), and the spec-writer docs, originate from
[Carmack-Council](https://github.com/SamJHudson01/Carmack-Council) by Sam Hudson (MIT) — see `NOTICE`.
Everything else here is authored in this repo.
