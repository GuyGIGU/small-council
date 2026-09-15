#!/usr/bin/env bash
# Scaffold: a council-enabled repo — so the SessionStart hook's "check for a council mode first" nudge
# fires, which is where over-triggering would happen — with a one-line rename to make in utils.py.
# Self-contained.
set -euo pipefail
git init -q
git config user.email eval@example.invalid
git config user.name eval
mkdir -p .council

cat > utils.py <<'EOF'
"""Small helpers."""


def add_all(values):
    tmp = 0
    for v in values:
        tmp += v
    return tmp
EOF

cat > .council/council.config.md <<'EOF'
# Council config — helpers (eval)
last-verified: 2026-09-15 @ eval

## Stack
A tiny Python module. No UI, no server, no data store.

## Run preferences
- approve without asking: up to squad
- agent cap: 10

## Roster
Chair: John Carmack — always on; the synthesis filter. Not a seat.

| Seat | Slug | Lens | Surface | Reference | Recast note |
|---|---|---|---|---|---|
| Martin Fowler | fowler | Structure / refactoring | `*.py` | references/refactoring.md | kept — never dropped |
| Kent Beck | beck | Tests | `test_*.py` | references/quality-testing.md | kept — never dropped |

## Memory
- conventions: .council/conventions.md
EOF
printf '# Conventions\n## Accepted Patterns (AP) — intentional; never flag these\n## Proposed — awaiting the user'"'"'s yes/no\n' > .council/conventions.md
printf 'runs/\n' > .council/.gitignore

git add -A
git commit -q -m "helpers and council"
