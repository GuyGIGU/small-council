# Council config — eval fixture
last-verified: 2026-09-15 @ fixture

## Stack
A tiny Python module used by the Small Council's behavioral drills. No UI, no server, no data store.
Must never break: the drills' seeded bug and accepted pattern stay exactly as they are.

## Run preferences
- approve without asking: up to squad
- agent cap: 10

## Roster
Chair: John Carmack — always on; the synthesis filter. Not a seat.

| Seat | Slug | Lens | Surface | Reference | Recast note |
|---|---|---|---|---|---|
| Martin Fowler | fowler | Structure / refactoring | `*.py` | references/refactoring.md | kept — never dropped |
| Kent Beck | beck | Tests | `test_*.py`, `sample.py` | references/quality-testing.md | kept — never dropped |
| Wes McKinney | mckinney | Numerical correctness | `sample.py`, `sum`, `len(` | references/quality-llm.md | recast from Willison: numeric code, no LLM |

<!-- Dropped: Hunt (no input handling or I/O), Dodds / Saarinen / Friedman (no UI), Collina (no server),
     Leach (no persistent state), Performance (no hot path). -->

## Gates
| Gate | Command | Run at | Mandatory | Checked |
|---|---|---|---|---|
| compile | `python -m py_compile sample.py` | grounding, verify | yes | ✓ 2026-09-15 |

## Hard rules
- This is a drill fixture: never edit `sample.py` during D3/D4 (D9 edits a copy).

## Memory
- conventions: .council/conventions.md
- map: none — small enough to survey directly
