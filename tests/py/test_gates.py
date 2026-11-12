import json
import unittest

import support

from council.records import gates


class GatesTest(support.Scratch):
    def test_slug_matches_the_helpers_byte_rule(self) -> None:
        self.assertEqual(gates.slug("tests"), "tests")
        self.assertEqual(gates.slug("unit tests/é"), "unit_tests___")
        self.assertEqual(gates.slug("a.b-c_d"), "a.b-c_d")

    def test_kind(self) -> None:
        self.assertEqual([gates.kind(n) for n in ("before-1", "regress-2", "probe-x", "after-1", "lint")],
                         ["proof", "proof", "probe", "check", "check"])

    def test_void_of(self) -> None:
        self.assertEqual(gates.void_of({"invalid": "wrong tree"}), "marked invalid (wrong tree)")
        self.assertEqual(gates.void_of({"timed_out": True}), "timed out")
        self.assertEqual(gates.void_of({"exit": 127}), "never ran (exit 127)")
        self.assertEqual(gates.void_of({"exit": 1, "timed_out": "yes"}), "")

    def test_failed_as_planned(self) -> None:
        self.assertTrue(gates.failed_as_planned({"name": "before-1", "exit": 1}))
        self.assertFalse(gates.failed_as_planned({"name": "before-1", "exit": 1, "proof": "preserve"}))
        self.assertFalse(gates.failed_as_planned({"name": "before-1", "exit": 1, "void": "timed out"}))
        self.assertFalse(gates.failed_as_planned({"name": "tests", "exit": 1}))

    def test_results_in_time_order(self) -> None:
        run = self.run_folder()
        (run / "gates").mkdir()
        (run / "gates" / "tests.json").write_text(json.dumps({"gate": "tests", "exit": 0, "seconds": 4,
                                                              "when": "2026-01-01 10:05:00", "command": "make test"}))
        (run / "gates" / "lint.json").write_text(json.dumps({"exit": "2", "when": "2026-01-01 10:01:00"}))
        (run / "gates" / "noise.json").write_text("not json")
        (run / "gates" / "plain.json").write_text(json.dumps({"gate": "plain"}))
        found = gates.results(run)
        self.assertEqual([(g["name"], g["exit"], g["proof"]) for g in found],
                         [("lint", 2, "change"), ("tests", 0, "change")])
        self.assertEqual(found[1]["seconds"], 4)
        self.assertEqual(gates.results(self.tmp), [])

    def test_files(self) -> None:
        run = self.run_folder()
        self.assertEqual(gates.files(run, "tests"), (run / "gates" / "tests.json", run / "gates" / "tests.txt"))
        self.assertEqual(gates.files(run, "tests", baseline=True)[0], run / "gates" / "baseline" / "tests.json")


if __name__ == "__main__":
    unittest.main()
