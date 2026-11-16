"""spine-a: council state and council run events, old against new, on every path and refusal."""
import os
import re
import shutil

from oldnew import CONFIG, OLD, council, git, run_dir, run_open, write


def plan(run, selected=("chair",), size="squad", verification="independent"):
    """A valid run-plan v1 (evals/run_cli.py write_plan)."""
    selected = ["chair"] + [s for s in selected if s != "chair"]
    if size != "solo" and verification != "self":
        selected.append("verify-plan")
    mode = re.search(r"^mode:\s*(.+)$", open(os.path.join(run, "session-state.md"), encoding="utf-8").read(), re.M).group(1)
    rows = [("kind", "id", "field", "value", "reason"), ("schema", "plan", "version", "1", "v"),
            ("run", "run", "id", os.path.basename(run), "r"), ("run", "run", "mode", mode.strip(), "m"),
            ("run", "run", "size", size, "s"), ("assessment", "run", "risk", "medium", "r"),
            ("assessment", "run", "complexity", "medium", "c"), ("assessment", "run", "uncertainty", "medium", "u"),
            ("budget", "run", "agent-cap", "10", "a"), ("budget", "run", "estimated-tokens", "100000", "e"),
            ("verification", "run", "level", verification, "v")]
    for slug in selected:
        role = "chair" if slug == "chair" else "verifier" if slug.startswith("verify-") else "worker"
        rows += [("seat", slug, "disposition", "selected", "n"), ("seat", slug, "role", role, "r"),
                 ("context", slug, "level", "focused", "c"), ("budget", slug, "tool-calls", "15", "t")]
    write(os.path.join(run, "run-plan.tsv"), "\n".join("\t".join(r) for r in rows) + "\n")


def base(repo, mode="council-review", sharing="- sharing: team"):
    write(os.path.join(repo, "a.txt"), "a\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    return run_open(repo, mode, sharing)


def edit(fn):
    """A before-call that rewrites the run's state file bytes with fn(bytes)."""
    def go(repo):
        f = os.path.join(run_dir(repo), "session-state.md")
        data = open(f, "rb").read()
        open(f, "wb").write(fn(data))
    return go


def events_file(fn):
    def go(repo):
        f = os.path.join(run_dir(repo), "events.tsv")
        if fn is None:
            os.remove(f)
        else:
            data = open(f, "rb").read() if os.path.exists(f) else b""
            open(f, "wb").write(fn(data))
    return go


def legacy(repo):
    """No plan: a run from before plans takes any stage move without a plan check."""
    edit(lambda d: re.sub(rb"plan-schema: [^\n]*\n", b"", d))(repo)
    if os.path.exists(os.path.join(run_dir(repo), "run-plan.tsv")):
        os.remove(os.path.join(run_dir(repo), "run-plan.tsv"))


def refusals(repo):
    name = base(repo)
    return [("state", "nokv"), ("state", "Bad=1"), ("state", "=x"), ("state", ""), ("state", "status=done"),
            ("state", "status=complete"), ("state", "closed=now"), ("state", "decision=  \t"), ("state", "skip="),
            ("state", "phase=nope"), ("state", "phase=Prepare"), ("state", "phase="), ("state", "skip=why"),
            ("state", "phase=prepare", "skip=why"), ("state", "phase=judge"), ("state", "phase=brief"),
            ("state", "--foo"), ("state", "--status", "x"), ("state", "--run", "nosuch"), ("state", "phase=convene"),
            ("state", "a=1", "nokv"), ("state", "next=x", "status=bad"), ("state",), ("state", "--run", name),
            (("state", "status=paused"), {"CLOSING": "1"}), (("state", "closed=x"), {"CLOSING": "1"})]


def moves(repo):
    name = base(repo)
    secret = "decision=go with \"plan B\" \\ now\tand api_key=sk-abcdefghijklmnopqrstuvwxyz123456\vthen"
    return [(("state",), {}, legacy), ("state", "phase=prepare"), ("state", "next=a=b c"), ("state", "foo-1=bar\r\nx"),
            ("state", "waiting=which way?"), ("state", "waiting=which way?"), ("state", "waiting=other", "--run", name),
            ("state", "status=paused"), ("state", "next=paused"), ("state", "--run", name, "status=in-progress"),
            ("state", secret), ("state", "waiting=again"),
            ("state", "decision=yes"), ("state", "phase=judge"), ("state", "phase=deliver"),
            ("state", "phase=deliver", "skip=no time; now\r\nreally"), ("state", "phase=prepare", "next=mine"),
            ("state", "waiting="), ("state", "waiting="), ("state", "phase=learn", "skip=a", "skip=b"),
            ("state", "phase=learn", "phase=deliver"), ("state", "decision=after", "next=n"), ("state",),
            ("run", "events"), ("run", "events", "check"), ("run", "events", "repair"), ("run", "events", "show", "--run", name)]


def full_plan(repo):
    name = base(repo)
    return [(("state", "phase=assign"), {}, lambda r: plan(run_dir(r), selected=("chair", "hunt"))),
            ("state", "phase=prepare"), ("state", "phase=judge"),
            ("state", "phase=judge", "skip=the user ruled the seats out; Chair reads it alone"),
            ("state", "phase=work"), ("state", "phase=collect"), ("state", "phase=deliver"),
            ("state", "phase=challenge", "skip=x"), ("run", "events"),
            (("state", "phase=judge"), {}, lambda r: open(os.path.join(run_dir(r), "run-plan.tsv"), "a").write("bad\trow\n")),
            ("state", "--run", name, "phase=learn")]


def solo(repo):
    base(repo, "council-research")
    return [(("state", "phase=prepare"), {}, lambda r: plan(run_dir(r), size="solo", verification="self")),
            ("state", "phase=judge"), ("state", "phase=deliver"), ("state", "phase=challenge"),
            (("state", "phase=deliver"), {}, lambda r: os.remove(os.path.join(run_dir(r), "run-plan.tsv")))]


def implement(repo):
    base(repo, "council-implement")
    return [(("state", "phase=prepare"), {}, legacy), ("state", "phase=build"), ("state", "phase=deliver"),
            ("state", "phase=deliver", "skip=blocked: task 2"), ("state", "phase=build", "next=task 3"),
            ("state", "phase=prepare"), ("state", "phase=build")]


def own_phases(repo):
    base(repo, "test-architect")
    return [("state", "phase=my-step"), ("state", "phase=Bad"), ("state", "phase=-x"), ("state", "phase=a-"),
            ("state", "phase=prepare"), ("state", "phase=x1")]


def quiet(repo):
    name = base(repo, sharing="- sharing: team\n- notifications: off  # quiet")
    return [("state", "waiting=q"), ("state", "waiting=r", "--run", name), ("state", "phase=prepare"),
            ("state", "waiting=q")]


def closed(repo):
    name = base(repo)
    council(OLD, repo, "run", "close", "--status", "abandoned")
    return [("state", "--run", name, "deliverable=d.md"), ("state", "--run", name, "decision=keep it"),
            ("state", "--run", name, "ask=x", "ask-saved=y"), ("state", "--run", name, "phase=learn"),
            ("state", "--run", name, "next=x"), ("state", "--run", name, "status=in-progress"),
            ("state", "--run", name, "waiting=w"), ("state", "--run", name), ("run", "events", "--run", name)]


def damaged(repo):
    base(repo)
    tear = events_file(lambda d: d + b"1\t9\ttorn")
    return [(("state", "phase=prepare"), {}, tear), ("state", "next=fine"), ("state", "waiting=w"),
            ("run", "events", "check"), ("run", "events", "show"), ("run", "events", "repair"), ("run", "events", "repair"),
            ("run", "events"), ("state", "phase=prepare"),
            (("run", "events", "repair"), {}, events_file(lambda d: d + b"1\t99\t2026-01-01T00:00:00Z\tx\tr\tv\td\r\nzz")),
            (("state", "phase=judge"), {}, events_file(lambda d: b"schema\tseq\tat\ttype\tsubject\tvalue\tdetail\n")),
            ("run", "events", "repair"), ("run", "events", "check"), ("run", "events"),
            (("state", "status=paused"), {}, events_file(lambda d: d + b"not a row\n")), ("run", "events", "repair"),
            (("state", "status=paused"), {}, events_file(lambda d: b"")), ("run", "events", "check"),
            (("state", "status=paused"), {}, events_file(None)), ("run", "events", "repair"), ("run", "events", "check"),
            ("run", "events", "show"), ("state", "next=still")]


def schemas(repo):
    base(repo)
    return [(("run", "events", "check"), {}, edit(lambda d: d.replace(b"events-schema: 1", b"events-schema: 2"))),
            ("state", "phase=prepare"), ("run", "events", "repair"),
            (("run", "events"), {}, edit(lambda d: d.replace(b"events-schema: 2\n", b""))), ("state", "phase=prepare"),
            ("run", "events", "repair"),
            (("run", "events", "check"), {}, events_file(None)), ("run", "events", "show"), ("run", "events", "repair"),
            ("state", "phase=judge"), ("run", "events", "bogus"), ("run", "events", "a", "b"),
            ("run", "events", "--status", "x"), ("run", "events", ""), ("run", "events", "--run", "nosuch")]


def bytes_and_bom(repo):
    base(repo)
    return [(("state",), {}, edit(lambda d: b"\xef\xbb\xbf" + d.replace(b"\n", b"\r\n"))), ("state", "phase=prepare"),
            ("state", "decision=crlf ok"), (("state", "next=x"), {}, edit(lambda d: d + b"tail: no newline")),
            (("state", "decision=new heading"), {}, edit(lambda d: d.replace(b"## Decisions so far", b"## Other"))),
            (("state", "decision=last"), {}, edit(lambda d: d + b"\n## Decisions so far\n- old\n## Next\nbody\n")),
            (("state", "phase=judge", "waiting=w"), {}, legacy),
            ("state", "x=\xe9 "), ("state", "decision=\xe9 café")]


def held(repo):
    base(repo)

    def lock(name):
        def go(r):
            d = os.path.join(run_dir(r), name)
            os.makedirs(d, exist_ok=True)
            write(os.path.join(d, "owner"), "%d\n" % os.getpid())
        return go

    def unlock(r):
        for name in ("session-state.md.lock", "events.tsv.lock"):
            shutil.rmtree(os.path.join(run_dir(r), name), ignore_errors=True)
    return [(("state", "next=x"), {}, lock("session-state.md.lock")), (("run", "events"), {}, lambda r: (unlock(r), lock("events.tsv.lock")(r))),
            ("run", "events", "check"), ("state", "phase=prepare"), (("state", "next=y"), {}, unlock)]


def closing(repo):
    """CLOSING=1 and EVENTS_LOST=1 are the close's own; bin/council never takes them from the caller."""
    name = base(repo)
    tear = events_file(lambda d: d + b"1\t9\ttorn")

    def hold(r):
        d = os.path.join(run_dir(r), "events.tsv.lock")
        os.makedirs(d, exist_ok=True)
        write(os.path.join(d, "owner"), "%d\n" % os.getpid())
    return [("state", "waiting=q"), (("state", "status=paused"), {"CLOSING": "1"}, hold),
            (("state", "--run", name, "status=in-progress"), {"EVENTS_LOST": "1"},
             lambda r: (shutil.rmtree(os.path.join(run_dir(r), "events.tsv.lock")), tear(r)))]


CASES = [closing, refusals, moves, full_plan, solo, implement, own_phases, quiet, closed, damaged, schemas, bytes_and_bom, held]
