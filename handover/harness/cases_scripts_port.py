"""scripts builder: evidence, tui, status, pet, history, outcomes, run audit, context, tune, repair, old against new."""
import os
import re
import sys

import oldnew
from oldnew import OLD, council, git, run_dir, run_open, write

sys.path.insert(0, os.path.dirname(oldnew.__file__))
from cases_spine_a import edit, plan  # noqa: E402

NEW = os.path.normpath(os.path.join(os.path.dirname(oldnew.__file__), "..", "wt", "port"))
_norm = oldnew.norm


def norm(text, repo):
    """The plugin's own folder (the status's terminal-view command names it) is <P> on both sides, and the words
    old and new (each side's folder name is its project's name in the status) are <S>."""
    for root in (OLD, NEW):
        for form in oldnew.forms(root):
            text = text.replace(form, "<P>")
    return re.sub(r"\b(old|new)\b", "<S>", _norm(text, repo))


oldnew.norm = norm


def base(repo, mode="council-review"):
    write(os.path.join(repo, "a.txt"), "a\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    return run_open(repo, mode)


def refusals(repo):
    base(repo)
    return [("evidence",), ("evidence", "nope"), ("evidence", "build", "x"), ("evidence", "--json"),
            ("evidence", "build", "--json"), ("evidence", "", "x"),
            ("tui", "x"), ("tui", "--watch", "--json"), ("tui", "--widget"),
            ("status", "x"), ("status", "--widget", "--json"), ("status", "--json", "--line"), ("status", "--preview"),
            ("status", "--stop"), ("status", "--line", "--preview"),
            ("pet", "x"), ("pet", "--run", "x"), ("pet", "--json"),
            ("history", "x"), ("history", "--run", "x"), ("history", "--watch"),
            ("outcomes", "x"), ("outcomes", "--run", "x"), ("outcomes", "--line"),
            ("run", "audit", "x"), ("run", "audit", "--json"), ("run", "audit", "--run", "nosuch"),
            ("context",), ("context", "nope"), ("context", "build"), ("context", "build", "a", "b"),
            ("context", "show", "--expand", "x", "a"), ("context", "build", ".."), ("context", "build", "a/b"),
            ("context", "show", "bad seat"), ("context", "build", "a", "--json"), ("context", "show", "."),
            ("tune", "nope"), ("tune", "propose", "x"), ("tune", "--run", "x"), ("tune", "apply", "budget"),
            ("tune", "apply", "budget", "150k"), ("tune", "revert", "budget", "--json"), ("tune", "revert", "budget"),
            ("tune", "revert", "budget", "--run", "x", "--user-said", "y"), ("tune", "--user-said", "x"),
            ("tune", "apply", "budget", "1", "2", "--user-said", "y"), ("tune", "", "x"),
            ("repair",), ("repair", "nope"), ("repair", "record", "T1"), ("repair", "show", "a", "b"),
            ("repair", "allow"), ("repair", "allow", "g", "--user-said", " \t"), ("repair", "allow", "g"),
            ("repair", "record", "a", "b", "--json"), ("repair", "check", "--user-said", "x"),
            ("repair", "show", "--run", "nosuch")]


def no_home(repo):
    write(os.path.join(repo, "a.txt"), "a\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    return [("history",), ("history", "--json"), ("outcomes",), ("outcomes", "--json"), ("tune",),
            ("tune", "apply", "budget", "150k", "--user-said", "yes"), ("status",), ("tui",), ("evidence", "show"),
            ("run", "audit"), ("context", "show", "fowler"), ("repair", "show"), ("pet", "--stop")]


def reads(repo):
    name = base(repo)
    run = run_dir(repo)
    plan(run, selected=("chair", "fowler"))
    write(os.path.join(run, "card-due"), "due\n")
    return [("status", "--json"), ("status", "--widget"), ("status", "--widget", "--preview"), ("status", "--line"),
            ("status",), ("status", "--run", name), ("tui", "--json"), ("tui",), ("history",), ("history", "--json"),
            ("outcomes",), ("outcomes", "--json"), ("evidence", "build"), ("evidence", "show"), ("evidence", "check"),
            ("run", "audit"), ("run", "audit", "--transcript", "nosuch.jsonl"), ("run", "audit", "--run", name),
            (("run", "audit"), {"COUNCIL_RUN": run.replace("\\", "/")}),
            ("repair", "show"), ("repair", "check"), ("repair", "show", "T1"), ("tune",), ("tune", "propose", "--json"),
            ("tune", "revert", "budget", "--user-said", "go back"),
            ("tune", "apply", "budget", "150k", "--user-said", "yes\tdo it\r\napi_key=sk-abcdefghijklmnopqrstuvwxyz12345"),
            ("tune", "revert", "budget", "--user-said", "go back"), ("pet", "--stop"),
            ("context", "show", "fowler"), ("context", "build", "nosuch"), ("context", "build", "fowler"),
            ("context", "show", "fowler"), ("context", "build", "fowler", "--expand", "a.txt", "--expand", "a.txt"),
            ("context", "build", "fowler", "--expand", "../outside"), ("context", "show", "chair")]


def context_plans(repo):
    base(repo)
    run = run_dir(repo)

    def drop_plan(r):
        f = os.path.join(run_dir(r), "run-plan.tsv")
        if os.path.exists(f):
            os.remove(f)

    def bad_plan(r):
        write(os.path.join(run_dir(r), "run-plan.tsv"), "kind\tid\n")

    def no_level(r):
        plan(run_dir(r), selected=("chair", "fowler"))
        f = os.path.join(run_dir(r), "run-plan.tsv")
        data = open(f, encoding="utf-8").read()
        open(f, "w", encoding="utf-8").write(data.replace("context\tfowler\tlevel\tfocused\tc\n", ""))

    def no_brief(r):
        plan(run_dir(r), selected=("chair", "fowler"))
        os.remove(os.path.join(run_dir(r), "brief.md"))

    have_brief = os.path.exists(os.path.join(run, "brief.md"))
    calls = [(("context", "build", "fowler"), {}, drop_plan), (("context", "build", "fowler"), {}, bad_plan),
             (("context", "build", "fowler"), {}, no_level)]
    if have_brief:
        calls.append((("context", "build", "fowler"), {}, no_brief))
    return calls


def audit_newest(repo):
    base(repo)
    return [(("run", "audit"), {}, edit(lambda d: d.replace(b"status: in-progress", b"status: complete"))),
            ("run", "audit", "--transcript", "x.jsonl"),
            (("run", "audit"), {}, edit(lambda d: re.sub(rb"code-root: [^\n]*", b"code-root: /elsewhere", d)))]




CASES = [refusals, no_home, reads, context_plans, audit_newest]
