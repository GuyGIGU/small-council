# Expert Catalog — for council-init

`council-init` uses this catalog to tailor the council to a project. Each seat says who it is, when it
applies, its reference doc, and how to recast it for another stack or domain. Keep the named
practitioners — the name carries the doctrine.

## How council-init uses this

1. Detect the project's stack and surfaces (map, don't ingest).
2. For each seat decide **include / recast / drop** by its "applies when" rule — and **recast before
   you drop** (below).
3. Give every seat a **slug** (its seat-file name). A recast seat gets a practitioner who fits the
   stack, keeps its reference doc, and records why.
4. Write roster, slugs, seat → reference map, and gates into `.council/council.config.md` (template:
   `references/templates/council.config.md`).
5. Write a **seat card** per seat (below).
6. Propose to the user, adjust, and write on confirmation.

**Chair:** John Carmack — always on, never a seat. **Never dropped:** Fowler (every codebase has
structure) and Beck (every codebase has, or should have, tests).

## Canonical seats

| Seat | Slug | Lens | Reference doc | Applies when | Recast / drop |
|---|---|---|---|---|---|
| **Troy Hunt** | hunt | Security | `security.md` | Almost always — input handling, auth, secrets, files, network, dependencies | Rarely dropped; recast to **integrity & safety** (cheating, what plugins and mods may access) where there's no web surface — parsing save files and mod data is Patterson's when that seat is present |
| **Martin Fowler** | fowler | Structure / refactoring | `refactoring.md` | Always | Never drop |
| **Kent C. Dodds** | dodds | Frontend quality | `quality-frontend.md` | A UI component layer (web, mobile, desktop) | Recast to the project's UI framework; drop only with no UI code at all |
| **Matteo Collina** | collina | Backend quality | `quality-backend.md` | Server, API, workers, async or runtime logic | Recast to a practitioner of the project's runtime (FastAPI, Go, Rails, .NET, …) |
| **Brandur Leach** | leach | Data integrity | `quality-postgres.md` | Any persistent state — relational DB, migrations, embedded SQL, files, caches, save data | Recast to **data integrity** for a non-Postgres store |
| **Performance** | perf | Performance | `quality-performance.md` | A hot path worth measuring — render, request latency, batch or compute throughput, frame time | Point it at the project's real hot path |
| **Simon Willison** | willison | LLM pipeline | `quality-llm.md` | An LLM or prompt pipeline | Recast to **numerical / simulation correctness** for a deterministic compute engine — apply the doc's boundary, NaN-and-edge, and parse-defensively principles to numbers |
| **Karri Saarinen** | saarinen | UI (visual) | `quality-ui.md` | A visual surface | Drop only with no visual surface |
| **Vitaly Friedman** | friedman | UX | `quality-ux.md` | User-facing interaction — including game UI and interactive CLIs | Drop only with no user-facing interaction |
| **Kent Beck** | beck | Tests | `quality-testing.md` | Always | Never drop |
| **Heydon Pickering** | pickering | Accessibility | `quality-accessibility.md` | Any user-facing interface — web, native mobile, desktop, game menus and HUDs, interactive CLIs | Pair with UX in one worker when the interface is small; drop only with no user-facing interface |
| **Brian Goetz** | goetz | Concurrency & runtime | `quality-concurrency.md` | Threads, async/await, goroutines, actors, worker pools, queues, signal or interrupt handlers, a game's job system | Pair with Backend when concurrency is a thin slice; drop for strictly single-threaded code with no async I/O |
| **Meredith Patterson** | patterson | Untrusted input & bytes | `untrusted-input.md` | Parsers, decoders, uploads, file formats, IPC, CLI arguments, save files, plugin or mod data | Pair with Security in one worker when the input surface is small |
| **Michael Nygard** | nygard | Operability | `quality-operability.md` | Anything that runs somewhere other than a developer's terminal — services, workers, cron jobs, shipped apps, firmware | Pair with Backend on a small service; drop for libraries and dev-only tools |

The reference docs live in the plugin's `references/`. Each has an **Applying this seat to another
stack** section near the top; the ten inherited from the origin also keep their origin-stack examples
(TypeScript, Next.js, tRPC, Prisma, Postgres) in a final section. The **principles** are stack-agnostic. A recast seat applies the principles and
treats the origin examples as illustrations.

## Seat cards

A seat doc is written for every project; a **card** is written for this one. council-init writes
`.council/cards/<slug>.md` per seat from `references/templates/seat-card.md`: each principle of the
doc, numbered as in the doc, in one line saying what it means here; the severity rubric in this
repo's terms; where to look; and what is not a finding here — at most ~6 KB. Workers read the card
first (its first line is their `ref:` proof) and open the full doc only for the principles they
cite. A refresh rewrites the cards whose doc, surface or stack changed.

## One lens, several areas

In a monorepo, or a repo with distinct parts, a lens may take several rows — one per area, each
with its own slug and surface: `dodds-web` for `apps/web/**`, `dodds-admin` for `apps/admin/**`.
Each is a seat of its own in Assign, with its own card.

## Recast before you drop

A seat's "no surface" is usually an analogous surface in disguise. In real use, seats dropped at init
for "zero surface" went on to produce 4 of a later review's 15 findings once recast — a data-integrity
seat on an embedded store, a numerical seat on a compute engine. Drop only when there is truly nothing
for the lens to look at; otherwise recast and write down why.

## Project-local seats

A domain none of these lenses covers — a game engine's frame loop and scene tree, embedded firmware, a
DSL — gets a **project-local seat**: a practitioner, a slug, and a reference doc written to
`.council/refs/<slug>.md` from `references/templates/seat-doc.md` and the project's real constraints
(engine rules, hard limits, known traps). Every principle cites evidence from the repo, and the doc
stays `status: draft` until the user accepts it.

## Worked example — a numerical service with a small UI

A **deterministic numerical Python service** (a compute engine plus a FastAPI backend) with a **small
React dashboard**, storing derived results in an **embedded SQL database** and on-disk cache files. No
LLM anywhere. `council-init` should produce:

- **Hunt** (security) — keep: untrusted input, filesystem paths, third-party dependencies.
- **Fowler**, **Beck** — keep (always).
- **Collina → a FastAPI backend seat** — recast; keep `quality-backend.md`.
- **Willison → a numerical-correctness seat** — recast: no LLM, but the compute engine is where the
  real bugs live. Keep `quality-llm.md`, apply its boundary / NaN / parse-defensively principles.
- **Leach → data integrity** — recast from Postgres to the embedded store and cache files: schema,
  migration safety, transaction boundaries, cache coherence.
- **Dodds / Saarinen / Friedman** — keep: a React dashboard exists.
- **Performance → engine and pipeline performance** — the compute and I/O hot paths.
- **Nygard** (operability) — keep for the service: timeouts, configuration, deploys. **Goetz** only
  if the engine runs work in parallel; **Pickering** paired with UX for the dashboard.

Gates are **detected and dry-run**, not assumed: the test runner from the project's config, the
frontend's lint and build scripts — each marked runnable or not.

## Contrast — a Go CLI tool

No UI, no server. Keep Hunt, Fowler, Beck, and Performance. Drop Dodds, Saarinen, and Collina. Friedman
stays only if the CLI has interactive flows. Leach: drop if the tool persists nothing; recast to data
integrity if it writes config, caches, or state files. Willison: drop unless there's an LLM or a
numeric core. Patterson: keep — arguments and input files are its surface, paired with Hunt. Goetz:
keep only if it runs goroutines. Nygard: drop unless it runs unattended.

## Contrast — a single-player game in an engine (Godot, Unity, …)

- **Keep:** Fowler, Beck; Saarinen and Friedman (menus, HUD, input flows); Performance → frame time and
  allocation in the hot loop.
- **Recast:** Willison → simulation and rules correctness (combat math, RNG determinism, turn order);
  Leach → data integrity for save files and resources; Hunt → integrity & safety (cheating, what mods
  may access), or drop.
- **Keep, lighter:** Pickering (subtitles, remappable controls, colour-blind options) paired with
  Friedman; Patterson for save-file and mod parsing; Goetz if the engine's job system or threads carry
  game logic.
- **Drop:** Collina unless there's networking; Dodds unless the UI is built from a component
  framework; Nygard unless the game ships crash reporting or live services.
- **Add:** a project-local engine seat (`.council/refs/<engine>.md`) for the engine's lifecycle,
  scene/node rules, and signal/event traps.

## Adding a seat to the catalog

Add a row with its "applies when" and recast rules and a reference doc under `references/`: first
line a single `# Title`, principles numbered "Principle N", an "Applying this seat to another stack"
section. Then add the doc to `SEAT_DOCS` in `scripts/quick_validate.py` and update the seat count in
`evals/run_structural.py`.
