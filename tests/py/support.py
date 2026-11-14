"""Shared setup for the records unit tests: src/ on the path, and a scratch folder per test."""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class Scratch(unittest.TestCase):
    """A test with its own empty folder, self.tmp, removed afterwards."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="council-test-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)

    def write(self, relative: str, content: str | bytes, binary: bool = False) -> Path:
        """Write a file under the scratch folder (str as UTF-8 with no newline translation)."""
        path = self.tmp / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if binary else content.encode("utf-8"))
        return path

    def run_folder(self, name: str = "2026-01-02-030405-council-review") -> Path:
        """An empty run folder inside a council home: <tmp>/.council/runs/<name>."""
        folder = self.tmp / ".council" / "runs" / name
        folder.mkdir(parents=True)
        return folder


HELPER = SRC.parent / "bin" / "council"


def helper_bash(test: unittest.TestCase, script: str, *words: str, env: dict | None = None) -> tuple[int, bytes]:
    """Run `script` in a bash that has sourced bin/council, its words as $1 …; (exit code, stdout bytes). Skips the
    test where there is no bash. For the bash a port leaves in place: the two readers must agree."""
    import os
    import subprocess

    from council.commands import shell
    bash = shutil.which("bash")
    if bash is None:
        test.skipTest("no bash")
    done = subprocess.run(shell.argv_for([bash, "-c", '. "$1"; shift; ' + script, "council", HELPER.as_posix(),
                                          *words]), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          env=dict(os.environ, **(env or {})))
    return done.returncode, done.stdout


def symlink_or_skip(test: unittest.TestCase, link: Path, target: Path, directory: bool = False) -> None:
    """Make a symlink, or skip the test where this machine doesn't allow one (Windows without rights)."""
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError) as exc:
        test.skipTest("symlinks unavailable here: {}".format(exc))
