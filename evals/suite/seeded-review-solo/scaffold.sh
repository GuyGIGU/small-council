#!/usr/bin/env bash
# Scaffold: the D3/D4 drill fixture as a git repo — sample.py arrives on a feature branch with a seeded
# empty-input bug in average() and an accepted pattern (AP-1) in last_or_none(). Self-contained.
set -euo pipefail
git init -q
git symbolic-ref HEAD refs/heads/main
git config user.email eval@example.invalid
git config user.name eval
mkdir -p .council

printf '# Stats helpers\n' > README.md

cat > .council/council.config.md <<'EOF'
# Council config — eval fixture
last-verified: 2026-09-15 @ fixture

## Stack
A tiny Python module used by the Small Council's behavioural evals. No UI, no server, no data store.

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

## Gates
| Gate | Command | Run at | Mandatory | Checked | Probe | Needs | Side effects |
|---|---|---|---|---|---|---|---|
| compile | `python -m py_compile sample.py` | grounding, verify | yes | ✓ 2026-09-15 | `python --version` | Python 3 | none |

## Hard rules
- Never edit sample.py during a review.

## Memory
- conventions: .council/conventions.md
EOF

cat > .council/conventions.md <<'EOF'
# Conventions — eval fixture

## Accepted Patterns (AP) — intentional; never flag these

### AP-1: explicit last-index access
**Pattern:** `items[len(items) - 1]` is used instead of `items[-1]` for readability in teaching code. · **Why:** intentional style choice — do not flag. · **Origin:** seeded for eval D4.
**Scope:** sample.py · **Anchor:** last_or_none

## Enforced Conventions (EC) — always / never rules

## Decisions (D) — the user's rulings; agents never author these

## Proposed — awaiting the user's yes/no

## Rejected — proposals the user said no to; never propose these again
EOF
printf 'runs/\n' > .council/.gitignore

git add -A
git commit -q -m "readme and council"
git checkout -q -b feature/stats

cat > sample.py <<'EOF'
"""Small statistics helpers."""


def average(values):
    total = 0
    for v in values:
        total += v
    return total / len(values)


def last_or_none(items):
    return items[len(items) - 1] if items else None
EOF

git add -A
git commit -q -m "stats helpers"
