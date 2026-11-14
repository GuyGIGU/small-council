"""The council home's .gitignore (records/ignores.py) against bin/council's home_ignores, asks_shared and
ensure_ignored, which `council run open` keeps until S8b: the same answers and the same file written."""
from __future__ import annotations

import subprocess
import unittest

import support

from council.records import ignores


class IgnoresTest(support.Scratch):
    def home(self, gitignore: bytes | None, git: bool = True) -> str:
        if git:
            subprocess.run(["git", "init", "-q", str(self.tmp)], check=True)
        (self.tmp / ".council").mkdir(exist_ok=True)
        if gitignore is not None:
            self.write(".council/.gitignore", gitignore, binary=True)
        return (self.tmp / ".council").as_posix()

    def bash(self, home: str) -> list[str]:
        script = ('for p in runs/x asks/x active-run cards/x; do home_ignores "$1" "$p" && echo y || echo n; done; '
                  'asks_shared "$1" && echo y || echo n')
        return support.helper_bash(self, script, home)[1].decode().split()

    def python(self, home: str) -> list[str]:
        said = [ignores.ignores(home, p) for p in ("runs/x", "asks/x", "active-run", "cards/x")]
        return ["y" if s else "n" for s in said + [ignores.asks_shared(home)]]

    def test_answers_agree_in_and_outside_git(self) -> None:
        for git, text in ((True, b"runs/\n!asks/\n"), (True, b"/runs\r\nactive-run\r\n"), (False, b" runs/ \nasks\n"),
                          (True, None)):
            with self.subTest(git=git, text=text):
                home = self.home(text, git)
                self.assertEqual(self.python(home), self.bash(home))
                support.shutil.rmtree(str(self.tmp / ".council"))

    def test_keep_out_writes_what_ensure_ignored_writes(self) -> None:
        for text in (b"", b"# mine\r\nruns/", b"!asks/\n", None):
            with self.subTest(text=text):
                home = self.home(text)
                support.helper_bash(self, 'ensure_ignored "$1"', home)
                bash = (self.tmp / ".council" / ".gitignore").read_bytes()
                if text is None:
                    (self.tmp / ".council" / ".gitignore").unlink()
                else:
                    self.write(".council/.gitignore", text, binary=True)
                ignores.keep_out(home)
                self.assertEqual((self.tmp / ".council" / ".gitignore").read_bytes(), bash)
                support.shutil.rmtree(str(self.tmp / ".council"))

    def test_shared_requests_are_left_tracked(self) -> None:
        home = self.home(b"!asks/\n")
        self.assertTrue(ignores.asks_shared(home))
        self.assertFalse(ignores.keep_out(home))
        self.assertNotIn(b"\nasks/", (self.tmp / ".council" / ".gitignore").read_bytes())


if __name__ == "__main__":
    unittest.main()
