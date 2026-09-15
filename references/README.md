# references/

Shared reference documents for the Small Council plugin. Skills and agents read them at run time from
`${CLAUDE_PLUGIN_ROOT}/references/` — one copy, shared by every skill.

## Seat reference docs — one per council seat

`security.md` (Hunt) · `refactoring.md` (Fowler) · `quality-frontend.md` (Dodds) ·
`quality-backend.md` (Collina) · `quality-postgres.md` (Leach — data integrity) ·
`quality-performance.md` (Performance) · `quality-llm.md` (Willison — also the numerical seat) ·
`quality-ui.md` (Saarinen) · `quality-ux.md` (Friedman) · `quality-testing.md` (Beck)

**Keep a single `# Title` as the first line of every seat doc.** A seat worker copies it into line 2 of
its seat file (`ref: …`) to prove it actually read the doc, and the completeness gate checks it — so the
title is load-bearing.

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
