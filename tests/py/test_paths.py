import os
import stat
import unittest

import support

from council.records import home, paths


class ReadTest(support.Scratch):
    def test_text_of_drops_the_bom_and_reads_missing_as_empty(self) -> None:
        self.write("a.md", "﻿status: done\n")
        self.assertEqual(paths.text_of(self.tmp / "a.md"), "status: done\n")
        self.assertEqual(paths.text_of(self.tmp / "missing.md"), "")
        self.assertEqual(paths.text_of(self.tmp), "")

    def test_text_of_refuses_a_file_over_its_limit(self) -> None:
        self.write("big.md", "x" * 11)
        self.assertEqual(paths.text_of(self.tmp / "big.md", limit=10), "")
        self.assertEqual(paths.text_of(self.tmp / "big.md", limit=11), "x" * 11)

    def test_text_of_strict_reads_bad_utf8_as_empty(self) -> None:
        self.write("bad.md", b"ok \xff", binary=True)
        self.assertEqual(paths.text_of(self.tmp / "bad.md"), "ok �")
        self.assertEqual(paths.text_of(self.tmp / "bad.md", errors="strict"), "")

    def test_text_of_refuses_a_link(self) -> None:
        target = self.write("real.md", "secret")
        support.symlink_or_skip(self, self.tmp / "link.md", target)
        self.assertTrue(paths.linked(self.tmp / "link.md"))
        self.assertEqual(paths.text_of(self.tmp / "link.md"), "")

    def test_contained(self) -> None:
        inside = self.write("run/x.md", "")
        self.assertTrue(paths.contained(inside, self.tmp / "run"))
        self.assertFalse(paths.contained(self.tmp / "other.md", self.tmp / "run"))

    def test_artifact_refusals_name_the_file_and_limit(self) -> None:
        self.assertIsNone(paths.artifact(self.tmp / "none.md", 1024, required=False))
        with self.assertRaisesRegex(paths.RecordError, "missing artifact"):
            paths.artifact(self.tmp / "none.md", 1024)
        self.write("big.md", "x" * (1024 * 1024 + 1))
        with self.assertRaisesRegex(paths.RecordError, "not a regular file under 1 MB"):
            paths.artifact(self.tmp / "big.md", 1024 * 1024)
        self.assertEqual(paths.artifact(self.write("ok.md", "hi"), 1024), b"hi")

    def test_universal_newlines(self) -> None:
        self.assertEqual(paths.universal("a\r\nb\rc\n"), "a\nb\nc\n")


class WriteTest(support.Scratch):
    def test_atomic_write_replaces_and_leaves_no_temporary(self) -> None:
        target = self.write("out.txt", "old")
        paths.atomic_write(target, b"new", prefix=".t-")
        self.assertEqual(target.read_bytes(), b"new")
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["out.txt"])

    @unittest.skipIf(os.name == "nt", "POSIX permissions")
    def test_keep_mode_keeps_permissions(self) -> None:
        target = self.write("cfg.md", "a")
        os.chmod(str(target), 0o640)
        paths.atomic_write(target, b"b", prefix=".t-", keep_mode=True)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)

    def test_refuse_link(self) -> None:
        target = self.write("real.txt", "x")
        support.symlink_or_skip(self, self.tmp / "link.txt", target)
        with self.assertRaisesRegex(paths.RecordError, "symlink output is not allowed"):
            paths.atomic_write(self.tmp / "link.txt", b"y", prefix=".t-", refuse_link=True)
        self.assertEqual(target.read_bytes(), b"x")


class HomeTest(support.Scratch):
    def test_run_folders_need_a_state_file_and_keep_the_newest(self) -> None:
        home = self.tmp / ".council"
        for name in ("2026-01-01-000000-council-plan", "2026-01-02-000000-council-review", "notes"):
            (home / "runs" / name).mkdir(parents=True)
        for name in ("2026-01-01-000000-council-plan", "2026-01-02-000000-council-review"):
            (home / "runs" / name / "session-state.md").write_text("status: done\n")
        self.assertEqual([p.name for p in paths.run_folders(home)],
                         ["2026-01-01-000000-council-plan", "2026-01-02-000000-council-review"])
        self.assertEqual([p.name for p in paths.run_folders(home, 1)], ["2026-01-02-000000-council-review"])
        self.assertEqual(len(paths.run_folders(home, require_state=False)), 3)
        self.assertEqual(paths.run_folders(self.tmp / "nowhere"), [])

    def test_is_run_and_home_of(self) -> None:
        run = self.run_folder()
        self.assertFalse(paths.is_run(run))
        (run / "session-state.md").write_text("status: in-progress\n")
        self.assertTrue(paths.is_run(run))
        self.assertEqual(paths.home_of(run), self.tmp / ".council")
        self.assertIsNone(paths.home_of(self.tmp))

    def test_worktrees_and_home_from(self) -> None:
        porcelain = "worktree /main\nHEAD a\nbranch x\n\nworktree /wt\nHEAD b\n"
        self.assertEqual(home.worktrees(porcelain), ["/main", "/wt"])
        self.assertEqual(home.worktrees("worktree /repo\nbare\n\nworktree /a\nHEAD c\n"), ["(bare)", "/a"])
        there = {"/main/.council"}
        self.assertEqual(home.home_from("/wt", "", porcelain, there.__contains__), "/main/.council")
        self.assertEqual(home.home_from("/sub", "/super", porcelain, there.__contains__), "/sub/.council")
        older = {"/wt/.council"}                       # a 0.1 council inside a worktree, none in the main one
        self.assertEqual(home.home_from("/wt", "", porcelain, older.__contains__), "/wt/.council")
        bare = "worktree /repo\nbare\n\nworktree /a\nHEAD c\n\nworktree /b\nHEAD d\n"
        configured = {"/b/.council/council.config.md", "/b/.council", "/a/.council"}
        self.assertEqual(home.home_from("/a", "", bare, configured.__contains__), "/b/.council")


if __name__ == "__main__":
    unittest.main()
