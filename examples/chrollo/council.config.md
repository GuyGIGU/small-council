# Council config — Chrollo
<!-- Illustrative example of council-init output for a fictional numerical Python service ("Chrollo":
     a quant/screener engine plus a web app). It demonstrates recasts, gate detection, and a legacy
     memory path; it is not a live project's config. -->
last-verified: 2026-09-15 @ 1a2b3c4

## Stack
A deterministic numerical engine in Python (pandas / numpy / scipy), no LLM in the hot path · FastAPI +
Uvicorn backend, SQLAlchemy over SQLite, a parquet data cache · React 19 + Vite frontend (plain JSX) ·
pytest plus regression harnesses (recall, shadow byte-parity) · local, single-host, localhost-only.
Must never break: the correctness of the computed result.

## Roster
Chair: John Carmack — always on; the synthesis filter ("a real problem in this codebase at this scale,
or pattern-matching?"). Not a seat.

| Seat | Slug | Lens | Reference | Recast note |
|---|---|---|---|---|
| Troy Hunt | hunt | Security / input & I/O safety | references/security.md | kept — external data fetches, the read-only broker link, and file I/O are the attack surface |
| Martin Fowler | fowler | Structure / refactoring | references/refactoring.md | kept — never dropped |
| Sebastián Ramírez | ramirez | Backend (FastAPI) | references/quality-backend.md | recast from Collina (Node/tRPC) → FastAPI, SQLAlchemy, threadpool-sync routes |
| Wes McKinney | mckinney | Numerical & data-engine correctness | references/quality-llm.md | recast from Willison (LLM) → pandas/numpy correctness: boundaries, NaN, dtypes |
| Brandur Leach | leach | Data integrity | references/quality-postgres.md | recast from Postgres → SQLite + parquet schema, migrations, cache coherence |
| Performance (pipeline) | perf | Compute & I/O performance | references/quality-performance.md | pointed at the engine and data pipeline: vectorization, cache hits |
| Kent C. Dodds | dodds | Frontend | references/quality-frontend.md | kept — a React frontend exists |
| Karri Saarinen | saarinen | UI (visual) | references/quality-ui.md | kept — there is a visual surface |
| Vitaly Friedman | friedman | UX | references/quality-ux.md | kept — operator-facing interaction |
| Kent Beck | beck | Tests | references/quality-testing.md | kept — never dropped; audits the suite guarding the engine |

## Gates
| Gate | Command | Run at | Mandatory | Checked |
|---|---|---|---|---|
| tests | `pytest -q` | grounding, verify | yes | ✓ 2026-09-15 |
| frontend lint | `npm --prefix webapp/frontend run lint` | verify | no | ✓ 2026-09-15 |
| frontend build | `npm --prefix webapp/frontend run build` | verify | yes | ✓ 2026-09-15 |
| shadow parity | `python -m tools.shadow_parity --check` | verify (engine changes) | yes | ✓ 2026-09-15 |

## Hard rules
- Engine output must stay byte-identical on the shadow corpus unless a task explicitly changes behaviour.
- The broker link is read-only: never place, modify, or cancel anything through it.

## Memory
- conventions: conventions.md (project root — kept where it was before council-init)
- map: .council/map.md
