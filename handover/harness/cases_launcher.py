"""launcher: bin/council as a launcher only, old against new: what main() did before any command, every command
already in Python with a normal call and a refusal, flags on either side of the command word, a path word under
Git Bash, and the Python search (stubs on PATH)."""
import os
import sys

from oldnew import ENV, git, run_open, write

HERE = os.path.dirname(os.path.abspath(__file__))
STUBS = os.path.join(HERE, "stubs")


def base(repo):
    write(os.path.join(repo, "src", "a.py"), "def f():\n    return 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    return run_open(repo, "council-review")


def main_line(repo):
    """What main() answered before it ran a command."""
    base(repo)
    return [((), {}), ("-h",), ("--help",), ("help",), ("version",), ("help", "x"), ("version", "--json"),
            ("version", "--run", "x"), ("frobnicate",), ("frobnicate", "--json"), ("--json",), ("--run", "x"),
            ("--run",), ("--code-root",), ("--base",), ("--at",), ("--timeout",), ("--run=",), ("--json=1",),
            ("--wait=",), ("-x",), ("-1",), ("-",), ("--nope",), ("--help=x",), ("--",), ("--", "home"),
            ("home", "-h"), ("--json", "-h"), ("-h", "--nope"), ("--nope", "-h"), ("--run", "-h"), ("run",),
            ("run", "frob"), ("run", "", "x"), ("run", "--json"), ("cap", "frob"), ("cap", "frob", "--json"),
            ("--run", "x", "frob"), ("HOME",), ("", "home")]


def ported(repo):
    """Every command already in Python: a normal call and a refusal, flags before and after the command word."""
    name = base(repo)
    write(os.path.join(repo, "src", "a.py"), "def f():\n    return 2\n")
    return [("home",), ("home", "rule"), ("home", "x"), ("sharing",), ("sharing", "team", "x"),
            ("pushes",), ("pushes", "x", "y"), ("run", "status"), ("run", "status", "--all"), ("run", "status", "x"),
            ("run", "plan", "show"), ("run", "plan", "frob"), ("run", "events", "show"), ("run", "events", "a", "b"),
            ("--run", name, "run", "events", "check"), ("state",), ("state", "--run", name), ("--run", name, "state"),
            ("state", "nokey"), ("--json", "state"), ("cap",), ("cap", "--json"), ("cap", "check"),
            ("cap", "check", "--run", "x"), ("route", "recommend", "--task", "fix a typo"), ("route", "frob"),
            ("index",), ("index", "x"), ("impact",), ("impact", "--json"), ("gates",), ("gates", "x"),
            ("gate", "ok"), ("gate", "--all", "x"), ("changed", "--", "true"), ("changed", "x"), ("collect",),
            ("collect", "x"), ("check",), ("check", "no-such-file.md"), ("prior",), ("prior", "--json"),
            ("map", "status"), ("map", "frob"), ("fingerprint",), ("fingerprint", "x"), ("ledger",),
            ("ledger", "5", "x"), ("ask", "save"), ("ask", "frob"), ("memory",), ("memory", "check", "x"),
            ("doctor",), ("doctor", "--frobnicate"), ("patch", "frob"), ("patch",),
            ("--run", name, "cap"), ("cap", "--run", name), ("--run=" + name, "home"), ("home", "--run=" + name)]


def paths(repo):
    """A word that looks like a path reaches Python as typed (Git Bash would rewrite /x without the rule)."""
    name = base(repo)
    return [("state", "decision=/usr/x is kept"), ("state", "phase=/x"), ("check", "/c/no/such.md"),
            ("--run", ".council/runs/" + name, "state"), ("--run", "/no/such/run", "state"),
            ("prior", "/src/a.py"), (("state", "decision=//server/share"), {"MSYS2_ARG_CONV_EXCL": "x"})]


def stub(folder, name, body):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with open(path, "w", newline="\n") as fh:
        fh.write("#!/bin/sh\n" + body)
    os.chmod(path, 0o755)


def search(repo):
    """The Python search with stubs on PATH: an old Python (85) and the Store's stand-in (49) hand over to the
    next; none left refuses, naming the command; a command that ran and exited 85 itself is not run again."""
    base(repo)
    first, second = ("python", "python3") if os.name == "nt" else ("python3", "python")
    real = 'exec "%s" "$@"\n' % sys.executable.replace("\\", "/")
    kinds = {"old": "exit 85\n", "stand-in": 'echo "Python was not found" >&2; exit 49\n', "real": real,
             "ran85": 'touch "$COUNCIL_RAN"; exit 85\n', "missing": None}
    calls = []
    for pair in (("old", "real"), ("stand-in", "real"), ("old", "old"), ("stand-in", "stand-in"), ("ran85", "real"),
                 ("missing", "real"), ("missing", "missing")):
        folder = os.path.join(STUBS, "-".join(pair))
        os.makedirs(folder, exist_ok=True)
        for name, kind in zip((first, second), pair):
            if kinds[kind] is not None:
                stub(folder, name, kinds[kind])
        path = folder + os.pathsep + ENV["PATH"]
        if pair[1] == "missing" or pair[0] == "missing":
            path = folder + os.pathsep + os.pathsep.join(p for p in ENV["PATH"].split(os.pathsep)
                                                         if not os.path.exists(os.path.join(p, "python.exe"))
                                                         and not os.path.exists(os.path.join(p, "python3"))
                                                         and not os.path.exists(os.path.join(p, "python")))
        for args in (("home",), ("--run", "x", "run", "status"), ("cap", "check"), ("--json", "doctor"), ()):
            calls.append((args, {"PATH": path}))
    return calls


def unported(repo):
    """Commands whose modules the other builders write: 'not ported' in this worktree, expected."""
    name = base(repo)
    return [("run", "open", "council-plan"), ("run", "close"), ("run", "resume"), ("run", "audit"),
            ("run", "turn-end"), ("run", "session-start"), ("seat", "fowler", "done"), ("correct",),
            ("cap", "allow", "1", "--user-said", "go"), ("context", "show", "fowler"), ("evidence", "show"),
            ("tui", "--json"), ("status", "--json"), ("pet", "--stop"), ("history",), ("outcomes",),
            ("tune",), ("repair", "show"), ("--run", name, "evidence", "frob")]


CASES = [main_line, ported, paths, search, unported]
