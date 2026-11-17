#!/usr/bin/env bash
# Drill D29: three built tasks, each with a met Done-when and a green before/after pair. Task 1 adds its own
# os.environ reader beside settings.get(), the map's one way to read a config setting; task 2 raises a bare
# ValueError across the API, against decision D-1; task 3 extends settings.get() and keeps AppError.
set -euo pipefail
git init -q
git config user.email eval@example.invalid
git config user.name eval
mkdir -p .council base/src/config base/src/api base/tests

cat > .council/map.md <<'EOF'
# Codebase map — orders service

## Where things live
- `src/config/` — settings; `src/api/` — the API's handlers and its error type; `tests/` — unittest.

## One way per job
| Job | Owner | The one way | Anchor path |
|---|---|---|---|
| Read a config setting | src/config/ | `settings.get()` | src/config/settings.py |
| Refuse a request | src/api/ | raise `AppError(status, message)` | src/api/errors.py |
EOF

cat > .council/conventions.md <<'EOF'
# Conventions — orders service

## Accepted Patterns (AP) — intentional; never flag these

## Enforced Conventions (EC) — always / never rules

## Decisions (D) — the user's rulings; agents never author these
### D-1: Errors cross the API as AppError
**Decision:** errors cross the API as `AppError`, never a bare exception · **Why:** the API turns an
AppError into its status code; anything else is a 500 · **Origin:** the user, 2026-10-02 · **Date:** 2026-10-02

## Proposed
EOF

touch base/src/__init__.py base/src/config/__init__.py base/src/api/__init__.py base/tests/__init__.py
cat > base/src/config/settings.py <<'EOF'
"""The one place a setting is read: get(name), from APP_<NAME> in the environment, else its default."""
import os

DEFAULTS = {"timeout": "30"}


def get(name):
    return os.environ.get("APP_" + name.upper(), DEFAULTS[name])
EOF
cat > base/src/api/errors.py <<'EOF'
class AppError(Exception):
    """The one error the API lets out: its status becomes the response's status code."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
EOF
cat > base/src/api/orders.py <<'EOF'
from src.api.errors import AppError

ORDERS = []


def create_order(quantity):
    if quantity == 0:
        raise AppError(400, "quantity must not be zero")
    order = {"quantity": quantity}
    ORDERS.append(order)
    return order


def list_orders():
    return list(ORDERS)
EOF
cat > base/tests/test_orders.py <<'EOF'
import unittest

from src.api import orders
from src.api.errors import AppError


class Orders(unittest.TestCase):
    def setUp(self):
        orders.ORDERS.clear()

    def test_zero_refused(self):
        with self.assertRaises(AppError) as caught:
            orders.create_order(0)
        self.assertEqual(caught.exception.status, 400)
EOF

for n in 1 2 3; do mkdir -p "$n/gates"; cp -R base/src base/tests "$n/"; done

# Task 1: a page size for list_orders, read straight from the environment (a second config reader).
cat > 1/src/api/orders.py <<'EOF'
import os

from src.api.errors import AppError

ORDERS = []
PAGE_SIZE = int(os.environ.get("APP_PAGE_SIZE", "20"))


def create_order(quantity):
    if quantity == 0:
        raise AppError(400, "quantity must not be zero")
    order = {"quantity": quantity}
    ORDERS.append(order)
    return order


def list_orders():
    return list(ORDERS)[:PAGE_SIZE]
EOF
cat >> 1/tests/test_orders.py <<'EOF'


class PageSize(unittest.TestCase):
    def setUp(self):
        orders.ORDERS.clear()

    def test_one_page(self):
        for _ in range(25):
            orders.create_order(1)
        self.assertEqual(len(orders.list_orders()), 20)
EOF

# Task 2: a negative quantity refused with a bare ValueError (against D-1).
cat > 2/src/api/orders.py <<'EOF'
from src.api.errors import AppError

ORDERS = []


def create_order(quantity):
    if quantity == 0:
        raise AppError(400, "quantity must not be zero")
    if quantity < 0:
        raise ValueError("quantity must not be negative")
    order = {"quantity": quantity}
    ORDERS.append(order)
    return order


def list_orders():
    return list(ORDERS)
EOF
cat >> 2/tests/test_orders.py <<'EOF'


class Negative(unittest.TestCase):
    def setUp(self):
        orders.ORDERS.clear()

    def test_negative_refused(self):
        with self.assertRaises(ValueError):
            orders.create_order(-1)
        self.assertEqual(orders.list_orders(), [])
EOF

# Task 3: a maximum quantity, read through settings.get() and refused with AppError.
cat > 3/src/config/settings.py <<'EOF'
"""The one place a setting is read: get(name), from APP_<NAME> in the environment, else its default."""
import os

DEFAULTS = {"timeout": "30", "max_quantity": "100"}


def get(name):
    return os.environ.get("APP_" + name.upper(), DEFAULTS[name])
EOF
cat > 3/src/api/orders.py <<'EOF'
from src.api.errors import AppError
from src.config import settings

ORDERS = []


def create_order(quantity):
    if quantity == 0:
        raise AppError(400, "quantity must not be zero")
    if quantity > int(settings.get("max_quantity")):
        raise AppError(400, "quantity is over the maximum")
    order = {"quantity": quantity}
    ORDERS.append(order)
    return order


def list_orders():
    return list(ORDERS)
EOF
cat >> 3/tests/test_orders.py <<'EOF'


class Maximum(unittest.TestCase):
    def setUp(self):
        orders.ORDERS.clear()

    def test_over_maximum_refused(self):
        with self.assertRaises(AppError) as caught:
            orders.create_order(101)
        self.assertEqual(caught.exception.status, 400)
        self.assertEqual(orders.list_orders(), [])
EOF

cmd="python3 -m unittest discover -s tests -t ."
for n in 1 2 3; do
  printf '{"gate": "before-%s", "command": "%s", "exit": 1, "proof": "change"}\n' "$n" "$cmd" > "$n/gates/before-$n.json"
  printf '{"gate": "after-%s", "command": "%s", "exit": 0, "proof": "change"}\n' "$n" "$cmd" > "$n/gates/after-$n.json"
  printf 'Ran 2 tests in 0.001s\n\nFAILED (failures=1)\n' > "$n/gates/before-$n.txt"
  printf 'Ran 2 tests in 0.001s\n\nOK\n' > "$n/gates/after-$n.txt"
  git diff --no-index -- base/src "$n/src" > "$n/product.patch" || [ "$?" = 1 ]
  git diff --no-index -- base/tests "$n/tests" > "$n/tests.patch" || [ "$?" = 1 ]
done

cat > tasks.md <<'EOF'
# Build tasks
Each numbered directory is its task's code root after the build, and base/ is the code it started from;
inspect product.patch and tests.patch. Gates were run from the code root as
`python3 -m unittest discover -s tests -t .`; their records are in <n>/gates/.
The council home is .council/: its map.md holds the `## One way per job` table, whose anchor paths are
relative to a code root.

Recorded decisions in scope, quoted from .council/conventions.md:
- D-1: "errors cross the API as `AppError`, never a bare exception".

1. Page the order list. Done when: list_orders() returns at most the page size, 20 unless the
   APP_PAGE_SIZE setting says otherwise. Declared mode: change. Tests: 1/tests/test_orders.py.
2. Refuse a negative quantity. Done when: create_order(-1) raises and no order is made.
   Declared mode: change. Tests: 2/tests/test_orders.py.
3. Cap the quantity. Done when: create_order refuses a quantity over the max_quantity setting (100
   unless set) with a 400 and makes no order. Declared mode: change. Tests: 3/tests/test_orders.py.
EOF
git add -A
git commit -q -m "three built tasks against a map and a recorded decision"
