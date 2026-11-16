"""commands: the stated differences of the clean-behaviours commands builder, old against new."""
import os

from cases_spine_a import plan
from oldnew import git, run_dir, run_open, write


def base(repo):
    write(os.path.join(repo, "a.txt"), "a\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    return run_open(repo, "council-review")


def index_cr_last_line(repo):
    """An untracked file whose last line has no newline and ends in CR: on Windows old cut the CR (a symbol)."""
    base(repo)
    write(os.path.join(repo, "tools.sh"), b"first() {\r\n  :\r\n}\r\nlast_one()\r", binary=True)
    return [("index",)]


def prior_tab(repo):
    """A mentioned line that holds a tab: old cut it at the first tab, new shows it whole (also in index.md)."""
    base(repo)
    write(os.path.join(repo, ".council", "reviews", "2026-09-05-tab.md"), "# t\n6 · P3 · a.txt:1\tthen\tmore words\n")
    write(os.path.join(repo, "a.txt"), "b\n")
    return [("prior", "a.txt"), ("index",), ("prior", "a.txt\nother.txt"), ("prior", "a.txt\r")]


def huge_state(repo):
    """A state over 4 MB: old read its stamp anyway; new names it with the next step."""
    base(repo)

    def grow(side):
        with open(os.path.join(run_dir(side), "session-state.md"), "a", encoding="utf-8") as f:
            f.write("x" * (4 * 1024 * 1024) + "\n")
    return [(("run", "events", "check"), None, grow)]


def skip_reason(repo):
    """A skip reason holding ;skipped=: the audit names the helper's own list (first wins)."""
    base(repo)
    plan(run_dir(repo))
    return [("state", "phase=judge", "skip=ruled;skipped=all of it"), ("run", "audit")]


def changed_flags(repo):
    base(repo)
    return [("changed", "--glob"), ("changed", "--glob=", "--", "true"), ("changed", "--glob", "a.txt", "extra"),
            ("changed", "--each=1"), ("version", "--each"), ("help", "--glob", "x"), ("changed", "--glob", "a.txt"),
            ("changed", "--glob", "a.txt", "--each", "--", "true")]


def control_gate(repo):
    """A gate command with an ESC and a form feed: old wrote a verdict json.loads refuses; new a space each."""
    base(repo)
    return [("gate", "ctl", "--", "echo 'a\x1bb\x0cc'"), ("status", "--json")]


CASES = [index_cr_last_line, prior_tab, huge_state, skip_reason, changed_flags, control_gate]
