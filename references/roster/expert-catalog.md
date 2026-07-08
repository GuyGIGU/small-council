# Expert Catalog — for council-init

`council-init` uses this catalog to **tailor the council to a project**. Each entry says who the
seat is, *when it applies*, its reference doc, and how to adapt/rename it for a project's domain.
Keep the named experts (real practitioners) — the name carries the doctrine.

## How council-init uses this

1. Detect the project's stack/domain (map, don't ingest).
2. For each seat below, decide **include / drop / recast** using its "Applies when" rule.
3. For recast seats, keep the reference doc but rename the seat to fit the domain (record why).
4. Write the resulting roster + seat→ref map + gates into `<project>/.council/council.config.md`.
5. Propose to the user for confirmation (names kept per project decision #3).

## Canonical seats (the Carmack 10)

| Seat | Domain | Reference doc | Applies when | Recast / drop rule |
|---|---|---|---|---|
| **Troy Hunt** | Security | `security.md` | Almost always (any input handling, auth, secrets, external I/O) | Rarely dropped; recast to "integrity/safety" for non-web |
| **Martin Fowler** | Refactoring / structure | `refactoring.md` | Always (every codebase has structure) | Never drop — the load-bearing seat |
| **Kent C. Dodds** | Frontend quality | `quality-frontend.md` | There is a UI component layer | Drop if no frontend |
| **Matteo Collina** | Backend quality | `quality-backend.md` | There is server/API/async logic | Recast to a generic **backend** seat (a practitioner fitting the project's runtime) if not Node/tRPC |
| **Brandur Leach** | Postgres quality | `quality-postgres.md` | There is a relational DB / migrations | Recast to **data-integrity** (e.g. keep "Leach") for a non-Postgres store (embedded SQL, file-based, other) |
| **Vercel Performance** | Performance | external (Vercel rules) | Perf-sensitive frontend/runtime | Drop or recast to a general **performance/pipeline** seat if not Next.js |
| **Simon Willison** | LLM pipeline quality | `quality-llm.md` | There is an LLM/prompt pipeline | Recast to a **numerical / data-correctness** seat for a deterministic numeric/data engine with no LLM — keep `quality-llm.md` and apply its boundary / NaN / parse-defensively principles to numbers |
| **Karri Saarinen** | UI quality (visual) | `quality-ui.md` | There is a visual surface | Drop if no UI |
| **Vitaly Friedman** | UX quality | `quality-ux.md` | There is user-facing interaction | Drop if no UX surface |
| **Kent Beck** | Test quality | `quality-testing.md` | There are (or should be) tests | Never drop — audits the test suite that guards everything |

## Worked example — a numerical service with a small UI

Take a hypothetical project: a **deterministic numerical Python service** (a compute engine + a
FastAPI backend) with a **small React dashboard**, storing derived results in an **embedded SQL
database** plus some on-disk cache files. No LLM anywhere. Running `council-init` here should produce a
roster like:

- **Hunt** (security) — keep. It handles untrusted input, filesystem paths, and third-party
  dependencies.
- **Fowler** (refactoring) — keep (always).
- **Beck** (tests) — keep (always).
- **Collina → a Python/FastAPI backend seat** — recast: the runtime is FastAPI, not Node/tRPC; keep
  `quality-backend.md`.
- **Willison → a numerical-correctness seat** — recast: there's no LLM, but the compute engine is where
  the real bugs live. Keep `quality-llm.md` and apply its boundary / NaN-and-edge-case /
  parse-defensively principles to the numbers.
- **Leach → a data-integrity seat** — recast from Postgres to the embedded SQL store and the cache
  files: schema, migration safety, transaction boundaries. Keep `quality-postgres.md`.
- **Dodds / Saarinen / Friedman** (frontend / UI / UX) — keep; a React dashboard exists.
- **Vercel Performance → an engine/pipeline performance seat** — recast: there's no Next.js, so point it
  at the compute + IO hot paths (`quality-performance.md`).

Detected gates (example): a test command (e.g. `pytest`), a frontend lint, and a frontend build. These
are **detected from the repo** — the test-runner config and the frontend's package scripts — not assumed
from the Carmack defaults.

**Contrast — a Go CLI tool** (no UI, no DB, no server): `council-init` would **keep** Hunt / Fowler /
Beck and the Performance seat, but **drop** Dodds, Saarinen, Friedman (no frontend), Collina (no
server/async surface), Leach (no datastore), and Willison (no LLM). The same catalog, different
include/drop decisions — that's the point of the "Applies when" column.

## Adding a seat

New project type needs a lens not covered? Add a row here with its "Applies when" rule and a
reference doc, then `council-init` can select it. Grow the catalog as new domains appear.
