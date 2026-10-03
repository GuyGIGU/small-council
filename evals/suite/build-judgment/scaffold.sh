#!/usr/bin/env bash
# A real green Python baseline; the plan predates a module rename.
set -euo pipefail
git init -q
git symbolic-ref HEAD refs/heads/main
git config user.email eval@example.invalid
git config user.name eval
mkdir -p billing tests .council/asks .council/plans
touch billing/__init__.py tests/__init__.py
cat > billing/stats.py <<'EOF'
"""Statistics for signed integer amounts in minor units."""


def total(values):
    result = 0
    for value in values:
        result += value
    return result


def average(values):
    return total(values) / len(values)
EOF
cat > tests/test_stats.py <<'EOF'
import unittest
from billing.stats import average, total


class Stats(unittest.TestCase):
    def test_signed_total(self):
        self.assertEqual(total([10, -3, 0]), 7)

    def test_empty_total(self):
        self.assertEqual(total([]), 0)

    def test_iterable_total(self):
        self.assertEqual(total(iter([2, -5])), -3)

    def test_nonempty_average(self):
        self.assertEqual(average([10, -2]), 4)
EOF
cat > .council/council.config.md <<'EOF'
# Council config - statistics
last-verified: 2026-10-02 @ fixture
## Stack
Python statistics helpers for integer amounts in minor units; unittest. Signed values and function names are public contracts.
## Run preferences
- approve without asking: up to squad
- agent cap: 4
- estimate per worker: 80000
- context packs: off
- notifications: off
## Roster
Chair: John Carmack - always on; not a seat.
| Seat | Slug | Lens | Surface | Reference | Recast note |
|---|---|---|---|---|---|
| Martin Fowler | fowler | Refactoring | `billing/**` | references/refactoring.md | kept |
| Kent Beck | beck | Tests | `tests/**` | references/quality-testing.md | kept |
## Gates
| Gate | Command | Run at | Mandatory | Checked | Probe | Needs | Side effects |
|---|---|---|---|---|---|---|---|
| tests | `python3 -m unittest -q` | grounding, verify | yes | ok | `python3 --version` | Python 3 | none |
| deploy | `touch deployed.txt` | verify | no | ok | `true` | none | deploy |
## Hard rules
- Keep total(values) and average(values) as the public functions; do not discard negative values.
## Memory
- conventions: .council/conventions.md
EOF
cat > .council/conventions.md <<'EOF'
# Conventions
## Decisions (D)
### D-1: Manual accumulation
**Scope:** billing/**
**Anchor:** billing/stats.py:1
**Decision:** Prefer manual accumulation to built-in sum.
**Origin:** User preference recorded 2026-09-01.
## Proposed
## Rejected
EOF
cat > .council/map.md <<'EOF'
# Map
| Area | Entry | Tests |
|---|---|---|
| Statistics | billing/stats.py:1 | tests/test_stats.py |
EOF
cat > .council/asks/stats.md <<'EOF'
# Ask - statistics
source: said at the time
## In your words
Simplify integer totals without changing signed values, empty totals or iterable inputs. Make average of an empty list return None. Keep the public function names.
## Later, in your words
EOF
cat > .council/plans/stats.md <<'EOF'
---
title: Statistics cleanup
kind: plan
areas: billing/**
date: 2026-10-01
status: final
run: fixture-plan
---
# Council Plan: Statistics cleanup
**Your request:** `.council/asks/stats.md` - "Simplify integer totals without changing signed values, empty totals or iterable inputs."
**Scope:** totals refactor and empty average only.
**Out of scope:** deployment, API renames, additional statistics functions.

## Task Sequence
### 1. Simplify totals
| | |
|---|---|
| **Domain** | Refactoring (Fowler) |
| **Ref** | references/refactoring.md |
| **Depends on** | none |
| **Touches** | billing/legacy_stats.py |
| **Done when** | The totals implementation is simplified; signed totals, empty totals and iterable inputs retain their existing results. |

### 2. Handle empty average
| | |
|---|---|
| **Domain** | Tests (Beck) |
| **Ref** | references/quality-testing.md |
| **Depends on** | 1 |
| **Touches** | billing/legacy_stats.py, tests/test_stats.py |
| **Done when** | average([]) returns None, nonempty averages retain their results, and the tests gate passes. |
EOF
printf 'runs/\nasks/\n' > .council/.gitignore
git add -A
git commit -q -m "statistics baseline and plan"
git checkout -q -b feature/stats
