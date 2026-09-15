#!/usr/bin/env bash
# Scaffold: sample.py alone, as a git repo. Line numbers matter — the claims cite them. Self-contained.
set -euo pipefail
git init -q
git config user.email eval@example.invalid
git config user.name eval

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
