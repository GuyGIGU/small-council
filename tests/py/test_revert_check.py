"""Line ends: a saved round's patch is taken between git's trees, while the files on disk may be checked out with
CRLF (core.autocrlf, a text eol attribute) or hold CRLF as committed. The revert check's scratch copy is written from
the tree's own blobs and patched byte for byte, and the code root is patched under its own settings, so the round
comes off both, whatever this machine's own git config says."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support

from council import git
from council.commands import patch_apply, revert_check

CASES = (   # name, the repo's config, .gitattributes, the file at the start, the file once the round is done
    ("autocrlf true, CRLF on disk", "true", b"", b"one\r\ntwo\r\n", b"one\r\nTWO\r\n"),
    ("CRLF committed as is", "false", b"", b"one\r\ntwo\r\n", b"one\r\nTWO\r\n"),
    ("text eol=crlf attribute", "false", b"*.txt text eol=crlf\n", b"one\r\ntwo\r\n", b"one\r\nTWO\r\n"),
    ("LF", "false", b"", b"one\ntwo\n", b"one\nTWO\n"),
)


def run_git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo)] + list(args), check=True, capture_output=True).stdout


class LineEndTest(support.Scratch):
    def round_of(self, name: str, autocrlf: str, attributes: bytes, old: bytes, new: bytes) -> tuple[Path, str, Path]:
        """A repo whose one file the round changed: (the repo, the tree of the files on disk, the round's patch)."""
        repo = self.tmp / name.replace(" ", "-").replace(",", "").replace("=", "")
        repo.mkdir()
        run_git(repo, "init", "-q")
        run_git(repo, "config", "core.autocrlf", autocrlf)
        if attributes:
            (repo / ".gitattributes").write_bytes(attributes)
        (repo / "a.txt").write_bytes(old)
        run_git(repo, "add", "-A")
        run_git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "a")
        start = run_git(repo, "rev-parse", "HEAD^{tree}").decode().strip()
        (repo / "a.txt").write_bytes(new)
        tree = git.files_tree(repo)
        patch = self.write(repo.name + ".patch", git.output(repo, "diff", "--binary", "-M", "--src-prefix=a/",
                                                               "--dst-prefix=b/", start, tree), binary=True)
        return repo, run_git(repo, "rev-parse", start + ":a.txt").decode().strip(), patch

    def each_case(self, machine: str) -> None:
        """Every case, with this machine-wide core.autocrlf (none for '')."""
        config = self.write("machine-%s.gitconfig" % (machine or "none"),
                            "[core]\n\tautocrlf = %s\n" % machine if machine else "")
        with mock.patch.dict(os.environ, {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(config)}):
            for case in CASES:
                with self.subTest(case=case[0], machine=machine or "unset"):
                    repo, blob, patch = self.round_of(*case)
                    scratch = Path(tempfile.mkdtemp(prefix="council-revert-"))
                    self.addCleanup(shutil.rmtree, str(scratch), True)
                    self.assertEqual(revert_check.write_copy(str(repo), git.files_tree(repo), scratch), "")
                    self.assertEqual(patch_apply.undo(scratch, patch, raw=True), [])
                    self.assertEqual((scratch / "a.txt").read_bytes(), run_git(repo, "cat-file", "blob", blob))
                    self.assertEqual(patch_apply.undo(repo, patch), [])
                    self.assertEqual((repo / "a.txt").read_bytes(), case[3])

    def test_the_round_comes_off_with_no_machine_wide_autocrlf(self) -> None:
        self.each_case("")

    def test_the_round_comes_off_with_a_machine_wide_autocrlf(self) -> None:
        self.each_case("true")


if __name__ == "__main__":
    unittest.main()
