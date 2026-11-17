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

    def together(self, script: str, *each: str) -> list[str]:
        """Run the Python script once per word in each, all at the same moment, each its own process with src/ on its
        path and its word as sys.argv[1]; every process's stderr (all '' when each one finished cleanly)."""
        import subprocess
        procs = [subprocess.Popen([sys.executable, "-c", "import sys; sys.path.insert(0, %r)\n" % str(SRC) + script,
                                   word], cwd=str(self.tmp), stderr=subprocess.PIPE) for word in each]
        said = []
        for proc in procs:
            err = proc.communicate(timeout=120)[1].decode("utf-8", "replace")
            said.append(err if proc.returncode == 0 else "exit %d: %s" % (proc.returncode, err))
        return said



def symlink_or_skip(test: unittest.TestCase, link: Path, target: Path, directory: bool = False) -> None:
    """Make a symlink, or skip the test where this machine doesn't allow one (Windows without rights)."""
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError) as exc:
        test.skipTest("symlinks unavailable here: {}".format(exc))
