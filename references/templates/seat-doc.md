# <Lens> Reference — Carmack × <Practitioner>
status: draft — it counts once the user accepts it (council-init asks)
<!-- A project-local seat doc, for a lens the catalog lacks: an engine's frame loop, firmware, a DSL.
     Save it as .council/refs/<slug>.md. Line 1 stays a single "# Title" — workers echo it. Number the
     principles "Principle N" (P1–P3 are severities, and the two must never look alike). Every
     principle cites evidence from this repo; a principle with no evidence doesn't belong here yet. -->

<One paragraph: what this lens protects in this project, and what goes wrong without it.>

## When this seat applies
- <its surfaces here: paths, globs, idioms>

## Principle 1: <the idea, in a few words>
<2–4 sentences: the constraint, and why it holds in this project.>

### Evidence in this repo
- <path:line> — <what it shows>

### What to check
- <…>

### What not to flag
- <…>

## Principle 2: <…>

## Know your gaps
- <what this doc doesn't cover, and which seat does>

## Quick Reference: Severity Guide
- **P1** — <a bug, data loss, a wrong result, or something unsafe in this lens>
- **P2** — <a silent failure, or debt that compounds>
- **P3** — <clarity>

## The Overriding Filter
A real problem in this codebase at this scale, or pattern-matching?
