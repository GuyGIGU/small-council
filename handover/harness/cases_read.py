"""read: the reading rules (plan rows, line ends, numbers, code-root, the state header), old against new."""
import os

from oldnew import git, run_dir, run_open, write


def base(repo, mode="council-review"):
    write(os.path.join(repo, "a.txt"), "a\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    return run_open(repo, mode)


def plan_bytes(data):
    def go(repo):
        with open(os.path.join(run_dir(repo), "run-plan.tsv"), "wb") as f:
            f.write(data)
    return go


def plan_rows(repo):
    """Item 1: a CRLF plan, a padded value, repeated keys: the first row wins, values trimmed of blanks only."""
    base(repo)
    rows = (b"kind\tid\tfield\tvalue\treason\r\n"
            b"budget\trun\tagent-cap\t 2 \tfirst\r\n"
            b"budget\trun\tagent-cap\t7\tlater\r\n"
            b"budget\trun\testimated-tokens\t1 000\tinner blank\r\n"
            b"run\trun\tsize\tsolo\tfirst\r\n"
            b"run\trun\tsize\tfull\tlater\r\n"
            b"seat\thunt\trole\t worker \tpadded\r\n"
            b"seat\thunt\tdisposition\t selected\tpadded\r\n"
            b"budget\thunt\ttool-calls\t3\tfirst\r\n"
            b"budget\thunt\ttool-calls\t30\tlater\r\n")
    return [(("cap",), None, plan_bytes(rows)),
            ("seat", "hunt", "done", "agent=a1", "tokens=5000"),
            ("cap",),
            ("collect",),
            ("state", "phase=prepare"),
            ("state", "phase=judge"),
            ("status",)]


def crlf_state(repo):
    """Item 2: a CRLF state file is rewritten all LF (on Windows already so: the same here, new on Linux/macOS)."""
    name = base(repo)

    def crlf(r):
        f = os.path.join(run_dir(r), "session-state.md")
        data = open(f, "rb").read().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        open(f, "wb").write(data)
    return [(("state", "focus=one rule", "--run", name), None, crlf), ("run", "events", "show")]


def lf_only(repo):
    """Item 3: only LF ends a line of synthesis.md / a verify file for council evidence (a bare CR or FF is text)."""
    name = base(repo)

    def files(r):
        run = run_dir(r)
        os.makedirs(os.path.join(run, "seats"), exist_ok=True)
        write(os.path.join(run, "seats", "hunt.md"), "# Hunt\n## Index\n3 · P1 · Principle 1 · a.txt:1 · Expiry\n")
        with open(os.path.join(run, "synthesis.md"), "wb") as f:
            f.write("# Synthesis\n## Kept\n1 · P1 · Principle 1 · a.txt:1 · Expiry\rskipped · state: OBSERVED · "
                    "from: hunt#3\n2 · P2 · Principle 2 · a.txt:1 · Second\x0c · state: OBSERVED · from: hunt#3\n"
                    "## Cut\n(none)\n".encode())
        with open(os.path.join(run, "verify-1.md"), "wb") as f:
            f.write("# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
                    "| 1 | Expiry | CONFIRMED | a.txt:1\x0cmore |\n| 2 | Second | REFUTED | a.txt:1 |\r\n".encode())
    return [(("evidence", "build", "--run", name), None, files), ("evidence", "check", "--run", name),
            ("evidence", "show", "--run", name)]


def state_edit(fn):
    def go(r):
        f = os.path.join(run_dir(r), "session-state.md")
        data = open(f, "rb").read()
        open(f, "wb").write(fn(data))
    return go


def numbers(repo):
    """Item 4: a count is plain ASCII digits, 1 to 12; a 23-digit plan cap is no number; seat tokens 5abc add 0."""
    base(repo)

    def plan(r):
        f = os.path.join(run_dir(r), "run-plan.tsv")
        data = open(f, "rb").read().replace(b"budget\trun\tagent-cap\t10", b"budget\trun\tagent-cap\t" + b"9" * 23)
        open(f, "wb").write(data)

    def seats(r):
        f = os.path.join(run_dir(r), "seats.tsv")
        open(f, "wb").write(b"slug\tstate\tagent\ttokens\tupdated\tnote\nhunt\trunning\ta1\t5abc\tx\t\n")
    return [(("cap",), None, plan), (("seat", "hunt", "done", "tokens=1000"), None, seats), ("cap",)]


def code_root_dash(repo):
    """Item 5: a run whose state says code-root: - is this tree's, for council run status too."""
    base(repo)
    return [(("run", "status"), None, state_edit(lambda d: __import__("re").sub(rb"code-root: [^\n]*", b"code-root: -",
                                                                                d)))]


def header_only(repo):
    """Item 6: a status line under a heading never opens a run."""
    name = base(repo)
    fix = state_edit(lambda d: d.replace(b"status: in-progress", b"status: complete") + b"## Notes\nstatus: in-progress\n")
    return [(("run", "status"), None, fix), ("run", "status", "--all"), ("cap",), ("run", "open", "council-plan")]


CASES = [plan_rows, crlf_state, lf_only, numbers, code_root_dash, header_only]
