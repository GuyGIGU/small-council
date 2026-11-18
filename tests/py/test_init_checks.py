"""council init's detection: the checks read from a project's manifests and scripts, and the seats' surface markers
read from its file list."""
from __future__ import annotations

import unittest

import support

from council.commands import init_checks, init_seats, init_write


class ChecksTest(support.Scratch):
    def found(self, files: dict[str, str]) -> dict[str, init_checks.Check]:
        for path, text in files.items():
            self.write(path, text)
        return {check.name: check for check in init_checks.found(self.tmp, sorted(files))}

    def test_package_scripts_by_their_runner_and_kind(self) -> None:
        found = self.found({"package.json": '{"scripts": {"test": "jest", "test:watch": "jest --watch", "lint": "x",'
                                            ' "lint:fix": "x --fix", "build": "vite build", "format": "prettier -w .",'
                                            ' "check-types": "tsc", "dev": "vite"}}', "yarn.lock": "",
                            "tsconfig.json": "{}", ".eslintrc.json": "{}"})
        self.assertEqual(sorted(found), ["yarn-build", "yarn-check-types", "yarn-format", "yarn-lint", "yarn-test"])
        self.assertEqual((found["yarn-test"].command, found["yarn-check-types"].kind, found["yarn-build"].side,
                          found["yarn-format"].side), ("yarn run test", "type check", "writes the tree",
                                                       "writes the tree"))
        self.assertEqual(found["yarn-lint"].broken, "yarn run lint-not-a-script")

    def test_npm_placeholder_is_no_test_and_config_alone_offers_tsc_and_eslint(self) -> None:
        found = self.found({"package.json": '{"scripts": {"test": "echo \\"Error: no test specified\\" && exit 1"}}',
                            "tsconfig.json": "{}", "eslint.config.js": ""})
        self.assertEqual(sorted(found), ["eslint", "tsc"])
        self.assertEqual(found["tsc"].command, "npx --no-install tsc --noEmit")

    def test_python_tools_from_sections_and_dependencies_only(self) -> None:
        found = self.found({"pyproject.toml": "[tool.pytest.ini_options]\n[tool.mypy]\n[project]\nname='x'\n",
                            "requirements-dev.txt": "black==24.1\npytest-cov\n", "setup.cfg": "[flake8]\n"})
        self.assertEqual(sorted(found), ["black", "flake8", "mypy", "pytest"])
        self.assertEqual(found["pytest"].source, "pyproject.toml [tool.pytest.ini_options]")
        self.assertEqual(found["black"].source, "requirements-dev.txt names black")
        self.assertNotIn("ruff", self.found({"pyproject.toml": "[tool.ruffle]\n"}))

    def test_rust_and_go_offer_their_lints_only_with_config(self) -> None:
        self.assertEqual(sorted(self.found({"Cargo.toml": "[package]\n"})), ["cargo-test"])
        self.assertEqual(sorted(self.found({"Cargo.toml": "[lints.clippy]\n", "rustfmt.toml": ""})),
                         ["cargo-clippy", "cargo-fmt", "cargo-test"])

    def test_go_module(self) -> None:
        self.assertEqual(sorted(self.found({"go.mod": "module x\n"})), ["go-test", "go-vet"])

    def test_make_targets_cmake_and_scripts(self) -> None:
        found = self.found({"Makefile": "CC:=gcc\ntest: build\n\t./t\nlint:\nrelease:\ninstall:\nfmt-check:\n",
                            "CMakeLists.txt": "project(x)\nenable_testing()\n", "scripts/test.sh": "",
                            "tools/build.cmd": "", "deep/x/test.sh": "", "scripts/release.sh": ""})
        self.assertEqual(sorted(found), ["cmake-build", "ctest", "make-fmt-check", "make-lint", "make-test",
                                         "scripts-test-sh", "tools-build-cmd"])
        self.assertEqual((found["make-test"].probe, found["make-fmt-check"].side), ("make -n test", "none"))
        self.assertEqual(found["scripts-test-sh"].broken, "bash scripts/no-such-test.sh")
        self.assertEqual(found["tools-build-cmd"].command, 'cmd //c "tools\\build.cmd"')

    def test_nothing_shown_nothing_offered(self) -> None:
        self.assertEqual(self.found({"README.md": "run pytest and cargo test\n", "src/a.py": ""}), {})


class SeatsTest(unittest.TestCase):
    def test_markers_from_the_file_list(self) -> None:
        files = ["src/auth/login.py", "src/auth/tokens.py", "web/App.tsx", "web/a.css", "tests/test_a.py",
                 "db/migrations/1.sql", "README.md"]
        self.assertEqual(init_seats.markers("hunt", files), ("src/auth/**", "**/login.py", "**/tokens.py"))
        self.assertEqual(init_seats.markers("dodds", files), ("**/*.tsx",))
        self.assertEqual(init_seats.markers("saarinen", files), ("**/*.css", "**/*.tsx"))
        self.assertEqual(init_seats.markers("beck", files), ("**/test_*.py", "tests/**"))
        self.assertEqual(init_seats.markers("leach", files), ("**/*.sql", "db/**"))
        self.assertEqual(init_seats.markers("perf", files), ())
        self.assertEqual(init_seats.markers("fowler", files), ("whatever no other seat claims",))

    def test_the_catalog_as_it_names_its_seats(self) -> None:
        seats = init_seats.catalog(str(support.SRC.parent))
        self.assertEqual(len(seats), 14)
        self.assertIn(("Troy Hunt", "hunt", "Security", "references/security.md"), seats)
        self.assertIn(("Performance", "perf", "Performance", "references/quality-performance.md"), seats)


class GateRowTest(unittest.TestCase):
    CHECK = init_checks.Check("t", "test", "bash t.sh", "bash t.sh", "bash no-t.sh", "t.sh", "bash")

    def row(self, probed: dict[str, init_write.Probe]) -> str:
        return init_write.gate_row(self.CHECK, probed, "2026-11-18", "no probe-<name> ran")[0]

    def test_a_row_says_what_its_probes_found(self) -> None:
        ok, broken_fail = init_write.Probe(0, "bash t.sh", ""), init_write.Probe(127, "bash no-t.sh", "")
        self.assertEqual(self.row({"probe-t": ok, "probe-t-broken": broken_fail}),
                         "| t | `bash t.sh` | verify | yes | ✓ 2026-11-18 | `bash t.sh` · broken: fail, exit 127 "
                         "| bash | none |")
        self.assertIn("| no | ✓ 2026-11-18 | `bash t.sh` |", self.row({"probe-t": ok}))
        self.assertIn("| no | ✗ 2026-11-18: passes with its tool broken", self.row(
            {"probe-t": ok, "probe-t-broken": init_write.Probe(0, "x", "")}))
        self.assertIn("| ✗ 2026-11-18: probe exit 0, but it printed nothing |",
                      self.row({"probe-t": init_write.Probe(0, "bash t.sh", "exit 0, but it printed nothing")}))
        self.assertIn("| no | ✗ not probed: no probe-t ran | not run: `bash t.sh` |", self.row({}))

    def test_a_check_that_runs_and_fails_today(self) -> None:
        failed = init_write.Probe(1, "bash t.sh", "")
        gone = init_write.Probe(127, "bash no-t.sh", "never ran (exit 127)", "a command it calls was not found")
        self.assertIn("| no | ✓ 2026-11-18: runs, and fails today (probe exit 1) |",
                      self.row({"probe-t": failed, "probe-t-broken": gone}))
        self.assertIn("| no | ✗ 2026-11-18: probe failed, exit 1 |", self.row({"probe-t": failed}))
        ran_twin = init_write.Probe(2, "bash no-t.sh", "")
        self.assertIn("| ✗ ", self.row({"probe-t": failed, "probe-t-broken": ran_twin}))
        cannot = init_write.Probe(1, "python -m t", "", "Python has no module t")
        self.assertIn("| ✗ ", self.row({"probe-t": cannot, "probe-t-broken": gone}))

    def test_could_not_run_is_council_gates_own_reading(self) -> None:
        from council.commands import gate_output
        self.assertEqual(gate_output.could_not_run(127, "x: command not found\n"), "a command it calls was not found")
        self.assertEqual(gate_output.could_not_run(1, "/usr/bin/python: No module named ruff\n"),
                         "Python has no module ruff")
        self.assertEqual(gate_output.could_not_run(1, "src/a.py:1: E1 error\n"), "")


if __name__ == "__main__":
    unittest.main()
