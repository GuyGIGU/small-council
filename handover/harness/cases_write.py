"""write: the stated differences of the write builder's items, old against new."""
import os
import re
import time

from cases_spine_a import base, edit
from oldnew import git, run_dir, write


def pointer_close(repo):
    """A2: an active-run naming the run is emptied by the old close, left by the new one."""
    name = base(repo)
    write(os.path.join(repo, ".council", "active-run"), ".council/runs/%s\n" % name)
    return [("run", "close", "--status", "abandoned")]


def pointer_doctor(repo):
    """A3: doctor's three active-run warnings (open run, closed run, missing folder)."""
    name = base(repo)

    def to(text):
        return lambda r: write(os.path.join(r, ".council", "active-run"), text)
    return [(("doctor",), {}, to(".council/runs/%s\n" % name)), (("doctor",), {}, to(".council/nowhere\n")),
            (("run", "close", "--status", "abandoned"), {}), (("doctor",), {}, to(".council/runs/%s\n" % name))]


def ignore_lines(repo):
    """A4: run open in a home with no .gitignore writes active-run (old) or not (new); an old line stays."""
    base(repo)

    def drop(r):
        os.remove(os.path.join(r, ".council", ".gitignore"))

    def old_line(r):
        write(os.path.join(r, ".council", ".gitignore"), "active-run\n")
    return [("run", "close", "--status", "abandoned"), (("run", "open", "council-plan"), {}, drop),
            ("run", "close", "--status", "abandoned"), (("run", "open", "council-plan"), {}, old_line)]


def minute_opened(repo):
    """Item 3: a just-me build whose opened: has no seconds; an hour-old untracked note names the council."""
    base(repo, "council-implement", sharing="- sharing: just me")

    def before(r):
        edit(lambda d: re.sub(rb"(?m)^(opened: \S+ \d\d:\d\d):\d\d$", rb"\1", d))(r)
        note = os.path.join(r, "NOTE.md")
        write(note, "# Note\nsee verify-1 and D-3\n")
        old = time.time() - 3600
        os.utime(note, (old, old))
    return [(("check",), {}, before)]


def memory_words(repo):
    """Item 4: a.b inside a.b.c, a binary file, an ignored file, a name only part of a word."""
    write(os.path.join(repo, ".council", "council.config.md"), "# c\n")
    write(os.path.join(repo, "src", "a.py"), "x = cfg.a.b.c\nkept_name = 1\n")
    write(os.path.join(repo, ".gitignore"), "build/\n")
    write(os.path.join(repo, "build", "out.py"), "ignored_name = 1\n")
    write(os.path.join(repo, "data.bin"), b"\0binary_only_name\nkept_name\n", binary=True)
    write(os.path.join(repo, ".council", "conventions.md"), "# m\n## Enforced Conventions\n"
          "### EC-1: dotted\n**Anchor:** a.b\n### EC-2: plain\n**Anchor:** kept_name\n"
          "### EC-3: ignored\n**Anchor:** ignored_name\n### EC-4: binary\n**Anchor:** binary_only_name\n"
          "### EC-5: part\n**Anchor:** ept_nam\n### EC-6: in its file\n**Anchor:** src/a.py::a.b\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "i")
    return [("memory", "check")]


CASES = [pointer_close, pointer_doctor, ignore_lines, minute_opened, memory_words]
