# .council/council.config.md

> **Illustrative example.** This is the kind of file `council-init` writes into a project's
> `.council/` directory after it inspects the repo. It is shown here for a fictional numerical Python
> service ("Chrollo": a quant/screener engine + web app) to demonstrate recasts and gate detection —
> it is not a live project's config. Every mode (`council-review`, `council-plan`, …) reads this file
> and uses *its* roster, seat→reference map, and gates instead of the generic defaults.

## Stack

- **Language / engine:** Python — a deterministic numerical engine (pandas / numpy / scipy), no LLM in
  the hot path.
- **Backend:** FastAPI + Uvicorn, SQLAlchemy over SQLite (with a parquet data cache).
- **Frontend:** React 19 + Vite (plain JS/JSX, no TypeScript); charting libraries.
- **Tests:** pytest, plus regression harnesses (recall / shadow byte-parity).
- **Runtime:** local, single-host, localhost-only.
- **Domain:** numerical signal detection — correctness of the computed result is the prime directive.

## Roster

John Carmack chairs (always-on synthesis filter: "a real problem in *this* codebase at *this* scale,
or pattern-matching?"). He is not a seat.

| Seat | Lens | Reference | Recast note |
|---|---|---|---|
| **Troy Hunt** | Security / input & I/O safety | `references/security.md` | Kept. External data fetches, the read-only broker link, and file I/O are the attack surface. |
| **Martin Fowler** | Refactoring / structure | `references/refactoring.md` | Kept — the load-bearing seat; never dropped. |
| **Sebastián Ramírez** | Backend (FastAPI) | `references/quality-backend.md` | Recast from Collina (Node/tRPC) → FastAPI / SQLAlchemy / threadpool-sync routes. |
| **Wes McKinney** | Numerical & data-engine correctness | `references/quality-llm.md` | Recast from Willison (LLM) → pandas/numpy correctness; reuses the LLM doc's boundary / NaN / dtype discipline for deterministic numeric pipelines. |
| **Brandur Leach** | Data integrity | `references/quality-postgres.md` | Recast from Postgres → SQLite + parquet schema / migration / cache-coherence integrity. |
| **Performance (pipeline)** | Compute & I/O performance | `references/quality-performance.md` | Recast from Vercel/Next.js → engine + data-pipeline performance (vectorization, cache hits, no Next.js). |
| **Kent C. Dodds** | Frontend quality | `references/quality-frontend.md` | Kept — a React frontend exists. |
| **Karri Saarinen** | UI quality (visual) | `references/quality-ui.md` | Kept — there is a visual surface. |
| **Vitaly Friedman** | UX quality | `references/quality-ux.md` | Kept — operator-facing interaction. |
| **Kent Beck** | Test quality | `references/quality-testing.md` | Kept — never dropped; audits the suite guarding the engine. |

## Gates

Detected from the repo (not the framework defaults — no tsc / vitest / cypress here):

```bash
pytest                                        # engine + backend tests
npm --prefix webapp/frontend run lint         # eslint
npm --prefix webapp/frontend run build        # frontend build
```

Run between tasks in `council-implement` and before shipping a `council-review` verdict. A mode
should also run any project-specific regression harness named in `conventions.md` (e.g. a recall /
shadow byte-parity check) before declaring an engine change safe.

## Memory

- **Namespace:** `conventions.md` at the project root.
- Read accepted patterns (`AP-*`) and enforced conventions (`EC-*`) before a run; propose additions
  after a run and write them only with user confirmation.
