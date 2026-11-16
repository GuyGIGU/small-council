"""runs: council run open, run resume and run turn-end, old against new, on every path and refusal."""
import os
import re

from oldnew import CONFIG, OLD, council, git, run_dir, run_open, write

MODES = ("council-review", "council-plan", "council-implement", "council-research", "council-postgame",
         "council-init", "test-architect", "context-core")
TE = ("run", "turn-end", "--session", "oldnew-session")
SEATS = "slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported\n"


def commit(repo, config=True, sharing="- sharing: team"):
    write(os.path.join(repo, "a.txt"), "a\n")
    if config:
        write(os.path.join(repo, ".council", "council.config.md"), CONFIG % sharing)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")


def edit(fn, name=None):
    def go(repo):
        f = os.path.join(run_dir(repo, name), "session-state.md")
        data = open(f, "rb").read()
        open(f, "wb").write(fn(data))
    return go


def setf(key, value, name=None):
    return edit(lambda d: re.sub(rb"(?m)^" + key.encode() + rb":[^\r\n]*", (key + ": " + value).encode(), d), name)


def each_mode(mode):
    def case(repo):
        commit(repo)
        return [("run", "open", mode), ("run", "events")]
    case.__name__ = "mode_" + mode.replace("-", "_")
    return case


def refusals(repo):
    commit(repo)
    return [("run", "open"), ("run", "open", "review"), ("run", "open", "council-review", "council-plan"),
            ("run", "open", "council-review", "--status", "x"),
            ("run", "open", "council-review", "--alongside=1"), ("run", "open", "", "--session=s"),
            (("run", "open", "council-review"), {"CLAUDE_CODE_SESSION_ID": "unmarked"}),
            (("run", "open", "council-review"), {"CLAUDE_CODE_SESSION_ID": "bad id/x"}),
            (("run", "open", "council-review", "--alongside"), {"CLAUDE_CODE_SESSION_ID": "unmarked",
                                                                "COUNCIL_ALLOW_NO_HOOKS": "1"}),
            (("run", "open", "council-review", "--alongside"), {"CLAUDE_CODE_SESSION_ID": ""}),
            ("run", "open", "--run", "x", "council-review", "--alongside"),
            ("run", "resume", "x"), ("run", "resume", "--status", "x"), ("run", "turn-end", "x"),
            ("run", "turn-end", "--run", "x", "--session", "s"), ("run", "turn-end", "--alongside"),
            ("run", "open", "council-review", "--", "x")]


def second(repo):
    commit(repo)
    return [("run", "open", "council-review"), ("run", "open", "council-plan"),
            ("run", "open", "council-plan", "--alongside", "--session=other"), ("run", "resume"), ("run", "events")]


def paused(repo):
    commit(repo)
    name = run_open(repo, "council-review")
    council(OLD, repo, "state", "status=paused")
    return [("run", "open", "council-research"), ("run", "resume"),
            (("run", "resume", "--run", name), {}, setf("status", "paused", name))]


def no_home(repo):
    commit(repo, config=False)
    return [("run", "open", "council-review"), ("run", "open", "test-architect"), TE, ("run", "open", "council-init"),
            TE]


def no_home_postgame(repo):
    commit(repo, config=False)
    return [("run", "resume"), ("run", "open", "council-postgame"), ("run", "resume")]


def no_config(repo):
    commit(repo, config=False)
    os.makedirs(os.path.join(repo, ".council"))
    return [("run", "open", "council-plan"), ("run", "resume")]


def capped(repo):
    commit(repo, sharing="- sharing: team\n- agent cap: 4")
    return [("run", "open", "council-review"), ("run", "open", "council-init", "--alongside")]


def memory(repo):
    commit(repo)
    write(os.path.join(repo, ".council", "conventions.md"), "x" * 30000)
    return [("run", "open", "council-review"),
            (("run", "open", "council-plan", "--alongside"), {},
             lambda r: write(os.path.join(r, ".council", "conventions.md"), "x" * 20000)),
            (("run", "open", "council-plan", "--alongside"), {},
             lambda r: write(os.path.join(r, ".council", "conventions.md"), "x" * 25601))]


def memory_configured(repo):
    commit(repo, sharing="- sharing: team\n\n## Memory\n- conventions: docs/mem.md")
    write(os.path.join(repo, "docs", "mem.md"), "y" * 26000)
    write(os.path.join(repo, ".council", "conventions.md"), "x" * 30000)
    return [("run", "open", "council-review")]


def ignores(repo):
    commit(repo)
    write(os.path.join(repo, ".council", "asks", "one.md"), "words\n")
    write(os.path.join(repo, ".council", ".gitignore"), "runs/\r\nactive-run")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "asks")
    return [("run", "open", "council-review")]


def ignores_shared(repo):
    commit(repo)
    write(os.path.join(repo, ".council", ".gitignore"), "!asks/\n")
    return [("run", "open", "council-review")]


def outside_git(repo):
    write(os.path.join(repo, ".council", "council.config.md"), CONFIG % "- sharing: team")
    return [(("run", "open", "council-review"), {}, lambda r: os.rename(os.path.join(r, ".git"), os.path.join(r, "gl"))),
            ("run", "resume"), TE]


def worktree(repo):
    commit(repo)

    def add(r):
        git(r, "worktree", "add", "-q", "wt", "-b", "side")
    return [(("run", "open", "council-review", "--code-root=nope"), {}, add),
            ("run", "open", "council-review", "--code-root=wt"), ("run", "open", "council-plan", "--code-root", "wt"),
            ("run", "resume"), ("run", "open", "council-plan"), ("run", "resume"), TE,
            ("run", "open", "council-research", "--code-root=wt/", "--alongside"),
            (("run", "resume", "--run", "fixed-review"), {}, rename("review")),
            (("run", "resume", "--run", "fixed-research"), {}, rename("research"))]


def rename(short):
    def go(repo):
        runs = os.path.join(repo, ".council", "runs")
        found = [n for n in os.listdir(runs) if n.endswith("-" + short)][0]
        os.rename(os.path.join(runs, found), os.path.join(runs, "fixed-" + short))
    return go


def worktree_gone(repo):
    commit(repo)
    name = run_open(repo, "council-review")
    return [(("run", "resume", "--run", name), {}, setf("code-root", "C:/no/such/tree")),
            (("run", "resume", "--run", name), {}, setf("code-root", "/no/such/tree"))]


def resume(repo):
    commit(repo)
    name = run_open(repo, "council-review")
    seats = SEATS + "fowler\trunning\ta\t\t\tround 2\t\t\nb\tdone\nc\tfailed\n"
    return [("run", "resume"),
            (("run", "resume"), {}, setf("session", "someone-else")),
            (("run", "resume", "--session", "s2"), {}, lambda r: write(os.path.join(run_dir(r), "seats.tsv"), seats)),
            (("run", "resume"), {"CLAUDE_CODE_SESSION_ID": ""}, setf("session", "")),
            (("run", "resume", "--run", name), {},
             edit(lambda d: d.replace(b"## Decisions", b"closed: 2026-01-01 00:00:00\nactual: 3\nwaiting: q\n"
                                      b"## Decisions\nclosed: kept below\nactual: too\n")
                  .replace(b"in-progress", b"paused"))),
            ("run", "events"),
            (("run", "resume"), {}, edit(lambda d: d.replace(b"status: in-progress", b"status: abandoned\nclosed: x"))),
            (("run", "resume", "--run", name), {}, edit(lambda d: d.replace(b"status: abandoned", b"status: complete"))),
            ("run", "resume", "--run", "nosuch")]


def resume_crlf(repo):
    commit(repo)
    run_open(repo, "council-plan")
    return [(("run", "resume"), {}, edit(lambda d: d.replace(b"\n", b"\r\n").replace(b"in-progress", b"paused"))),
            (("run", "resume"), {}, lambda r: os.remove(os.path.join(run_dir(r), "events.tsv"))),
            (("run", "resume"), {}, lambda r: open(os.path.join(run_dir(r), "events.tsv"), "wb").write(
                b"schema\tseq\tat\ttype\tsubject\tvalue\tdetail\n1\t1\t2026-01-01T00:00:00Z\trun.opened\trun\tx\ty\n1\t2"))]


def resume_none(repo):
    commit(repo)
    return [("run", "resume"), ("run", "open", "council-review"), ("run", "open", "council-plan", "--alongside"),
            ("run", "resume")]


def turn_end(repo):
    commit(repo)
    return [("run", "turn-end"), TE, ("run", "open", "council-review"), TE, TE,
            (TE, {}, setf("waiting", "")), ("run", "open", "council-plan", "--alongside"),
            (TE, {}, unwait), TE, ("run", "events"), ("run", "turn-end", "--session=other")]


def unwait(repo):
    runs = os.path.join(repo, ".council", "runs")
    for n in os.listdir(runs):
        setf("waiting", "", n)(repo)


def turn_end_cards(repo):
    commit(repo)
    one = council(OLD, repo, "run", "open", "council-review")[1].strip().replace("\\", "/").rsplit("/", 1)[-1]
    two = council(OLD, repo, "run", "open", "council-plan", "--alongside")[1].strip().replace("\\", "/").rsplit("/", 1)[-1]
    seats = SEATS + "fowler\trunning\ta\t\t\t\t\t\n"

    def due(*names):
        def go(r):
            for n in names:
                write(os.path.join(run_dir(r, n), "card-due"), "due\n")
        return go

    def working(r):
        for n in (one, two):
            write(os.path.join(run_dir(r, n), "seats.tsv"), seats)
    return [(TE, {}, working), (TE, {}, due(one)), TE, (TE, {}, due(one, two)),
            (TE, {}, lambda r: [os.remove(os.path.join(run_dir(r, n), "seats.tsv")) for n in (one, two)]),
            (TE, {}, due(two)), (TE, {}, lambda r: write(os.path.join(run_dir(r, one), "card-due"), "due\r\n")),
            (TE, {}, lambda r: write(os.path.join(run_dir(r, one), "card-due"), "due")),
            (TE, {}, lambda r: (due(one)(r), unwait(r))), (TE, {}, lambda r: (due(one, two)(r), unwait(r))),
            (TE, {}, lambda r: (due(two)(r), setf("waiting", "", one)(r)))]


def turn_end_quiet(repo):
    commit(repo, sharing="- sharing: team\n- notifications: off")
    run_open(repo, "council-review")
    return [TE, TE, (TE, {}, lambda r: write(os.path.join(run_dir(r), "card-due"), "due\n")),
            ("run", "turn-end", "--session", "another"), ("run", "events")]


def turn_end_lost(repo):
    commit(repo)
    run_open(repo, "council-review")
    return [(TE, {}, lambda r: open(os.path.join(run_dir(r), "events.tsv"), "ab").write(b"1\t9\ttorn")), TE]


CASES = [each_mode(m) for m in MODES] + [refusals, second, paused, no_home, no_home_postgame, no_config, capped,
                                         memory, memory_configured, ignores, ignores_shared, outside_git, worktree,
                                         worktree_gone, resume, resume_crlf, resume_none, turn_end, turn_end_cards,
                                         turn_end_quiet, turn_end_lost]
