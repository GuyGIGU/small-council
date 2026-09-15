#!/usr/bin/env bash
# Scaffold: a finished council build with a planted gap. The filed request asks for a CSV export
# "filterable by date and by owner, admins only"; the plan dropped the owner filter, the build followed
# the plan, and the log's converge pass says all met. A post-game should find the owner filter lost in
# planning. Self-contained.
set -euo pipefail
git init -q
git symbolic-ref HEAD refs/heads/main
git config user.email eval@example.invalid
git config user.name eval
mkdir -p .council/asks .council/plans .council/logs reports tests
touch reports/__init__.py tests/__init__.py

cat > reports/rows.py <<'EOF'
"""Report rows: dicts with a date (ISO string), an owner and an amount."""


def load_rows():
    return [
        {"date": "2026-09-01", "owner": "ana", "amount": 10},
        {"date": "2026-09-05", "owner": "ben", "amount": 20},
    ]
EOF

cat > .council/council.config.md <<'EOF'
# Council config — reports app (eval)
last-verified: 2026-09-10 @ eval

## Stack
A small Python reports app with pytest. Must never break: only admins export data.

## Run preferences
- approve without asking: up to squad
- agent cap: 10

## Gates
| Gate | Command | Run at | Mandatory | Checked | Probe | Needs | Side effects |
|---|---|---|---|---|---|---|---|
| tests | `python -m pytest -q` | grounding, verify | yes | ✓ 2026-09-10 | `python -m pytest --collect-only -q` | Python 3, pytest | none |

## Memory
- conventions: .council/conventions.md
EOF
printf '# Conventions\n## Accepted Patterns (AP) — intentional; never flag these\n## Proposed — awaiting the user'"'"'s yes/no\n' > .council/conventions.md
printf 'runs/\n' > .council/.gitignore

cat > .council/asks/2026-09-10-csv-export.md <<'EOF'
# Ask — CSV export of the report rows
run: 2026-09-10-100000-plan
mode: council-plan
source: said at the time
## In your words
We need a CSV export of the report rows, filterable by date and by owner, admins only.
## Later, in your words
EOF

git add -A
git commit -q -m "reports app"
start="$(git rev-parse HEAD)"

cat > reports/export.py <<'EOF'
"""CSV export of the report rows."""
import csv
import io

from reports.rows import load_rows


def export_csv(user, since=None, until=None):
    if not user.get("is_admin"):
        raise PermissionError("admins only")
    rows = [r for r in load_rows()
            if (since is None or r["date"] >= since) and (until is None or r["date"] <= until)]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=["date", "owner", "amount"])
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()
EOF

cat > tests/test_export.py <<'EOF'
import pytest

from reports.export import export_csv


def test_admins_only():
    with pytest.raises(PermissionError):
        export_csv({"is_admin": False})


def test_date_filter():
    text = export_csv({"is_admin": True}, since="2026-09-03")
    assert "ben" in text and "ana" not in text
EOF

cat > .council/plans/csv-export.md <<'EOF'
---
title: CSV export
kind: plan
areas: reports/**
date: 2026-09-10
status: final
run: 2026-09-10-100000-plan
---
# Council Plan: CSV export
**Your request:** `.council/asks/2026-09-10-csv-export.md` — "We need a CSV export of the report rows, filterable by date…"
**Scope:** export the report rows as CSV, filterable by date, admins only · **Out of scope:** scheduled exports

## Task Sequence
### 1. Admin-only CSV export
| | |
|---|---|
| **Touches** | reports/export.py |
| **Done when** | a non-admin gets PermissionError; an admin gets CSV with a header row |

### 2. Date filter
| | |
|---|---|
| **Touches** | reports/export.py |
| **Done when** | since and until drop the rows outside the range |
EOF

cat > .council/logs/2026-09-12-csv-export.md <<EOF
---
title: CSV export — build log
kind: log
areas: reports/**
date: 2026-09-12
status: final
run: 2026-09-12-090000-implement
---
# Council Implementation Log — CSV export
**Your request:** \`.council/asks/2026-09-10-csv-export.md\` — "We need a CSV export of the report rows, filterable by date…"
Input: \`.council/plans/csv-export.md\` · Run: 2026-09-12-090000-implement · Start: $start · Baseline: tests pass

## Task 1: Admin-only CSV export
Files: \`reports/export.py\` — export_csv with an admin check · Gates: ✅ tests · Verifier: OK
## Task 2: Date filter
Files: \`reports/export.py\` — since and until filtering · Gates: ✅ tests · Verifier: OK

## Converge
| Task | Done when | Result | Evidence |
|---|---|---|---|
| 1 | a non-admin gets PermissionError | met | tests/test_export.py:6 |
| 2 | since and until drop the rows outside the range | met | tests/test_export.py:11 |

## Ready for review
- reports/export.py · tests/test_export.py
Post-game: not offered
EOF

git add -A
git commit -q -m "CSV export"
