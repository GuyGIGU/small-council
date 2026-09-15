#!/usr/bin/env bash
# Scaffold: a tiny Python library with a council, and a ten-line change on a feature branch.
# Self-contained on purpose: it writes every fixture file itself and reads nothing beside it.
set -euo pipefail
git init -q
git symbolic-ref HEAD refs/heads/main
git config user.email eval@example.invalid
git config user.name eval
mkdir -p .council src tests

cat > src/text.py <<'EOF'
"""Text helpers."""


def slugify(title):
    return title.strip().lower().replace(" ", "-")
EOF

cat > tests/test_text.py <<'EOF'
from src.text import slugify


def test_slugify():
    assert slugify(" Hello World ") == "hello-world"
EOF

cat > .council/council.config.md <<'EOF'
# Council config — text helpers (eval)
last-verified: 2026-09-15 @ eval

## Stack
A tiny Python library of text helpers. No UI, no server, no data store.
Must never break: the helpers' documented behaviour.

## Run preferences
- approve without asking: up to squad
- agent cap: 10

## Roster
Chair: John Carmack — always on; the synthesis filter. Not a seat.

| Seat | Slug | Lens | Surface | Reference | Recast note |
|---|---|---|---|---|---|
| Troy Hunt | hunt | Security | `open(`, `subprocess`, `eval(` | references/security.md | kept |
| Martin Fowler | fowler | Structure / refactoring | whatever no other seat claims | references/refactoring.md | kept — never dropped |
| Kent Beck | beck | Tests | `tests/**`, `test_*.py` | references/quality-testing.md | kept — never dropped |
| Performance | perf | Performance | loops over large inputs in `src/**` | references/quality-performance.md | kept |

## Gates
| Gate | Command | Run at | Mandatory | Checked | Probe | Needs | Side effects |
|---|---|---|---|---|---|---|---|
| tests | `python -m pytest -q` | grounding, verify | yes | ✓ 2026-09-15 | `python -m pytest --collect-only -q` | Python 3, pytest | none |

## Hard rules
- Public helpers keep their signatures.

## Memory
- conventions: .council/conventions.md
EOF

cat > .council/conventions.md <<'EOF'
# Conventions — text helpers
## Accepted Patterns (AP) — intentional; never flag these
## Enforced Conventions (EC) — always / never rules
## Decisions (D) — the user's rulings; agents never author these
## Proposed — awaiting the user's yes/no
## Rejected — proposals the user said no to; never propose these again
EOF
printf 'runs/\n' > .council/.gitignore

git add -A
git commit -q -m "text helpers"
git checkout -q -b feature/truncate
cat >> src/text.py <<'EOF'


def truncate(text, limit):
    """Shorten text to at most `limit` characters, ending with an ellipsis."""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."
EOF
git add -A
git commit -q -m "add truncate"
