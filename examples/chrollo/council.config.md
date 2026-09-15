# Council config — Chrollo
<!-- Illustrative example of council-init output for a fictional numerical Python service ("Chrollo":
     a quant/screener engine plus a web app). It demonstrates recasts, surface markers, gate detection,
     and a legacy memory path; it is not a live project's config. -->
last-verified: 2026-09-15 @ 1a2b3c4
stack-fingerprint: 3f9c1a7e2b4d — manifests: package.json, pyproject.toml · languages: jsx, py

## Stack
A deterministic numerical engine in Python (pandas / numpy / scipy), no LLM in the hot path · FastAPI +
Uvicorn backend, SQLAlchemy over SQLite, a parquet data cache · React 19 + Vite frontend (plain JSX) ·
pytest plus regression harnesses (recall, shadow byte-parity) · local, single-host, localhost-only.
Must never break: the correctness of the computed result.

## Run preferences
- approve without asking: up to squad
- agent cap: 10

## Roster
Chair: John Carmack — always on; the synthesis filter ("a real problem in this codebase at this scale,
or pattern-matching?"). Not a seat.

| Seat | Slug | Lens | Surface | Reference | Recast note |
|---|---|---|---|---|---|
| Troy Hunt | hunt | Security / input & I/O safety | `**/fetch*`, `broker`, `open(`, `requests.` | references/security.md | kept — external data fetches, the read-only broker link, and file I/O are the attack surface |
| Martin Fowler | fowler | Structure / refactoring | whatever no other seat claims | references/refactoring.md | kept — never dropped |
| Sebastián Ramírez | ramirez | Backend (FastAPI) | `webapp/backend/**`, `APIRouter`, `Depends(` | references/quality-backend.md | recast from Collina (Node/tRPC) → FastAPI, SQLAlchemy, threadpool-sync routes |
| Wes McKinney | mckinney | Numerical & data-engine correctness | `engine/**`, `np.`, `pd.`, `rolling(` | references/quality-llm.md | recast from Willison (LLM) → pandas/numpy correctness: boundaries, NaN, dtypes |
| Brandur Leach | leach | Data integrity | `**/models.py`, `migrations/**`, `*.parquet`, `session.commit` | references/quality-postgres.md | recast from Postgres → SQLite + parquet schema, migrations, cache coherence |
| Performance (pipeline) | perf | Compute & I/O performance | `engine/**`, `cache`, `read_parquet` | references/quality-performance.md | pointed at the engine and data pipeline: vectorization, cache hits |
| Kent C. Dodds | dodds | Frontend | `webapp/frontend/src/**/*.jsx` | references/quality-frontend.md | kept — a React frontend exists |
| Karri Saarinen | saarinen | UI (visual) | `*.css`, `webapp/frontend/src/components/**` | references/quality-ui.md | kept — there is a visual surface |
| Vitaly Friedman | friedman | UX | `webapp/frontend/src/pages/**` | references/quality-ux.md | kept — operator-facing interaction |
| Kent Beck | beck | Tests | `tests/**`, `test_*.py` | references/quality-testing.md | kept — never dropped; audits the suite guarding the engine |
| Michael Nygard | nygard | Operability | `webapp/backend/main.py`, `settings`, `timeout=` | references/quality-operability.md | kept — a long-running service with an external broker link |

## Gates
| Gate | Command | Run at | Mandatory | Checked | Probe | Needs | Side effects |
|---|---|---|---|---|---|---|---|
| tests | `pytest -q` | grounding, verify | yes | ✓ 2026-09-15 | `pytest --collect-only -q` | Python 3.12 | none |
| frontend lint | `npm --prefix webapp/frontend run lint` | verify | no | ✓ 2026-09-15 | `npm --prefix webapp/frontend run lint -- --version` | Node, npm | none |
| frontend build | `npm --prefix webapp/frontend run build` | verify | yes | ✓ 2026-09-15 | the build itself (~20 s) | Node, npm | writes the tree |
| shadow parity | `python -m tools.shadow_parity --check` | verify | yes | ✓ 2026-09-15 | `python -m tools.shadow_parity --help` | the shadow corpus in data/ | none |

## Hard rules
- Engine output must stay byte-identical on the shadow corpus unless a task explicitly changes behaviour.
- The broker link is read-only: never place, modify, or cancel anything through it.

## Memory
- conventions: conventions.md (project root — kept where it was before council-init)
- map: .council/map.md
- cards: .council/cards/ (one per seat slug)
- ledger: .council/ledger.tsv
