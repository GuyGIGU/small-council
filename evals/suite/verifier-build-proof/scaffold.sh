#!/usr/bin/env bash
# Four independent snapshots; deliberately misleading evidence is part of the fixture.
set -euo pipefail
git init -q
git config user.email eval@example.invalid
git config user.name eval
for n in 1 2 3 4; do mkdir -p "$n/gates"; done
cat > 1/before.py <<'EOF'
"""Totals for signed integer amounts in minor units."""


def total(values):
    result = 0
    for value in values:
        result += value
    return result
EOF
cat > 1/module.py <<'EOF'
"""Totals for signed integer amounts in minor units."""


def total(values):
    return sum(values)
EOF
cat > 1/test_module.py <<'EOF'
import unittest
from module import total


class Totals(unittest.TestCase):
    def test_signed(self):
        self.assertEqual(total([2, -5]), -3)

    def test_empty(self):
        self.assertEqual(total([]), 0)

    def test_iterable(self):
        self.assertEqual(total(iter([2, -5])), -3)
EOF
cp 1/test_module.py 1/before_test.py
cat > 2/before.py <<'EOF'
def average(values):
    return sum(values) / len(values)
EOF
cp 2/before.py 2/module.py
cat > 2/test_module.py <<'EOF'
import unittest
from module import average


class Average(unittest.TestCase):
    def test_nonempty(self):
        self.assertEqual(average([2, 4]), 3)
EOF
cp 2/test_module.py 2/before_test.py
cp 1/before.py 3/before.py
cat > 3/module.py <<'EOF'
"""Totals for signed integer amounts in minor units."""


def total(values):
    return sum(value for value in values if value >= 0)
EOF
cat > 3/before_test.py <<'EOF'
import unittest
from module import total


class Totals(unittest.TestCase):
    def test_signed(self):
        self.assertEqual(total([2, -5]), -3)
EOF
cat > 3/test_module.py <<'EOF'
import unittest
from module import total


class Totals(unittest.TestCase):
    def test_signed(self):
        self.assertGreaterEqual(total([2, -5]), -3)
EOF
cp 2/before.py 4/before.py
cat > 4/module.py <<'EOF'
def average(values):
    return sum(values) / len(values) if values else None
EOF
cat > 4/test_module.py <<'EOF'
import unittest
from module import average


class Average(unittest.TestCase):
    def test_empty(self):
        self.assertIsNone(average([]))
EOF
cp 4/test_module.py 4/before_test.py
for n in 1 2 3 4; do
  mode=preserve; bex=0
  [ "$n" != 4 ] || { mode=change; bex=127; }
  printf '{"gate": "before-%s", "command": "python3 -m unittest test_module.py", "exit": %s, "proof": "%s"}\n' "$n" "$bex" "$mode" > "$n/gates/before-$n.json"
  printf '{"gate": "after-%s", "command": "python3 -m unittest test_module.py", "exit": 0, "proof": "%s"}\n' "$n" "$mode" > "$n/gates/after-$n.json"
  count=1; [ "$n" != 1 ] || count=3
  printf 'Ran %s tests in 0.001s\n\nOK\n' "$count" > "$n/gates/before-$n.txt"
  cp "$n/gates/before-$n.txt" "$n/gates/after-$n.txt"
  git diff --no-index -- "$n/before.py" "$n/module.py" > "$n/product.patch" || [ "$?" = 1 ]
  git diff --no-index -- "$n/before_test.py" "$n/test_module.py" > "$n/tests.patch" || [ "$?" = 1 ]
done
printf 'python3: command not found\n' > 4/gates/before-4.txt
cat > tasks.md <<'EOF'
# Build tasks
Each numbered directory is its task's code root; inspect both product.patch and tests.patch.
Governing reference: references/quality-testing.md. Artifacts are in <n>/gates/.

1. Refactor integer total to sum. Done when: signed integer values, empty inputs and iterables retain their results.
   Declared mode: preserve. Invariants: total([2,-5]) == -3, total([]) == 0,
   total(iter([2,-5])) == -3. Tests: 1/test_module.py; unchanged from 1/before_test.py.
2. Fix empty average. Done when: average([]) returns None, nonempty means retain their results.
   Declared mode: preserve. Invariant offered: average([2,4]) == 3.
   Tests: 2/test_module.py; unchanged from 2/before_test.py.
3. Refactor integer total. Done when: signed integer totals retain their results, including total([2,-5]) == -3.
   Declared mode: preserve. Tests: 3/test_module.py; original in 3/before_test.py.
4. Fix empty average. Done when: average([]) returns None with a failing-before/passing-after check.
   Declared mode: change. Tests: 4/test_module.py; original in 4/before_test.py.
EOF
git add -A
git commit -q -m "four build proof snapshots"
