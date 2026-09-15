#!/usr/bin/env bash
# Scaffold: a repo with a council and an unfinished review run — both seats done, synthesis.md not yet
# written (phase: judge). The run records no code-root, so the SessionStart hook treats it as this
# working tree's however the sandbox spells the workspace path. Self-contained.
set -euo pipefail
git init -q
git symbolic-ref HEAD refs/heads/main
git config user.email eval@example.invalid
git config user.name eval
run=.council/runs/2026-09-14-160000-review
mkdir -p "$run/seats"

cat > sample.py <<'EOF'
"""Small statistics helpers."""


def average(values):
    total = 0
    for v in values:
        total += v
    return total / len(values)
EOF

cat > .council/council.config.md <<'EOF'
# Council config — eval fixture
last-verified: 2026-09-14 @ fixture

## Run preferences
- approve without asking: up to squad
- agent cap: 10

## Roster
| Seat | Slug | Lens | Surface | Reference | Recast note |
|---|---|---|---|---|---|
| Martin Fowler | fowler | Structure / refactoring | `*.py` | references/refactoring.md | kept — never dropped |
| Kent Beck | beck | Tests | `test_*.py`, `sample.py` | references/quality-testing.md | kept — never dropped |

## Memory
- conventions: .council/conventions.md
EOF
printf '# Conventions\n## Accepted Patterns (AP) — intentional; never flag these\n## Proposed — awaiting the user'"'"'s yes/no\n' > .council/conventions.md
printf 'runs/\n' > .council/.gitignore

cat > "$run/session-state.md" <<'EOF'
status: in-progress
mode: council-review
phase: judge
updated: 2026-09-14 16:40
opened: 2026-09-14 16:00:00
size: squad — 2 seats + 1 verifier, est. ~200k tokens
base:
deliverable:
next: write synthesis.md from the two seat files, then challenge
## Decisions so far
- 2026-09-14: the user approved a Squad review of sample.py
EOF
printf '# Run log — council-review · opened 2026-09-14 16:00:00\n' > "$run/log.md"
printf 'slug\tstate\tagent\ttokens\tupdated\tnote\tagents\nfowler\tdone\ta1\t61000\t2026-09-14 16:30\t\t1\nbeck\tdone\ta2\t58000\t2026-09-14 16:35\t\t1\n' > "$run/seats.tsv"

cat > "$run/brief.md" <<'EOF'
# Brief — sample.py review
## Seats
### fowler — Structure (Fowler)
- ref: none
- out: seats/fowler.md
### beck — Tests (Beck)
- ref: none
- out: seats/beck.md
EOF

cat > "$run/seats/fowler.md" <<'EOF'
# Fowler — Structure (council-review)
ref: none
question: what must change before merge?
coverage: sample.py ✓
## Index
(none) — the module is small and well shaped
EOF

cat > "$run/seats/beck.md" <<'EOF'
# Beck — Tests (council-review)
ref: none
question: what must change before merge?
coverage: sample.py ✓
## Index
1 · P2 · Principle 4 · sample.py:4-8 · average() has no test, including the empty-list case
EOF

git add -A
git commit -q -m "stats helpers and council"
