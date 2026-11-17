#!/usr/bin/env bash
# A small Python shop with two decision records: 0001 (money as float dollars) is superseded by 0002
# (money as integer cents, never floats), which the code follows. council-init should carry 0002 into
# memory as a PROPOSED decision citing its file:line, leave 0001 out, and write nothing before the user
# confirms. No .council/ yet. Self-contained.
set -euo pipefail
git init -q
git config user.email eval@example.invalid
git config user.name eval
mkdir -p docs/adr src/shop tests

cat > README.md <<'EOF'
# Tiny shop
A cart and its totals. `python3 -m unittest discover -s tests -t .` runs the tests.
EOF

cat > docs/adr/0001-money-as-float-dollars.md <<'EOF'
# 1. Money as float dollars

Status: Superseded by 0002

## Decision
Amounts are float dollars, rounded to two places when shown.
EOF

cat > docs/adr/0002-money-as-integer-cents.md <<'EOF'
# 2. Money as integer cents

Status: Accepted (2026-09-14)

## Context
Float dollars drifted: a cart of three 0.10 items totalled 0.30000000000000004.

## Decision
Every amount is an integer number of cents, never a float. Only `shop.money.format_cents` turns
cents into text.

## Consequences
Prices in the catalogue are entered in cents.
EOF

touch src/__init__.py src/shop/__init__.py tests/__init__.py
cat > src/shop/money.py <<'EOF'
"""Amounts are integer cents (docs/adr/0002-money-as-integer-cents.md)."""


def format_cents(cents):
    sign = "-" if cents < 0 else ""
    return "%s$%d.%02d" % (sign, abs(cents) // 100, abs(cents) % 100)
EOF
cat > src/shop/cart.py <<'EOF'
from src.shop.money import format_cents


class Cart:
    def __init__(self):
        self.lines = []

    def add(self, name, price_cents, quantity=1):
        if not isinstance(price_cents, int):
            raise TypeError("prices are integer cents")
        self.lines.append((name, price_cents, quantity))

    def total_cents(self):
        return sum(price * quantity for _, price, quantity in self.lines)

    def receipt(self):
        return "\n".join("%s x%d %s" % (name, quantity, format_cents(price * quantity))
                         for name, price, quantity in self.lines) + "\nTotal " + format_cents(self.total_cents())
EOF
cat > tests/test_cart.py <<'EOF'
import unittest

from src.shop.cart import Cart


class Totals(unittest.TestCase):
    def test_three_dimes(self):
        cart = Cart()
        cart.add("dime sweet", 10, 3)
        self.assertEqual(cart.total_cents(), 30)
        self.assertTrue(cart.receipt().endswith("Total $0.30"))

    def test_float_refused(self):
        with self.assertRaises(TypeError):
            Cart().add("float sweet", 0.10)
EOF
git add -A
git commit -q -m "a tiny shop and its decision records"
