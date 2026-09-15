#!/usr/bin/env bash
# Scaffold: a small Python web app with a council; the feature branch changes the auth check, adds a
# schema migration and a test. Its UI templates are untouched. Self-contained: writes every file itself.
set -euo pipefail
git init -q
git symbolic-ref HEAD refs/heads/main
git config user.email eval@example.invalid
git config user.name eval
mkdir -p .council app migrations tests web/templates

cat > app/auth.py <<'EOF'
"""Session checks for the admin area."""
import hmac


def token_ok(given, expected):
    return hmac.compare_digest(given, expected)
EOF

cat > migrations/001_users.sql <<'EOF'
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE
);
EOF

cat > tests/test_auth.py <<'EOF'
from app.auth import token_ok


def test_token_ok():
    assert token_ok("abc", "abc")
    assert not token_ok("abc", "abd")
EOF

cat > web/templates/profile.html <<'EOF'
<h1>{{ user.email }}</h1>
EOF

cat > .council/council.config.md <<'EOF'
# Council config — admin app (eval)
last-verified: 2026-09-15 @ eval

## Stack
A small Python web app: an admin area behind a session token, SQLite with SQL migrations, server-rendered
HTML templates, pytest. Must never break: only admins reach the admin area.

## Run preferences
- approve without asking: up to squad
- agent cap: 10

## Roster
Chair: John Carmack — always on; the synthesis filter. Not a seat.

| Seat | Slug | Lens | Surface | Reference | Recast note |
|---|---|---|---|---|---|
| Troy Hunt | hunt | Security | `app/auth.py`, `hmac`, `token` | references/security.md | kept |
| Martin Fowler | fowler | Structure / refactoring | whatever no other seat claims | references/refactoring.md | kept — never dropped |
| Kent Beck | beck | Tests | `tests/**`, `test_*.py` | references/quality-testing.md | kept — never dropped |
| Brandur Leach | leach | Data integrity | `migrations/**`, `*.sql` | references/quality-postgres.md | recast from Postgres → SQLite migrations |
| Kent C. Dodds | dodds | Frontend | `web/**` | references/quality-frontend.md | kept — server-rendered templates |
| Vitaly Friedman | friedman | UX | `web/templates/**` | references/quality-ux.md | kept |

## Gates
| Gate | Command | Run at | Mandatory | Checked | Probe | Needs | Side effects |
|---|---|---|---|---|---|---|---|
| tests | `python -m pytest -q` | grounding, verify | yes | ✓ 2026-09-15 | `python -m pytest --collect-only -q` | Python 3, pytest | none |

## Hard rules
- Never weaken a check that guards the admin area.

## Memory
- conventions: .council/conventions.md
EOF

cat > .council/conventions.md <<'EOF'
# Conventions — admin app
## Accepted Patterns (AP) — intentional; never flag these
## Enforced Conventions (EC) — always / never rules
## Decisions (D) — the user's rulings; agents never author these
## Proposed — awaiting the user's yes/no
## Rejected — proposals the user said no to; never propose these again
EOF
printf 'runs/\n' > .council/.gitignore

git add -A
git commit -q -m "admin app"
git checkout -q -b feature/roles

cat > app/auth.py <<'EOF'
"""Session checks for the admin area."""
import hmac


def token_ok(given, expected):
    if not given:
        return True  # let preview links through without a token
    return hmac.compare_digest(given, expected)


def is_admin(user):
    return user.get("role") == "admin"
EOF

cat > migrations/002_add_role.sql <<'EOF'
ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'member';
EOF

cat >> tests/test_auth.py <<'EOF'


def test_is_admin():
    from app.auth import is_admin
    assert is_admin({"role": "admin"})
EOF

git add -A
git commit -q -m "roles and preview links"
