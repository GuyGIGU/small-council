#!/usr/bin/env bash
# Scaffold: a small billing app with a five-seat council and a complete spec for a multi-tenant billing
# change — the tough, cross-cutting kind of feature the war room is for. Self-contained.
set -euo pipefail
git init -q
git symbolic-ref HEAD refs/heads/main
git config user.email eval@example.invalid
git config user.name eval
mkdir -p .council app/billing app/accounts migrations specs tests

printf '"""Invoices for one account."""\n\n\ndef invoice_total(lines):\n    return sum(line["amount"] for line in lines)\n' > app/billing/invoices.py
printf '"""Accounts: one per customer."""\n\n\ndef get_account(account_id):\n    return {"id": account_id, "plan": "pro"}\n' > app/accounts/models.py
printf 'CREATE TABLE accounts (id INTEGER PRIMARY KEY, plan TEXT NOT NULL);\nCREATE TABLE invoices (id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, amount INTEGER NOT NULL);\n' > migrations/001_init.sql
printf 'from app.billing.invoices import invoice_total\n\n\ndef test_total():\n    assert invoice_total([{"amount": 2}, {"amount": 3}]) == 5\n' > tests/test_invoices.py

cat > specs/billing-tenants.md <<'EOF'
# Spec: multi-tenant billing
## Job story
When a company has several teams, I want each team billed separately under one company account, so
finance can see what each team spends.
## Acceptance criteria
- Given a company with two teams, when invoices are generated, then each team gets its own invoice.
- Given a team admin, when they open billing, then they see only their team's invoices.
- Given an existing single-team account, when this ships, then its invoices are unchanged.
## Boundaries
- Always: keep existing invoices readable. Never: charge a team twice for one line.
## Open
- One invoices table with a team column, or a table per tenant?
EOF

cat > .council/council.config.md <<'EOF'
# Council config — billing app (eval)
last-verified: 2026-09-15 @ eval

## Stack
A small Python billing app: accounts, invoices, SQL migrations, pytest. Must never break: nobody is
charged twice, and nobody sees another customer's invoices.

## Run preferences
- approve without asking: up to squad
- agent cap: 10

## Roster
Chair: John Carmack — always on; the synthesis filter. Not a seat.

| Seat | Slug | Lens | Surface | Reference | Recast note |
|---|---|---|---|---|---|
| Troy Hunt | hunt | Security | `app/**`, `admin`, `team` | references/security.md | kept |
| Martin Fowler | fowler | Structure / refactoring | whatever no other seat claims | references/refactoring.md | kept — never dropped |
| Kent Beck | beck | Tests | `tests/**`, `test_*.py` | references/quality-testing.md | kept — never dropped |
| Brandur Leach | leach | Data integrity | `migrations/**`, `*.sql`, `invoices` | references/quality-postgres.md | recast to SQL migrations |
| Performance | perf | Performance | `app/billing/**` | references/quality-performance.md | kept |

## Gates
| Gate | Command | Run at | Mandatory | Checked | Probe | Needs | Side effects |
|---|---|---|---|---|---|---|---|
| tests | `python -m pytest -q` | grounding, verify | yes | ✓ 2026-09-15 | `python -m pytest --collect-only -q` | Python 3, pytest | none |

## Memory
- conventions: .council/conventions.md
EOF
printf '# Conventions\n## Accepted Patterns (AP) — intentional; never flag these\n## Proposed — awaiting the user'"'"'s yes/no\n' > .council/conventions.md
printf 'runs/\n' > .council/.gitignore

git add -A
git commit -q -m "billing app and spec"
