"""close: council run close, old against new, on every path and refusal."""
import json
import os
import re
import shutil
from datetime import datetime, timezone

from cases_spine_a import base, edit, events_file, plan  # noqa: F401
from oldnew import OLD, council, run_dir, write

SEATS = "slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported\n"
DELIVER = ("state", "phase=deliver", "skip=the test is about the close")


def seats(rows):
    def go(r):
        write(os.path.join(run_dir(r), "seats.tsv"), SEATS + "".join("\t".join(row) + "\n" for row in rows))
    return go


def put(name, text):
    def go(r):
        write(os.path.join(run_dir(r), name), text)
    return go


def both(*fns):
    def go(r):
        for fn in fns:
            fn(r)
    return go


def planned(**kw):
    return lambda r: plan(run_dir(r), **kw)


def events_add(*rows):
    return events_file(lambda d: d + "".join("1\t%d\t2026-01-01T00:00:00Z\t%s\n" % (900 + i, row)
                                             for i, row in enumerate(rows)).encode())


def refusals(repo):
    name = base(repo)
    return [("run", "close", "--status", "bad"), ("run", "close", "extra"), ("run", "close", "--session", "s"),
            ("run", "close", "--run", "nosuch"), ("run", "close", "--status", "complete", "a", "b"),
            ("run", "close", "--foo"), ("run", "close", "--", "x"), ("run", "close", "--status="),
            ("run", "close"), ("run", "close", "--status", "paused"), ("run", "close", "--status", "paused"),
            ("run", "close", "--run", name), ("run", "close", "--status", "abandoned", "--run", name),
            ("run", "close", "--status", "abandoned", "--run", name), ("run", "close", "--run", name),
            ("run", "close", "--run", name, "--status", "paused"), ("run", "close")]


def delivered(repo):
    """A complete close with seats, synthesis and verify files, a deliverable, the ledger and the claims note."""
    name = base(repo)
    syn = "# Synthesis\n## Kept\n1 · a finding · from: hunt#1\n## Cut\n2 · cut one · from: beck#1\n"
    ver = "# Verification — r\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n| 1 | a | REFUTED | x |\n"
    return [(DELIVER, {}, planned(selected=("chair", "hunt", "beck"))), ("state", "deliverable=d.md"),
            (("run", "close"), {}, both(seats([("hunt", "done", "a", "150000", "-", "-", "1", "1"),
                                               ("beck", "done", "b", "20000", "-", "-", "1", "1"),
                                               ("verify-plan", "done", "c", "5000", "-", "-", "1", "1")]),
                                        put("synthesis.md", syn), put("verify-1.md", ver))),
            ("run", "close", "--run", name), ("run", "close", "--run", name, "--status", "abandoned")]


def bare_complete(repo):
    """No seats, no verify file, no deliverable, no request: every warning a complete close says."""
    base(repo)
    return [(DELIVER, {}, planned()), (("run", "close"), {}, put("verify-2.md", "nope\n")), ("run", "close")]


def legacy_retake(repo):
    """A run from before the stream closes complete at prepare (the phase warning), then is taken back."""
    name = base(repo)

    def legacy(r):
        edit(lambda d: re.sub(rb"events-schema: [^\n]*\n", b"", d))(r)
        os.remove(os.path.join(run_dir(r), "events.tsv"))
    return [(("state", "phase=prepare"), {}, legacy), (("run", "close"), {}, seats([("hunt", "done", "a", "1000", "-",
                                                                                     "-", "1", "1")])),
            ("ledger",), ("run", "close", "--status", "abandoned", "--run", name), ("ledger",),
            ("run", "close", "--status", "abandoned", "--run", name), ("run", "close", "--status", "paused", "--run", name)]


def went_back(repo):
    base(repo)
    return [(DELIVER, {}, planned(selected=("chair", "hunt"))), ("state", "phase=judge"), ("run", "close"),
            ("state", "phase=challenge"), ("run", "close"), ("state", "phase=deliver"), ("run", "close")]


def lost_stream(repo):
    base(repo)
    return [(DELIVER, {}, planned()), (("run", "close"), {}, events_file(None)), ("run", "events", "check")]


def empty_stream(repo):
    base(repo)
    return [(DELIVER, {}, planned()),
            (("run", "close", "--status", "paused"), {}, events_file(lambda d: b"schema\tseq\tat\ttype\tsubject\tvalue\t"
                                                                                b"detail\n"))]


def torn_stream(repo):
    base(repo)
    return [(DELIVER, {}, planned()), (("run", "close"), {}, events_file(lambda d: d + b"1\t9\ttorn")),
            ("run", "close", "--status", "abandoned"), ("run", "events", "repair"), ("run", "close")]


def busy(repo):
    base(repo)
    rows = [("hunt", "running", "a", "-", "-", "-", "1", "0"), ("beck", "queued", "-", "-", "-", "-", "0", "0"),
            ("fowler", "done", "c", "9000", "-", "-", "1", "1")]
    return [(("run", "close", "--status", "paused"), {}, both(planned(selected=("chair", "hunt")), seats(rows))),
            ("run", "resume"), ("run", "close", "--status", "abandoned")]


def gates_red(repo):
    base(repo)
    return [(DELIVER, {}, planned()),
            (("run", "close"), {}, events_add("gate.finished\tok\tfailed\t-", "gate.finished\tadhoc\tfailed\t-"))]


def gates_green(repo):
    base(repo)
    return [(DELIVER, {}, planned()),
            (("run", "close"), {}, events_add("gate.finished\tok\tfailed\t-", "gate.finished\tok\tpassed\t-"))]


def solo_self(repo):
    base(repo, "council-plan")
    return [(DELIVER, {}, planned(size="solo", verification="self")),
            (("run", "close"), {}, put("verify-self.md", "no shape\n"))]


def research_claims(repo):
    """A research run with a synthesis and no claim index, then an index older than a verify file."""
    name = base(repo, "council-research")
    return [(DELIVER, {}, planned()), (("run", "close"), {}, put("synthesis.md", "# S\n## Kept\n")),
            (("run", "close", "--run", name), {}, put("claims.jsonl", "")),
            (("run", "close", "--run", name), {}, lambda r: os.utime(os.path.join(run_dir(r), "claims.jsonl"), (1, 1)))]


def estimate_over(repo):
    base(repo)

    def chair_share(r):
        with open(os.path.join(run_dir(r), "run-plan.tsv"), "a") as fh:
            fh.write("budget\trun\tchair-tokens\t40000\tc\n")
    rows = [("hunt", "done", "a", "150000", "-", "-", "1", "1"), ("beck", "done", "b", "-", "-", "-", "1", "0")]
    return [(DELIVER, {}, both(planned(selected=("chair", "hunt", "beck")), chair_share)),
            (("run", "close", "--status", "paused"), {}, seats(rows)), ("run", "resume"),
            (("run", "close"), {}, seats(rows[:1]))]


def pointer(repo):
    name = base(repo)
    write(os.path.join(repo, ".council", "active-run"), ".council/runs/%s\r\nx\n" % name)
    return [("run", "close", "--status", "abandoned")]


def pointer_other(repo):
    base(repo)
    write(os.path.join(repo, ".council", "active-run"), ".council/runs/another\n")
    return [("run", "close", "--status", "abandoned")]


def build_log(text):
    def case(repo):
        name = base(repo, "council-implement")
        if text is not None:
            write(os.path.join(repo, ".council", "logs", "2026-01-01-x.md"), text.replace("NAME", name))
        write(os.path.join(repo, ".council", "logs", "2026-01-00-other.md"), "Run: 2026-other\n")
        return [(DELIVER, {}, planned()), ("run", "close")]
    case.__name__ = "build_log_%s" % ("none" if text is None else len(text))
    return case


def close_lock(repo):
    base(repo)

    def hold(r):
        d = os.path.join(run_dir(r), "close.lock")
        os.makedirs(d, exist_ok=True)
        write(os.path.join(d, "owner"), "%d\n" % os.getpid())
    return [(("run", "close"), {}, hold), (("run", "close", "--status", "paused"), {},
                                          lambda r: shutil.rmtree(os.path.join(run_dir(r), "close.lock")))]


def followup(repo):
    """The follow-up line from the record, said once: a second close with the same line stays quiet."""
    for i in range(5):
        past = os.path.join(repo, ".council", "runs", "2026-09-%02d-100000-review" % (i + 1))
        write(os.path.join(past, "session-state.md"), "status: complete\nmode: council-review\nphase: deliver\n"
                                                      "## Decisions so far\n")
        write(os.path.join(past, "run-plan.tsv"), "kind\tid\tfield\tvalue\treason\nrun\trun\tsize\tsquad\tr\n"
                                                  "budget\trun\testimated-tokens\t260000\tr\n")
        write(os.path.join(past, "seats.tsv"), SEATS + "".join("%s\tdone\ta\t400000\t-\t-\t1\t1\n" % s
                                                               for s in ("hunt", "beck", "verify-1")))
    base(repo)

    def again(r):
        council(OLD, r, "run", "open", "council-review")
        plan(run_dir(r), selected=("chair", "hunt"))
        council(OLD, r, *DELIVER)
    return [(DELIVER, {}, planned(selected=("chair", "hunt"))),
            (("run", "close"), {}, seats([("hunt", "done", "a", "20000", "-", "-", "1", "1")])),
            (("run", "close"), {}, both(again, seats([("hunt", "done", "a", "20000", "-", "-", "1", "1")])))]


def chair_usage(repo):
    """The Chair's own tokens from a transcript under CLAUDE_CONFIG_DIR: said, and recorded before the close."""
    base(repo)
    cfg = os.path.join(os.path.dirname(repo), "chaircfg")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def call(mid, fresh, write_):
        return json.dumps({"type": "assistant", "timestamp": now, "sessionId": "oldnew-session", "isSidechain": False,
                           "message": {"id": mid, "role": "assistant", "content": [{"type": "text", "text": "x"}],
                                       "usage": {"input_tokens": fresh, "cache_read_input_tokens": 0,
                                                 "cache_creation_input_tokens": write_, "output_tokens": 7}}}) + "\n"
    write(os.path.join(cfg, "projects", "p", "oldnew-session.jsonl"), call("m1", 3, 20000) + call("m2", 2, 33998))
    env = {"CLAUDE_CONFIG_DIR": cfg}
    return [(DELIVER, {}, planned()), (("run", "close", "--status", "paused"), env), (("run", "resume"), env),
            (("run", "close"), env)]


CASES = [refusals, delivered, bare_complete, legacy_retake, went_back, lost_stream, empty_stream, torn_stream, busy,
         gates_red, gates_green, solo_self, research_claims, estimate_over, pointer, pointer_other,
         build_log(None), build_log("Run: NAME\nbody\n"), build_log("Run: NAME\n## Shortcuts and concessions\nnone\n"),
         build_log("see NAME here\n## Shortcuts and concessions\n"), close_lock, followup, chair_usage]
