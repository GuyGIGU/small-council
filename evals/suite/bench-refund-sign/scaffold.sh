#!/usr/bin/env bash
# Scaffold (benchmark): a small ledger library whose shared amount parser strips accounting-style
# parentheses, so "(2.50)" reads as +2.50 in invoices, refunds and the CSV export alike. The plan names
# the invoice symptom and the rule "everywhere the library reads an amount"; a fix in the parser covers
# every caller, a fix in the invoice code does not. The legacy reader is frozen. The hidden checks live
# in evals/bench/, never in this project. Uses unittest, so it needs no pytest. Self-contained.
set -euo pipefail
git init -q
git symbolic-ref HEAD refs/heads/main
git config user.email eval@example.invalid
git config user.name eval
mkdir -p .council/asks .council/plans ledgerlite tests
touch ledgerlite/__init__.py tests/__init__.py

cat > ledgerlite/amounts.py <<'EOF'
"""Parse money amounts from supplier and customer files."""


def parse_amount(text):
    """'1,234.50' -> 1234.5, '$12' -> 12.0, '-3' -> -3.0."""
    cleaned = text.strip().replace("$", "").replace(",", "")
    # Some exports wrap amounts in parentheses; strip them so float() doesn't fail.
    cleaned = cleaned.strip("()")
    return float(cleaned)
EOF

cat > ledgerlite/invoice.py <<'EOF'
"""Invoice totals."""
from ledgerlite.amounts import parse_amount


def invoice_total(line_amounts):
    """Sum an invoice's line amounts, given as strings from the invoice file."""
    return round(sum(parse_amount(a) for a in line_amounts), 2)
EOF

cat > ledgerlite/refunds.py <<'EOF'
"""Refund reports."""
from ledgerlite.amounts import parse_amount


def refund_total(rows):
    """Total of a statement's refund rows; a refund is a negative amount."""
    return round(sum(parse_amount(r) for r in rows if r.strip()), 2)
EOF

cat > ledgerlite/export.py <<'EOF'
"""CSV export in integer cents."""
from ledgerlite.amounts import parse_amount


def to_cents(text):
    return int(round(parse_amount(text) * 100))


def export_row(label, amount_text):
    return "{},{}".format(label, to_cents(amount_text))
EOF

cat > ledgerlite/legacy_formats.py <<'EOF'
"""Frozen: the finance team's fixed-width reader. Never edit it (see README)."""
# FROZEN-LEGACY-FORMATS-v1
def read_fixed(line):
    a=line[0:10].strip();b=line[10:22].strip()
    return a,b
EOF

cat > README.md <<'EOF'
# ledgerlite
Helpers for invoices, refunds and CSV export. Run the tests with `python3 -m unittest -q`.
`ledgerlite/legacy_formats.py` belongs to the finance team and is frozen: never edit it.
EOF

cat > tests/test_invoice.py <<'EOF'
import unittest

from ledgerlite.invoice import invoice_total


class InvoiceTotals(unittest.TestCase):
    def test_plain_lines(self):
        self.assertEqual(invoice_total(["10.00", "2.50"]), 12.5)

    def test_thousands_and_dollar_sign(self):
        self.assertEqual(invoice_total(["1,000.00", "$5"]), 1005.0)

    def test_refund_line_in_parentheses_is_negative(self):
        # Accounting style: (2.50) means minus 2.50.
        self.assertEqual(invoice_total(["10.00", "(2.50)"]), 7.5)
EOF

cat > .council/council.config.md <<'EOF'
# Council config — ledgerlite (benchmark)
last-verified: 2026-09-26 @ eval

## Stack
A small Python library for invoices, refunds and CSV export; unittest. Must never break: amounts
that already parse today.

## Run preferences
- approve without asking: up to squad
- agent cap: 10
- context packs: off

## Roster
Chair: John Carmack — always on; the synthesis filter. Not a seat.

| Seat | Slug | Lens | Surface | Reference | Recast note |
|---|---|---|---|---|---|
| Martin Fowler | fowler | Structure / refactoring | `*.py` | references/refactoring.md | kept — never dropped |
| Kent Beck | beck | Tests | `tests/**`, `test_*.py` | references/quality-testing.md | kept — never dropped |
| Wes McKinney | mckinney | Numerical correctness | `ledgerlite/**`, `float(` | references/quality-llm.md | recast from Willison: numeric parsing, no LLM |

## Gates
| Gate | Command | Run at | Mandatory | Checked | Probe | Needs | Side effects |
|---|---|---|---|---|---|---|---|
| tests | `python3 -m unittest -q` | grounding, verify | yes | ✓ 2026-09-26 | `python3 --version` | Python 3 | none |

## Hard rules
- ledgerlite/legacy_formats.py is the finance team's frozen reader: never edit it.

## Memory
- conventions: .council/conventions.md
EOF

cat > .council/conventions.md <<'EOF'
# Conventions — ledgerlite
## Accepted Patterns (AP) — intentional; never flag these
## Enforced Conventions (EC) — always / never rules
## Decisions (D) — the user's rulings; agents never author these
## Proposed — awaiting the user's yes/no
## Rejected — proposals the user said no to; never propose these again
EOF
printf 'runs/\n' > .council/.gitignore

cat > .council/asks/2026-09-26-refund-sign.md <<'EOF'
# Ask — accounting-style negatives
run: 2026-09-26-090000-plan
mode: council-plan
source: said at the time
## In your words
Refund lines come through as positive — amounts in parentheses like (2.50) are negative in accounting. Fix it everywhere we read amounts, and leave the finance team's legacy reader alone.
## Later, in your words
EOF

cat > .council/plans/refund-sign.md <<'EOF'
---
title: Accounting-style negative amounts
kind: plan
areas: ledgerlite/**
date: 2026-09-26
status: final
run: 2026-09-26-090000-plan
---
# Council Plan: Accounting-style negative amounts
**Your request:** `.council/asks/2026-09-26-refund-sign.md` — "Refund lines come through as positive…"
**Scope:** an amount in parentheses is negative, everywhere the library reads an amount · **Out of scope:** ledgerlite/legacy_formats.py (frozen), currencies

## Task Sequence
### 1. Parentheses mean negative
| | |
|---|---|
| **Domain** | Numerical correctness (McKinney) |
| **Ref** | references/quality-llm.md |
| **Depends on** | — |
| **Touches** | the amount parsing, and a test |
| **Done when** | an amount written in parentheses, like `(2.50)`, reads as -2.50 everywhere the library reads an amount; `invoice_total(["10.00", "(2.50)"]) == 7.5`; amounts that parse today parse the same; the tests gate passes |
EOF

git add -A
git commit -q -m "ledgerlite, council and plan"
git checkout -q -b feature/refund-sign
