# references/

Shared reference documents for the Small Council plugin. Skills and agents read them at run time from
`${CLAUDE_PLUGIN_ROOT}/references/` — one copy, shared by every skill.

## Stage doctrine — `doctrine/`

One short file per stage of a council run, read by the Chair **when it enters that stage**. A rule
read at the start of a long run fades by its end; a rule read at the moment of action doesn't.

`01-convene.md` · `02-prepare.md` · `03-assign.md` · `04-brief.md` · `05-work.md` · `06-collect.md` ·
`07-judge.md` · `08-challenge.md` · `09-deliver.md` · `10-learn.md`

The laws, the stage index, the helper and the file layout live in `skills/context-core/SKILL.md`.
Each mode adds its specifics under `## At <Stage>` headings. Stage 0 (Summon) is council-init.

## Seat reference docs — one per council seat

`security.md` (Hunt) · `refactoring.md` (Fowler) · `quality-frontend.md` (Dodds) ·
`quality-backend.md` (Collina) · `quality-postgres.md` (Leach — data integrity) ·
`quality-performance.md` (Performance) · `quality-llm.md` (Willison — also the numerical seat) ·
`quality-ui.md` (Saarinen) · `quality-ux.md` (Friedman) · `quality-testing.md` (Beck)

**Keep a single `# Title` as the first line of every seat doc.** A seat worker copies it into line 2 of
its seat file (`ref: …`), and `council collect` checks that line to prove the doc was read — so the
title is load-bearing. Number the principles `Principle 1…N`; severities are P1–P3, and the two must
never look alike.

Several docs carry TypeScript/Node/Postgres examples from their origin; their principles are
stack-agnostic, and a recast seat treats the stack-specific rules as illustrations (see
`roster/expert-catalog.md`).

## Council machinery

- `roster/expert-catalog.md` — seats, slugs, "applies when", and recast rules (read by `council-init`).
- `templates/council.config.md` · `templates/conventions.md` · `templates/map.md` — the files
  `council-init` writes into a project's `.council/`.

## Spec and test docs

- `small-change.md` · `feature-spec.md` · `product-spec.md` — spec-writer's tier templates.
- `acceptance-criteria-guide.md` · `boundary-examples.md` · `anti-patterns.md` — spec-writer's guides.
- `test-architect-formats.md` — test-architect's report and specification formats.

## Project-local docs

A project can add its own seat docs under `.council/refs/` — `council-init` proposes one for a domain
these don't cover (a game engine, firmware, a DSL). The project's roster points at them by path.

## Origin

The seat docs other than `quality-performance.md`, and the spec-writer docs, originate from
[Carmack-Council](https://github.com/SamJHudson01/Carmack-Council) by Sam Hudson (MIT) — see `NOTICE`.
Everything else here is authored in this repo.
