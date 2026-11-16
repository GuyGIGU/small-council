"""seat: council seat, council cap allow and council correct, old against new, on every path and refusal."""
import os
import re
import shutil

from oldnew import OLD, council, git, run_dir, run_open, write


def plan(run, selected=("chair",), cap="10", estimate="100000", extra=()):
    """A valid run-plan v1 (as cases_spine_a.plan), with the run's budget rows to choose."""
    selected = ["chair"] + [s for s in selected if s != "chair"] + ["verify-plan"]
    mode = re.search(r"^mode:\s*(.+)$", open(os.path.join(run, "session-state.md"), encoding="utf-8").read(),
                     re.M).group(1)
    rows = [("kind", "id", "field", "value", "reason"), ("schema", "plan", "version", "1", "v"),
            ("run", "run", "id", os.path.basename(run), "r"), ("run", "run", "mode", mode.strip(), "m"),
            ("run", "run", "size", "squad", "s"), ("assessment", "run", "risk", "medium", "r"),
            ("assessment", "run", "complexity", "medium", "c"), ("assessment", "run", "uncertainty", "medium", "u"),
            ("budget", "run", "agent-cap", cap, "a"), ("budget", "run", "estimated-tokens", estimate, "e"),
            ("verification", "run", "level", "independent", "v")] + list(extra)
    for slug in selected:
        role = "chair" if slug == "chair" else "verifier" if slug.startswith("verify-") else "worker"
        rows += [("seat", slug, "disposition", "selected", "n"), ("seat", slug, "role", role, "r"),
                 ("context", slug, "level", "focused", "c"), ("budget", slug, "tool-calls", "15", "t")]
    write(os.path.join(run, "run-plan.tsv"), "\n".join("\t".join(r) for r in rows) + "\n")


def base(repo, mode="council-review", **kw):
    write(os.path.join(repo, "a.txt"), "a\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    name = run_open(repo, mode)
    plan(run_dir(repo), **kw)
    return name


def put(name, data):
    """A before-call that writes a run file (None: removes it)."""
    def go(repo):
        f = os.path.join(run_dir(repo), name)
        if data is None:
            os.remove(f) if os.path.isfile(f) else shutil.rmtree(f, ignore_errors=True)
        else:
            write(f, data, binary=isinstance(data, bytes))
    return go


def edit(name, fn):
    def go(repo):
        f = os.path.join(run_dir(repo), name)
        data = open(f, "rb").read()
        open(f, "wb").write(fn(data))
    return go


def hold(name):
    def go(repo):
        d = os.path.join(run_dir(repo), name)
        os.makedirs(d, exist_ok=True)
        write(os.path.join(d, "owner"), "%d\n" % os.getpid())
    return go


def seat_refusals(repo):
    name = base(repo)
    s = "seat"
    return [(s,), (s, "a"), (s, "", "done"), (s, "a", "nope"), (s, "a/b", "done"), (s, "a b", "done"), (s, "a", "done", "x"),
            (s, "a", "done", "bogus=1"), (s, "a", "done", "agent"), (s, "a", "done", "agent=a b"), (s, "a", "done", "agent=Chair"),
            (s, "a", "done", "agent=small-council:council-worker"), (s, "a", "done", "tokens=1.2M"), (s, "a", "done", "tokens=74k"),
            (s, "a", "done", "tokens=74,3k"), (s, "a", "done", "tokens=12 tool uses, 45000 tokens"), (s, "a", "done", "tokens="),
            (s, "a", "done", "tokens=  "), (s, "a", "done", "tokens=500"), (s, "a", "done", "tokens=74304\n"),
            (s, "a", "done", "tokens=-5000"), (s, "a", "done", "tokens=1e5"), (s, "a", "done", "tokens=9999999999999"),
            (s, "a", "done", "tokens=74304 tokens\nx"), (s, "a", "done", "tokens=Tokens"), (s, "a", "done", "agents="),
            (s, "a", "done", "agents=x"), (s, "a", "done", "agents=1001"), (s, "a", "done", "agents=99999999999999999999"),
            (s, "a", "done", "tools="), (s, "a", "done", "tools=1.5"), (s, "a", "done", "tools=1234567"), (s, "a", "done", "tools=0000001"),
            (s, "a", "queued", "tokens=5000"), (s, "a", "running", "agents=1"), (s, "a", "skipped", "tools=3"),
            (s, "a", "done", "agents=0", "tokens=5000"), (s, "a", "done", "--status", "x"), (s, "a", "done", "--run", "nosuch"),
            (s, "a", "done", "tokens=5000", "tokens=12"), (s, "a", "done", "--", "x"), (s, "a", "running", "--run", name),
            (s, "a", "queued"), (s, "verify-9", "running"), ("seat", "--user-said", "x", "a", "done")]


def seat_flow(repo):
    name = base(repo, selected=("chair", "hunt", "fowler", "w", "verify-1", "verify-2"))
    s = "seat"
    return [(s, "hunt", "queued"), ("state", "waiting=which one?"), (s, "hunt", "running", "agent=a1"),
            (s, "fowler", "running", "agent=f1", "--run", name), (s, "hunt", "done", "agent=a1", "tokens=74,304", "tools=20"),
            (s, "hunt", "done", "tokens=80 000 tokens", "tools=21", "note=resumed\tonce\r\nmore"),
            (s, "hunt", "done", "tokens=60000"), (s, "fowler", "done", "tokens=1.5k"),
            (s, "fowler", "done", "tokens=150000", "agents=0"), (s, "fowler", "failed", "tokens=150000", "agents=3"),
            (s, "w", "done", "tokens=5000", "agents=1"), (s, "w", "done", "tokens=5000", "agents=1", "tools=4"),
            (s, "w", "done", "tokens=5000", "agents=01"), (s, "w", "blocked", "tokens=6000", "note=stuck"),
            (s, "verify-1", "running", "agent=v1"), (s, "verify-1", "done", "tokens=5000"),
            ((s, "verify-1", "done", "tokens=5000"), {}, put("verify-1b.md", "x\n")),
            ((s, "verify-1", "done", "tokens=5000"), {}, put("verify-1b.md", "")),
            ((s, "verify-1", "done", "tokens=5000"), {}, put("verify-1-a.md", "x\n")),
            ((s, "verify-2", "done", "tokens=5000"), {}, put("verify-2.md", "y\n")),
            (s, "verify-2", "done", "agents=0"), (s, "nosel", "queued"), (s, "nosel", "done", "tokens=7000"),
            (s, "chair", "done", "agents=0"), (s, "chair", "done", "agents=0", "agent=c1"), (s, "x", "skipped"),
            (s, "hunt", "done", "agent=a2", "tokens=3000", "tools=2"), ("run", "events"), ("cap",)]


def tool_hints(repo):
    base(repo, selected=("chair", "hunt", "w"))
    return [("seat", "hunt", "done", "tokens=5000"), ("seat", "w", "done", "tokens=6000"),
            ("seat", "w", "done", "tokens=7000", "tools=30"),
            (("seat", "hunt", "done", "tokens=8000", "tools=3"), {}, put("tools.tsv", None)),
            (("seat", "w", "done", "tokens=9000", "tools=3"), {}, put("tools.tsv", "at\tseat\tagent\ttools\n")),
            (("seat", "hunt", "done", "tokens=9100", "tools=40"), {}, put("tools.tsv", b"")),
            (("seat", "hunt", "done", "tokens=9200", "tools=5"), {}, lambda rp: (put("tools.tsv", None)(rp), hold("tools.tsv")(rp)))]


def cap_and_ceiling(repo):
    base(repo, selected=("chair", "a", "b", "c"), cap="4", estimate="20000",
                extra=[("budget", "run", "token-ceiling", "30000", "c"), ("budget", "run", "chair-tokens", "5000", "c")])
    s = "seat"
    return [(s, "a", "running", "agent=a1"), (s, "a", "done", "tokens=9000"), (s, "b", "running", "agent=b1"),
            (s, "b", "done", "tokens=9000"), (s, "c", "running", "agent=c1"), (s, "c", "done", "tokens=20000"),
            (s, "c", "running", "agent=c2"), (s, "c", "running", "agent=c3"),
            ("cap", "allow", "2", "--user-said", "yes go on\tplease token=sk-abcdefghijklmnopqrstuvwxyz123456"),
            (s, "c", "done", "agent=c4", "tokens=3000"), (s, "c", "done", "agent=c5", "tokens=3000"),
            ("cap",), ("run", "events"),
            ((s, "c", "done", "agent=c6", "tokens=3000"), {}, edit("session-state.md", lambda d: re.sub(rb"plan-schema: [^\n]*\n", b"", d)))]


def at_cap(repo):
    base(repo, selected=("chair", "a", "b"), cap="3", estimate="0")
    return [("seat", "a", "running", "agent=a1"), ("seat", "b", "running", "agent=b1"),
            ("seat", "verify-plan", "running", "agent=p1"),
            ("cap", "allow", "1", "--user-said", "ok"), ("seat", "b", "done", "tokens=4000"),
            ((("seat", "a", "done", "tokens=4000")), {}, put("events.tsv.lock", None))]


def legacy_rows(repo):
    base(repo, selected=("chair", "old", "new", "w"))
    old = "slug\tstate\tagent\ttokens\tupdated\tnote\nold\trunning\tx1\t40000\t2026-01-01 10:00\tn\nw\tqueued\t\t\t\t\n"
    return [(("seat", "old", "done", "agent=x2", "tokens=5000"), {}, put("seats.tsv", old)),
            ("seat", "old", "done", "tokens=6000"), ("seat", "new", "running", "agent=n1"),
            (("seat", "w", "running", "agent=w1"), {}, put("seats.tsv", "old\trunning\tx1\t7\t\t\t2\t\nw\tqueued\n")),
            (("seat", "w", "done", "tokens=5000"), {}, put("seats.tsv", "slug\tstate\tagent\ttokens\tupdated\tnote\tagents\n"
                                                               "w\trunning\tw1\t12x\t\t\t\n")),
            (("seat", "w", "done", "tokens=5000"), {}, put("usage.tsv", "at\tseat\tagent\tkind\truns\ttokens\n"
                                                                "t\tw\t\tfinished\t2\t\nt\tw\tz\tfinished\tx\t5\n"
                                                                "t\tw\tq\tfinished\t\t9999999999999\nt\tw\tw1\tdispatched\n")),
            (("seat", "w", "done"), {}, put("usage.tsv", b"")), ("seat", "w", "done", "agent=w9")]


def brief_files(repo):
    base(repo, selected=("chair", "hunt", "fowler", "plain"))
    brief = ("# Brief\n\n## Seats\n### hunt\n- ref: none\n- out: seats/hunt.md\n### fowler\n- **out:** `out/f.txt`\n"
             "## Other\n### plain\n")
    return [(("seat", "hunt", "done", "tokens=5000"), {}, put("brief.md", brief)),
            ((("seat", "hunt", "done", "tokens=5000")), {}, put("seats/hunt.md", "x\n")),
            ("seat", "hunt", "running", "note=round 2 of it"), ("seat", "hunt", "done", "tokens=6000"),
            ((("seat", "hunt", "done", "tokens=6000")), {}, put("seats/hunt-r2.md", "y\n")),
            ("seat", "fowler", "done", "tokens=5000"), ((("seat", "fowler", "done", "tokens=5000")), {}, put("out/f.txt", "z")),
            ("seat", "plain", "done", "tokens=5000"), ("seat", "fowler", "done", "agents=0")]


def closed_run(repo):
    name = base(repo, selected=("chair", "a", "b", "c", "d"))
    for call in (("seat", "a", "running", "agent=a1"), ("seat", "b", "queued"), ("seat", "c", "queued"),
                 ("seat", "d", "done", "agent=d1", "tokens=5000")):
        council(OLD, repo, *call)
    council(OLD, repo, "run", "close", "--status", "abandoned")
    r = ("--run", name)
    return [("seat", "chair", "done", "agents=0", *r), ("seat", "chair", "done", "agents=0", *r),
            ("seat", "a", "failed", *r), ("seat", "a", "failed", "agent=a2", *r), ("seat", "b", "skipped", *r),
            ("seat", "c", "failed", "note=gone", *r), ("seat", "d", "done", "tokens=7000", *r), ("seat", "e", "skipped", *r),
            ("cap", "allow", "1", "--user-said", "go", *r), ("correct", "d", "tokens=6000", "evidence=transcript line 40", *r),
            (("seat", "a", "failed", *r), {}, put("run-plan.tsv", None)),
            (("seat", "chair", "done", "agents=0", *r), {}, edit("session-state.md", lambda d: d.replace(b"status: abandoned",
                                                                                                b"status: complete"))),
            (("seat", "zz", "done", "agents=0", *r), {}, lambda rp: plan(run_dir(rp), selected=("chair", "zz", "a", "b", "c", "d"))),
            ("correct", "d", "tokens=6000", "evidence=transcript line 40", *r),
            ("correct", "zz2", "unrecorded=yes", "agents=1", "tokens=2000", "evidence=transcript line 41", *r)]


def closed_complete(repo):
    name = base(repo, selected=("chair", "a"))
    council(OLD, repo, "seat", "a", "running", "agent=a1")
    council(OLD, repo, "run", "close", "--status", "abandoned")
    done = edit("session-state.md", lambda d: d.replace(b"status: abandoned", b"status: complete"))
    return [(("seat", "a", "failed", "--run", name), {}, done), ("seat", "chair", "done", "agents=0", "--run", name)]


def damaged(repo):
    base(repo, selected=("chair", "a"))
    tear = edit("events.tsv", lambda d: d + b"1\t9\ttorn")
    return [(("seat", "a", "queued"), {}, tear), ("correct", "a", "tokens=5000", "evidence=transcript line 9"),
            ("cap", "allow", "1", "--user-said", "go"),
            (("seat", "a", "queued"), {}, put("events.tsv", "schema\tseq\tat\ttype\tsubject\tvalue\tdetail\n")),
            (("seat", "a", "queued"), {}, put("events.tsv", None)), ("cap", "allow", "1", "--user-said", "go"),
            ("seat", "a", "done", "agents=0")]


def plan_refusals(repo):
    base(repo, selected=("chair", "a"))
    return [(("seat", "a", "queued"), {}, put("run-plan.tsv", None)), ("seat", "a", "done", "tokens=5000"),
            (("seat", "a", "running"), {}, put("run-plan.tsv", "kind\tid\tfield\tvalue\treason\nbad\trow\n")),
            (("seat", "a", "running"), {}, lambda rp: (plan(run_dir(rp), selected=("chair", "a")),
                                                       edit("session-state.md", lambda d: re.sub(rb"plan-schema: [^\n]*\n", b"", d))(rp),
                                                       os.remove(os.path.join(run_dir(rp), "run-plan.tsv")))),
            ("seat", "b", "queued")]


def no_stream(repo):
    """A run from before the event stream: no events-schema, no events.tsv."""
    base(repo, selected=("chair", "a"))
    unstamp = edit("session-state.md", lambda d: re.sub(rb"events-schema: [^\n]*\n", b"", d))
    return [(("seat", "a", "running", "agent=a1"), {}, lambda rp: (unstamp(rp), os.remove(os.path.join(run_dir(rp), "events.tsv")))),
            ("cap", "allow", "3", "--user-said", "fine"), ("correct", "a", "agents=2", "evidence=the workflow log 3"),
            ("seat", "a", "done", "tokens=5000")]


def cap_allow(repo):
    name = base(repo)
    c = ("cap", "allow")
    return [c, c + ("1",), c + ("1", "2", "--user-said", "go"), c + ("1", "--user-said", " \t "), c + ("1", "--user-said", ""),
            c + ("0", "--user-said", "go"), c + ("000", "--user-said", "go"), c + ("abc", "--user-said", "go"),
            c + ("1001", "--user-said", "go"), c + ("-1", "--user-said", "go"), c + ("", "--user-said", "go"),
            c + ("00005", "--user-said", "go"), c + ("1", "--status", "x", "--user-said", "go"), ("cap", "bogus"),
            c + ("2", "--user-said=api_key=sk-abcdefghijklmnopqrstuvwxyz123456"), c + ("1", "--user-said", "ok\vthen\fnow\r\n"),
            (c + ("1", "--user-said", "torn"), {}, edit("cap-allowances.tsv", lambda d: d + b"2026\t3")),
            (c + ("1", "--user-said", "header"), {}, put("cap-allowances.tsv", b"")),
            ("state", "waiting=more?"), c + ("1", "--user-said", "go", "--run", name),
            (c + ("1", "--user-said", "held"), {}, hold("events.tsv.lock")),
            (c + ("1", "--user-said", "dir"), {}, lambda rp: (put("events.tsv.lock", None)(rp), put("cap-allowances.tsv", None)(rp),
                                                            os.makedirs(os.path.join(run_dir(rp), "cap-allowances.tsv")))),
            (c + ("1", "--user-said", "café é \ \"q\""), {}, put("cap-allowances.tsv", None)),
            c + ("1", "--user-said", "café é \\ \"q\"")]


def correct(repo):
    base(repo, selected=("chair", "a", "b"))
    for call in (("seat", "a", "running", "agent=a1"), ("seat", "a", "done", "tokens=5000"), ("seat", "b", "queued")):
        council(OLD, repo, *call)
    c = "correct"
    ev = "evidence=transcript line 12"
    return [(c,), (c, ""), (c, "a/b"), (c, "a", "x"), (c, "a", "tokens"), (c, "a", "unrecorded=no"), (c, "a"), (c, "a", ev),
            (c, "a", "tokens=1.2M", ev), (c, "a", "tokens=", ev), (c, "a", "tokens=1234567890123", ev),
            (c, "a", "tokens=0001234567890123", ev), (c, "a", "agents=x", ev), (c, "a", "agents=1001", ev),
            (c, "a", "agents=00001", ev), (c, "a", "agents=12345", ev), (c, "a", "tokens=5000"), (c, "a", "tokens=5000", "evidence=short"),
            (c, "a", "tokens=5000", "evidence=  ...  !!!  ---  "), (c, "a", "tokens=500", ev), (c, "a", "tokens=0", "agents=2", ev),
            (c, "a", "--status", "x", "tokens=5000", ev), (c, "nope", "tokens=5000", ev),
            (c, "a", "tokens=06000", ev), (c, "a", "agents=2", "tokens=7000", "evidence=log \"x\" \\ y\tz\x01\x7f é ünï"),
            (c, "b", "agents=0", "tokens=0", ev), (c, "a", "unrecorded=yes", "agents=1", ev), (c, "z", "unrecorded=yes", ev),
            (c, "z", "unrecorded=yes", "agents=0", ev), (c, "z", "unrecorded=yes", "agents=2", "tokens=9000", ev),
            (c, "z", "unrecorded=yes", "agents=1", ev), (c, "z", "tokens=9100", ev), ("seat", "z", "running", "agent=z1"),
            (c, "a", "tokens=8000", "evidence=" + "é" * 600), (c, "a", "tokens=8000", "evidence=" + "x" * 1200),
            ((c, "a", "tokens=8100", ev), {}, hold("seats.tsv.lock")),
            ((c, "a", "tokens=8200", ev), {}, lambda rp: (put("seats.tsv.lock", None)(rp), put("corrections.jsonl", None)(rp),
                                                        os.makedirs(os.path.join(run_dir(rp), "corrections.jsonl")))),
            ((c, "a", "tokens=8300", ev), {}, lambda rp: (put("corrections.jsonl", None)(rp),
                                                        edit("session-state.md", lambda d: d.replace(b"status: in-progress",
                                                                                                     b"status: complete"))(rp)))]


def held_seat(repo):
    base(repo, selected=("chair", "a"))
    return [(("seat", "a", "queued"), {}, hold("seats.tsv.lock")),
            (("seat", "a", "running", "agent=a1"), {}, lambda rp: (put("seats.tsv.lock", None)(rp), hold("events.tsv.lock")(rp))),
            (("seat", "a", "running", "agent=a1"), {}, lambda rp: (put("events.tsv.lock", None)(rp), put("usage.tsv", None)(rp),
                                                                 os.makedirs(os.path.join(run_dir(rp), "usage.tsv")))),
            (("seat", "a", "running", "agent=a1"), {}, lambda rp: (shutil.rmtree(os.path.join(run_dir(rp), "usage.tsv")),
                                                                 put("seats.tsv", None)(rp), os.makedirs(os.path.join(run_dir(rp), "seats.tsv"))))]


CASES = [closed_complete, seat_refusals, seat_flow, tool_hints, cap_and_ceiling, at_cap, legacy_rows, brief_files, closed_run, damaged,
         plan_refusals, no_stream, cap_allow, correct, held_seat]
