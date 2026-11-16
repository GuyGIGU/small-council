"""Old hooks (SP/main-read/hooks) against new (the worktree's hooks) on the same repos, stdin, HOME and XDG.

python hookcmp.py --new <worktree> --out <folder> [case ...]

Each case builds a prototype (repo + home), copied to old/ and new/; every call runs the named hook on both
sides with the same stdin JSON and compares exit code, stdout, stderr and every file under the repo's .council,
HOME and XDG_CACHE_HOME (names, bytes and whether each mark file was touched by the call)."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OLD = os.path.normpath(os.environ.get("OLDNEW_OLD") or os.path.join(HERE, "..", "..", "main-read"))
BASH = shutil.which("bash")
SID = "sess-1"
BASE = dict(os.environ, GIT_AUTHOR_NAME="e", GIT_AUTHOR_EMAIL="e@x.invalid", GIT_COMMITTER_NAME="e",
            GIT_COMMITTER_EMAIL="e@x.invalid", GIT_AUTHOR_DATE="2026-01-01T00:00:00Z",
            GIT_COMMITTER_DATE="2026-01-01T00:00:00Z")
for var in ("COUNCIL_RUN", "CLAUDE_CODE_SESSION_ID", "CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT", "XDG_CACHE_HOME"):
    BASE.pop(var, None)


def git(cwd, *args):
    return subprocess.run(["git", "-c", "core.autocrlf=false", *args], cwd=cwd, check=True, capture_output=True,
                          env=BASE).stdout.decode().strip()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(text if isinstance(text, bytes) else text.encode("utf-8"))


def age(path, seconds):
    t = time.time() - seconds
    os.utime(path, (t, t))


def state(status, phase="work", session=None, code_root="{TOP}", mode="council-review", extra=""):
    lines = ["status: " + status, "mode: " + mode, "phase: " + phase, "updated: 2026-09-15 10:00"]
    if code_root is not None:
        lines.append("code-root: " + code_root)
    if session is not None:
        lines.append("session: " + session)
    return "\n".join(lines) + "\n" + extra + "next: x\n\n## Decisions so far\n"


def run(repo, name, text, seats=None):
    folder = os.path.join(repo, ".council", "runs", name)
    write(os.path.join(folder, "session-state.md"), text)
    if seats:
        write(os.path.join(folder, "seats.tsv"), "slug\tstate\tagent\ttokens\tupdated\tnote\n" + seats)
    return folder


def start(source="startup", sid=SID, cwd=None, raw=None):
    if raw is not None:
        return raw
    fields = {"session_id": sid, "transcript_path": "/x/t.jsonl", "hook_event_name": "SessionStart", "source": source}
    if cwd is not None:
        fields["cwd"] = cwd
    return json.dumps(fields)


def stop(agent="small-council:council-worker", sid=SID, message="Wrote /x/none.md — 1 items (1 high)."):
    return json.dumps({"session_id": sid, "hook_event_name": "SubagentStop", "agent_type": agent, "agent_id": "a1",
                       "last_assistant_message": message, "stop_hook_active": False, "cwd": ""},
                      separators=(",", ":"))


def bash_call(command, sid=SID):
    return json.dumps({"session_id": sid, "cwd": "", "hook_event_name": "PreToolUse", "tool_name": "Bash",
                       "tool_input": {"command": command}}, separators=(",", ":"))


# ---------------------------------------------------------------- cases: build(proto) -> [call]
# A call: (hook, stdin, {env}, before(side_root)) — env values may hold {REPO}, {HOME}, {PLUGIN}, {SIDE}.

def no_council(p):
    return [("session-start", start()), ("session-start", start("compact")), ("session-start", start(sid=""))]


def bare_home(p):
    os.makedirs(os.path.join(p, "repo", ".council"))
    return [("session-start", start())]


def CONFIG(extra=""):
    return "# Council config\n\n## Run preferences\n" + extra


def fresh(p):
    repo = os.path.join(p, "repo")
    write(os.path.join(repo, ".council", "council.config.md"), CONFIG())
    return [("session-start", start()), ("session-start", start()),       # the second: marks there already
            ("session-start", start(sid="bad/id")), ("session-start", start(sid="")),
            ("session-start", start(sid=".hidden")),
            ("session-start", start(), {"CLAUDE_PLUGIN_ROOT": None}),     # ROOT from the script's folder
            ("session-start", start(), {"XDG_CACHE_HOME": "{HOME}/.cache"}),
            ("session-start", start(), {"XDG_CACHE_HOME": None}),
            ("session-start", start(), {"CLAUDE_PROJECT_DIR": None}),
            ("session-start", start(), {"CLAUDE_PROJECT_DIR": "{SIDE}/nowhere"}),
            ("session-start", start(raw='{"session_id" : "spaced", "source" : "clear"}')),
            ("session-start", start(raw='not json at all')),
            ("session-start", start(raw='{"session_id":"a","x":{"session_id":"b"}}\n{"session_id":"c"}\n\n'))]


def memory(p):
    repo = os.path.join(p, "repo")
    write(os.path.join(repo, ".council", "council.config.md"), CONFIG())
    write(os.path.join(repo, ".council", "conventions.md"),
          "# Conventions\n## Proposed\n<!-- Format: - PROPOSED accepted pattern: ... -->\n"
          "- PROPOSED accepted pattern: a — x (from r1, d)\r\n- PROPOSED enforced convention: b — y\n"
          "### AP-7: proposed entry under the heading\n**Scope:** src\n\n## Proposals (from run 2)\n"
          "- **D-3 — another one.** text\n## Accepted Patterns\n### AP-1: kept\n**Scope:** all\n")
    write(os.path.join(repo, "conventions.md"), "# Root\n## Accepted Patterns\n### AP-9: other\n**Scope:** all\n")
    calls = [("session-start", start())]

    def configured(side):
        write(os.path.join(side, "repo", ".council", "council.config.md"),
              CONFIG() + "\n## Memory\n- conventions: docs/missing.md (the team's)\n")
    calls.append(("session-start", start(), {}, configured))

    def other(side):
        write(os.path.join(side, "repo", ".council", "council.config.md"),
              CONFIG() + "\n## Memory\n- conventions: conventions.md\n")
    calls.append(("session-start", start(), {}, other))
    return calls


def maps(p):
    repo = os.path.join(p, "repo")
    write(os.path.join(repo, "a.txt"), "a\n")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "one")
    first = git(repo, "rev-parse", "HEAD")
    write(os.path.join(repo, "a.txt"), "b\n")
    git(repo, "commit", "-q", "-am", "two")
    head = git(repo, "rev-parse", "HEAD")
    write(os.path.join(repo, ".council", "council.config.md"), CONFIG("- sharing: just me\n"))
    write(os.path.join(repo, ".council", "map.md"), "# Map\nmap-commit: %s\n" % head)
    calls = [("session-start", start())]
    for text in ("# Map\r\nmap-commit:   %s  # old\r\n" % first, "# Map\nmap-commit: deadbeefdeadbeef\n",
                 "# Map\nno commit line\n", "", "map-commit: %sabcdef\n" % head[:7]):
        calls.append(("session-start", start(), {}, lambda side, t=text: write(
            os.path.join(side, "repo", ".council", "map.md"), t)))
    return calls


def sharing_and_config(p):
    repo = os.path.join(p, "repo")
    write(os.path.join(repo, ".council", "council.config.md"),
          CONFIG("- sharing: Just-Me  # mine\n- notifications: off\n"))
    run(repo, "2026-09-15-100000-review", state("in-progress"))
    calls = [("session-start", start())]
    broken = [b"\xff\xfe# not utf-8 \x80\r\n## Run preferences\r\n- sharing: private\r\n",
              b"- sharing: team\n- sharing: just me\n", b""]
    for data in broken:
        calls.append(("session-start", start(), {}, lambda side, d=data: write(
            os.path.join(side, "repo", ".council", "council.config.md"), d)))

    def folder(side):
        cfg = os.path.join(side, "repo", ".council", "council.config.md")
        os.remove(cfg)
        os.makedirs(cfg)
    calls.append(("session-start", start(), {}, folder))
    return calls


def runs_here(p):
    repo = os.path.join(p, "repo")
    write(os.path.join(repo, ".council", "council.config.md"), CONFIG())
    seats = "hunt\trunning\ta1\t\t10:00\tround 2\nbeck\tdone\ta2\t5\t10:05\t\nx\tfailed\t\t\t\t\nq\tqueued\t\t\t\t\n"
    run(repo, "2026-09-15-100000-review", state("in-progress", session=SID), seats)
    run(repo, "2026-09-15-110000-plan", state("paused", phase="", mode="plan", session="other"))
    run(repo, "2026-09-15-120000-implement", state("in-progress", phase="build", mode="council-implement",
                                                   session="other", extra="waiting: the user's go\n"), seats)
    run(repo, "2026-09-15-130000-review", state("abandoned", phase="judge", extra="closed: 2026-09-15 13:00\n"))
    run(repo, "2026-09-15-140000-postgame", state("in-progress", mode="council-postgame", session=None))
    write(os.path.join(repo, ".council", "runs", "2026-09-15-120000-implement", "card-due"), "due\n")
    write(os.path.join(repo, ".council", "runs", "2026-09-15-100000-review", "card-due"), "reminded\n")

    def old(side, names=("2026-09-15-120000-implement",), seconds=3 * 3600):
        for name in names:
            for top, _, files in os.walk(os.path.join(side, "repo", ".council", "runs", name)):
                for f in files:
                    age(os.path.join(top, f), seconds)
    calls = [("session-start", start(src)) for src in ("startup", "compact", "clear", "resume")]
    calls += [("session-start", start(src), {}, old) for src in ("startup", "clear", "compact")]
    calls += [("session-start", start("compact", sid="sess-9"))]               # not this session's: fallback
    everything = ("2026-09-15-100000-review", "2026-09-15-110000-plan", "2026-09-15-120000-implement",
                  "2026-09-15-140000-postgame")
    calls += [("session-start", start("compact", sid="sess-9"), {}, lambda s: old(s, everything, 13 * 3600))]
    calls += [("session-start", start("compact", sid=""))]
    calls += [("session-start", start("compact"), {}, lambda side: write(os.path.join(
        side, "repo", ".council", "runs", "2026-09-15-140000-postgame", "session-state.md"),
        state("in-progress", mode="council-postgame", session=SID, code_root="-")))]
    return calls


def many_and_elsewhere(p):
    repo = os.path.join(p, "repo")
    write(os.path.join(repo, ".council", "council.config.md"), CONFIG())
    other = os.path.join(p, "elsewhere")
    os.makedirs(other)
    for i in range(12):
        run(repo, "2026-09-1%d-1%02d000-review" % (i % 10, i), state("in-progress" if i % 3 else "paused",
                                                                    session=SID if i == 1 else "s%d" % i))
    for i in range(7):
        run(repo, "2026-08-0%d-000000-plan" % (i + 1), state("in-progress", phase="" if i == 2 else "work",
                                                             code_root="{SIDE}/elsewhere", mode="plan"))
    for i in range(6):
        run(repo, "2026-07-0%d-000000-review" % (i + 1), state("paused", code_root="{SIDE}/gone-%d" % i))
    run(repo, "2026-06-01-000000-review", state("in-progress", code_root="{SIDE}/elsewhere", session=SID))
    calls = [("session-start", start()), ("session-start", start("compact"))]

    def fewer(side):
        runs = os.path.join(side, "repo", ".council", "runs")
        for name in os.listdir(runs):
            if name.startswith(("2026-08-0", "2026-07-0")) and name[9] != "1":
                shutil.rmtree(os.path.join(runs, name))
    calls.append(("session-start", start(), {}, fewer))

    def only_mine(side):
        runs = os.path.join(side, "repo", ".council", "runs")
        for name in os.listdir(runs):
            if name.startswith("2026-09-1") and name != "2026-09-11-101000-review":
                shutil.rmtree(os.path.join(runs, name))
    calls.append(("session-start", start("compact"), {}, only_mine))
    return calls


def worktree(p):
    repo = os.path.join(p, "repo")
    write(os.path.join(repo, "a.txt"), "a\n")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "one")
    write(os.path.join(repo, ".council", "council.config.md"), CONFIG())
    run(repo, "2026-09-15-100000-review", state("in-progress", session=SID))
    return [("session-start", start(cwd="{SIDE}/wt"), {}, lambda side: (git(os.path.join(side, "repo"), "worktree",
             "add", "-q", os.path.join(side, "wt"), "-b", "w") if not os.path.isdir(os.path.join(side, "wt")) else 0)),
            ("session-start", start("compact", cwd="{SIDE}/wt")),
            ("session-start", start(cwd="{SIDE}/repo")),
            ("session-start", start(cwd="{SIDEWIN}\\wt")),
            ("session-start", start(cwd="{SIDE}/wt"), {"CLAUDE_PROJECT_DIR": "{SIDE}/wt"})]


def legacy(p):
    repo = os.path.join(p, "repo")
    write(os.path.join(repo, ".council", "council.config.md"), CONFIG())
    old = os.path.join(repo, ".council", "council-review-output", "r1")
    write(os.path.join(old, "session-state.md"), "status: in-progress\nphase: judge\nupdated: 2026-01-01 10:00\n")
    write(os.path.join(repo, ".council", "active-run"), ".council/council-review-output/r1\r\nsecond line\n")
    calls = [("session-start", start(src)) for src in ("startup", "compact", "clear")]

    def final(side):
        write(os.path.join(side, "repo", ".council", "council-review-output", "r1", "FINAL-review.md"), "x")
        write(os.path.join(side, "repo", ".council", "council-review-output", "r1", "final-lower.md"), "x")
    calls += [("session-start", start(src), {}, final if src == "startup" else None) for src in ("startup", "compact")]

    def mine(side):
        f = os.path.join(side, "repo", ".council", "council-review-output", "r1", "session-state.md")
        write(f, "\ufeffstatus: paused\nmode: council-plan\nsession: %s\n## x\nphase: no\n" % SID)
    calls += [("session-start", start("compact"), {}, mine), ("session-start", start())]
    calls += [("session-start", start(), {}, lambda side: write(os.path.join(side, "repo", ".council", "active-run"),
                                                                "{ABS}/.council/runs/x\n".replace("{ABS}", side)))]
    calls += [("session-start", start(), {}, lambda side: write(
        os.path.join(side, "repo", ".council", "council-review-output", "r1", "session-state.md"),
        "status: complete\n"))]
    return calls


def gates(p):
    repo = os.path.join(p, "repo")
    os.makedirs(repo, exist_ok=True)

    def stale(side):
        for d in (os.path.join(side, "home", ".cache", "small-council", "sessions"),
                  os.path.join(side, "xdg", "small-council", "sessions")):
            write(os.path.join(d, "ancient"), "")
            age(os.path.join(d, "ancient"), 40 * 86400)
    return [("seat-gate", stop()), ("seat-gate", stop()), ("seat-gate", stop(sid="bad id")),
            ("seat-gate", stop(sid="")), ("seat-gate", stop(agent="general-purpose")),
            ("seat-gate", stop(sid="g2"), {"XDG_CACHE_HOME": None}),
            ("seat-gate", stop(sid="g3"), {"XDG_CACHE_HOME": "{HOME}/.cache"}),
            ("bash-gate", bash_call("council run status")), ("bash-gate", bash_call("council doctor", sid="b2")),
            ("bash-gate", bash_call("ls", sid="b3")), ("bash-gate", bash_call("council x", sid="bad id")),
            ("bash-gate", bash_call("council run status | head", sid="b4")),
            ("seat-gate", stop(sid="g4"), {}, stale)]


def odd_bytes(p):
    repo = os.path.join(p, "repo")
    write(os.path.join(repo, ".council", "council.config.md"), CONFIG())
    folder = os.path.join(repo, ".council", "runs", "2026-09-15-100000-review")
    write(os.path.join(folder, "session-state.md"), b"\xef\xbb\xbfstatus: in-progress\r\nmode: review\r\n"
          b"phase: w\xe9rk  # odd\r\nupdated: 2026-09-15 10:00\r\nsession: \xc3\xa9t\xc3\xa9\r\n")
    write(os.path.join(folder, "seats.tsv"), b"slug\tstate\r\nh\xe9\trunning\r\n")
    return [("session-start", start()), ("session-start", start("compact", sid="\u00e9t\u00e9")),
            ("session-start", start(raw='{"session_id":"\u00e9t\u00e9","source":"compact"}')),
            ("session-start", start(raw='{"source":"compact","session_id":"x\\\\"y"}'))]


CASES = [odd_bytes, no_council, bare_home, fresh, memory, maps, sharing_and_config, runs_here, many_and_elsewhere, worktree,
         legacy, gates]


# ---------------------------------------------------------------- the comparison

def forms(path):
    p = path.replace("\\", "/")
    out = {path, p}
    if re.match(r"[A-Za-z]:/", p):
        out.add("/" + p[0].lower() + p[2:])
    temp = os.environ.get("TEMP", "").replace("\\", "/")
    if temp and p.lower().startswith(temp.lower() + "/"):
        out.add("/tmp" + p[len(temp):])                  # Git Bash's /tmp is TEMP
    return sorted(out, key=len, reverse=True)


def norm(text, side, plugin):
    for f in forms(plugin):
        text = text.replace(f, "<PLUGIN>")
    for f in forms(side):
        text = text.replace(f, "<SIDE>")
    return text


def snapshot(side, plugin):
    found = {}
    for top in ("repo/.council", "home", "xdg"):
        for base, _, files in os.walk(os.path.join(side, top)):
            for name in files:
                full = os.path.join(base, name)
                if name.endswith(".lock"):
                    continue
                with open(full, "rb") as fh:
                    found[norm(os.path.relpath(full, side).replace("\\", "/"), side, plugin)] = \
                        (norm(fh.read().decode("utf-8", "replace"), side, plugin), os.path.getmtime(full))
    return found


def fill(value, side):
    return (value.replace("{SIDEWIN}", side.replace("/", "\\")).replace("{SIDE}", side.replace("\\", "/"))
            .replace("{HOME}", os.path.join(side, "home").replace("\\", "/")))


def call_hook(plugin, side, hook, stdin, env):
    e = dict(BASE, HOME=os.path.join(side, "home").replace("\\", "/"), XDG_CACHE_HOME=os.path.join(side, "xdg"),
             CLAUDE_PROJECT_DIR=os.path.join(side, "repo"), CLAUDE_PLUGIN_ROOT=plugin)
    for k, v in env.items():
        if v is None:
            e.pop(k, None)
        else:
            e[k] = fill(v, side)
    p = subprocess.run([BASH, os.path.join(plugin, "hooks", hook + ".sh")], input=fill(stdin, side).encode("utf-8"),
                       capture_output=True, env=e, cwd=os.path.join(side, "repo"), timeout=120)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def pair(build, new, work, counts, diffs, log):
    name = build.__name__
    root = os.path.join(work, name)
    if os.path.exists(root):
        shutil.rmtree(root, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))
    proto = os.path.join(root, "proto")
    os.makedirs(os.path.join(proto, "repo"))
    git(os.path.join(proto, "repo"), "init", "-q")
    git(os.path.join(proto, "repo"), "symbolic-ref", "HEAD", "refs/heads/main")
    calls = build(proto)
    sides = {}
    for side in ("old", "new"):
        s = sides[side] = os.path.join(root, side)
        shutil.copytree(proto, s, symlinks=True)
        for top, _, files in os.walk(os.path.join(s, "repo", ".council")):
            for f in files:
                if f == "session-state.md":
                    full = os.path.join(top, f)
                    st = os.stat(full)
                    data = open(full, "rb").read().replace(b"{TOP}", git(os.path.join(s, "repo"), "rev-parse",
                                                                         "--show-toplevel").encode())
                    data = data.replace(b"{SIDE}", s.replace("\\", "/").encode())
                    open(full, "wb").write(data)
                    os.utime(full, (st.st_atime, st.st_mtime))
    for call in calls:
        hook, stdin, env, before = (tuple(call) + ({}, None))[:4]
        got = {}
        for side in ("old", "new"):
            s = sides[side]
            if before:
                before(s)
            plugin = OLD if side == "old" else new
            snap0 = snapshot(s, plugin)
            code, out, err = call_hook(plugin, s, hook, stdin, env)
            snap = snapshot(s, plugin)
            files = {k: (v[0], "kept" if k in snap0 and snap0[k][1] == v[1] else "touched") for k, v in snap.items()}
            got[side] = (code, norm(out, s, plugin), norm(err, s, plugin), files)
        counts["calls"] += 1
        o, n = got["old"], got["new"]
        log.append("== %s :: %s %s %r\nexit %s\n--- stdout\n%s--- stderr\n%s" % (name, hook, stdin[:80], env, *o[:3]))
        if o == n:
            counts["same"] += 1
        else:
            counts["diff"] += 1
            what = ["%s:\n  old=%r\n  new=%r" % (label, o[i], n[i])
                    for i, label in enumerate(("exit", "stdout", "stderr")) if o[i] != n[i]]
            what += ["file %s:\n  old=%r\n  new=%r" % (f, o[3].get(f), n[3].get(f))
                     for f in sorted(set(o[3]) | set(n[3])) if o[3].get(f) != n[3].get(f)]
            diffs.append("== %s :: %s %s %r\n%s" % (name, hook, stdin[:120], env, "\n".join(what)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("only", nargs="*")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    counts = {"cases": 0, "calls": 0, "same": 0, "diff": 0}
    diffs, log = [], []
    started = time.time()
    for build in CASES:
        if not a.only or build.__name__ in a.only:
            counts["cases"] += 1
            pair(build, os.path.abspath(a.new), os.path.join(out, "repos"), counts, diffs, log)
    with open(os.path.join(out, "diffs.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(diffs))
    with open(os.path.join(out, "calls.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log))
    print("cases=%(cases)d calls=%(calls)d same=%(same)d diff=%(diff)d" % counts,
          "in %.0fs; diffs: %s" % (time.time() - started, os.path.join(out, "diffs.txt")))
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
