"""The council home's .gitignore (records/ignores.py): the answers bin/council's home_ignores and asks_shared gave
and the file its ensure_ignored wrote, written out."""
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

    def python(self, home: str) -> str:
        said = [ignores.ignores(home, p) for p in ("runs/x", "asks/x", "active-run", "cards/x")]
        return "".join("y" if s else "n" for s in said + [ignores.asks_shared(home)])

    def test_answers_in_and_outside_git(self) -> None:
        """runs/x, asks/x, active-run and cards/x ignored, then asks/ shared."""
        for git, text, said in ((True, b"runs/\n!asks/\n", "ynnny"), (True, b"/runs\r\nactive-run\r\n", "ynynn"),
                                (False, b" runs/ \nasks\n", "nynnn"), (True, None, "nnnnn")):
            with self.subTest(git=git, text=text):
                home = self.home(text, git)
                self.assertEqual(self.python(home), said)
                support.shutil.rmtree(str(self.tmp / ".council"))

    def test_keep_out_writes_what_ensure_ignored_wrote(self) -> None:
        for text, wrote in ((b"", b"runs/\nasks/\n"), (b"# mine\r\nruns/", b"# mine\r\nruns/\r\nasks/\r\n"),
                            (b"!asks/\n", b"!asks/\nruns/\n"), (None, b"runs/\nasks/\n"),
                            (b"runs/\nactive-run\n", b"runs/\nactive-run\nasks/\n")):   # an old line is left as it is
            with self.subTest(text=text):
                ignores.keep_out(self.home(text))
                self.assertEqual((self.tmp / ".council" / ".gitignore").read_bytes(), wrote)
                support.shutil.rmtree(str(self.tmp / ".council"))

    def test_shared_requests_are_left_tracked(self) -> None:
        home = self.home(b"!asks/\n")
        self.assertTrue(ignores.asks_shared(home))
        self.assertFalse(ignores.keep_out(home))
        self.assertNotIn(b"\nasks/", (self.tmp / ".council" / ".gitignore").read_bytes())


if __name__ == "__main__":
    unittest.main()
