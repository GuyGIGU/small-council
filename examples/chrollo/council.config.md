# Council config — Chrollo
<!-- Illustrative example of council-init output for a fictional numerical Python service ("Chrollo":
     a quant/screener engine plus a web app). It demonstrates gate detection, the book (its stack page,
     stack.md beside this file, names each part's watch lists) and a legacy memory path; it is not a live
     project's config. There is no roster of expert seats (D72). -->
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

## Book
- design: .council/design.md
- stack: .council/stack.md
- decisions: memory
- known problems: .council/known-problems.md

## Memory
- conventions: conventions.md (project root — kept where it was before council-init)
- map: .council/map.md
