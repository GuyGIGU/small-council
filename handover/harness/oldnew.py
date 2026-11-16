"""Old (SP/main-read, bash) against new (a worktree's bin/council) on the same scratch repos.

python oldnew.py --new <worktree> --cases <cases.py> --out <folder> [case ...]

Each case builds one prototype repo, copied twice (old/, new/); every call runs in both with its own plugin, and
the exit code, stdout, stderr and every file under .council/ are compared after it, each side's repo path, the
clock and pids normalized. Everything it writes is under --out, so several runs at once share nothing."""
import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import time
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

HERE = os.path.dirname(os.path.abspath(__file__))
OLD = os.path.normpath(os.environ.get("OLDNEW_OLD") or os.path.join(HERE, "..", "main-read"))
BASH = shutil.which("bash")
SID = "oldnew-session"
CONFIG = ("# Council config — eval\nlast-verified: 2026-09-15 @ eval\n\n## Roster\n| Seat | Slug | Lens | Surface | Reference "
          "| Recast note |\n|---|---|---|---|---|---|\n| Martin Fowler | fowler | Structure | `src/**` | "
          "references/refactoring.md | kept |\n\n## Gates\n| Gate | Command | Run at | Mandatory | Checked | Needs | Side "
          "effects |\n|---|---|---|---|---|---|---|\n| ok | `true` | grounding, verify | yes | ok | — | none |\n\n"
          "## Run preferences\n%s\n")
ENV = {}
SKIP_FILES = ("events.tsv.lock", "session-state.md.lock", "ledger.tsv.lock", "memory.md.lock")


def setup(out):
    """The environment every call runs in: a fixed git identity and clock, and session marks under out."""
    xdg = os.path.join(out, "xdg")
    ENV.clear()
    ENV.update(os.environ, GIT_AUTHOR_NAME="e", GIT_AUTHOR_EMAIL="e@x.invalid", GIT_COMMITTER_NAME="e",
               GIT_COMMITTER_EMAIL="e@x.invalid", GIT_AUTHOR_DATE="2026-01-01T00:00:00Z",
               GIT_COMMITTER_DATE="2026-01-01T00:00:00Z", XDG_CACHE_HOME=xdg, CLAUDE_CODE_SESSION_ID=SID,
               TMPDIR=os.path.join(out, "tmp"))
    for var in ("COUNCIL_RUN", "COUNCIL_ALLOW_NO_HOOKS", "COUNCIL_PLUGIN_ROOT", "CLOSING", "EVENTS_LOST", "QUIET"):
        ENV.pop(var, None)
    os.makedirs(os.path.join(xdg, "small-council", "sessions"), exist_ok=True)
    os.makedirs(ENV["TMPDIR"], exist_ok=True)
    open(os.path.join(xdg, "small-council", "sessions", SID), "w").close()


def git(cwd, *args):
    return subprocess.run(["git", "-c", "core.autocrlf=false", *args], cwd=cwd, check=True, capture_output=True,
                          env=ENV).stdout.decode("utf-8", "replace").strip()


def write(path, text, binary=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(text if binary else text.encode("utf-8"))


def council(plugin, cwd, *args, env=None):
    p = subprocess.run([BASH, os.path.join(plugin, "bin", "council"), *args], cwd=cwd, capture_output=True,
                       env=dict(ENV, **(env or {})), timeout=300)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def run_open(repo, mode, sharing="- sharing: team"):
    """Write a config and open a run with the OLD plugin; the run's folder name."""
    write(os.path.join(repo, ".council", "council.config.md"), CONFIG % sharing)
    code, out, err = council(OLD, repo, "run", "open", mode)
    if code != 0:
        raise SystemExit("run open failed: " + out + err)
    return out.strip().splitlines()[0].replace("\\", "/").rsplit("/", 1)[-1]


def run_dir(repo, name=None):
    """A run folder of repo: the named one, else the only one."""
    runs = os.path.join(repo, ".council", "runs")
    return os.path.join(runs, name or sorted(os.listdir(runs))[-1])


def forms(path):
    p = path.replace("\\", "/")
    out = {path, p}
    if re.match(r"[A-Za-z]:/", p):
        out.add("/" + p[0].lower() + p[2:])
        out.add(p[0].lower() + p[1:])
    return sorted(out, key=len, reverse=True)


def norm(text, repo):
    for f in forms(repo):
        text = text.replace(f, "<R>")
    text = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", "<T>", text)
    text = re.sub(r"\d{8}T\d{6}Z", "<T>", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?", "<T>", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}-\d{6}", "<RUN>", text)
    text = re.sub(r"\b\d{2}:\d{2}:\d{2}\b", "<T>", text)        # a bare clock (audit.md: "closed complete at 12:06:22")
    text = re.sub(r"\b1\d{9}\b", "<EPOCH>", text)
    text = re.sub(r"pid=\d+|\bpid \d+|process \d+|<T>-\d+|\.tmp\d+", "pid", text)
    return re.sub(r"age \d+ s", "age N s", text)


def snapshot(repo):
    found = {}
    for base, dirs, files in os.walk(os.path.join(repo, ".council")):
        for name in files:
            if name not in SKIP_FILES:
                full = os.path.join(base, name)
                with open(full, "rb") as fh:
                    found[norm(os.path.relpath(full, repo).replace("\\", "/"), repo)] = norm(
                        fh.read().decode("utf-8", "replace"), repo)
    return found


def crlf_only(o, n, sides):
    """The accepted divergence: a scripts/ entry run as its own process on Windows printed CR LF, in-process LF."""
    def fix(text, repo):
        for form in forms(repo):
            text = text.replace(form.replace("\\", "\\\\").replace("/", "\\\\"), "<R>")
        return text
    oo = (o[0], fix(o[1].replace("\r\n", "\n"), sides["old"]), fix(o[2].replace("\r\n", "\n"), sides["old"]), o[3])
    return oo == (n[0], fix(n[1], sides["new"]), fix(n[2], sides["new"]), n[3])


def pair(name, build, new, work, counts, diffs, calls_log):
    """build(repo) -> calls; each call is args, or (args, env), or (args, env, before) with before(repo) run first."""
    counts["cases"] += 1
    proto = os.path.join(work, name, "proto")
    if os.path.exists(os.path.join(work, name)):
        shutil.rmtree(os.path.join(work, name), onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))   # git's read-only files
    os.makedirs(proto)
    git(proto, "init", "-q")
    git(proto, "symbolic-ref", "HEAD", "refs/heads/main")
    calls = build(proto)
    sides = {}
    for side in ("old", "new"):
        repo = sides[side] = os.path.join(work, name, side)
        shutil.copytree(proto, repo, symlinks=True)
        top = git(repo, "rev-parse", "--show-toplevel")
        runs = os.path.join(repo, ".council", "runs")
        for run in os.listdir(runs) if os.path.isdir(runs) else []:
            f = os.path.join(runs, run, "session-state.md")
            if os.path.isfile(f):
                data = open(f, "rb").read()
                data = re.sub(rb"^code-root: [^\r\n]*", b"code-root: " + top.encode(), data, flags=re.M)
                open(f, "wb").write(data)
    for call in calls:
        args, env, before = (tuple(call) + ({}, None))[:3] if isinstance(call[0], tuple) else (call, {}, None)
        got = {}
        for side in ("old", "new"):
            repo = sides[side]
            if before:
                before(repo)
            code, out, err = council(OLD if side == "old" else new, repo, *args, env=env)
            got[side] = (code, norm(out, repo), norm(err, repo), snapshot(repo))
        counts["calls"] += 1
        o, n = got["old"], got["new"]
        calls_log.append("== %s :: council %r\nexit %s\n--- stdout\n%s--- stderr\n%s" % (name, args, *o[:3]))
        if o == n:
            counts["same"] += 1
        elif crlf_only(o, n, sides):
            counts["crlf-only"] += 1
        else:
            counts["diff"] += 1
            what = ["%s:\n  old=%r\n  new=%r" % (label, o[i], n[i])
                    for i, label in enumerate(("exit", "stdout", "stderr")) if o[i] != n[i]]
            what += ["file %s:\n  old=%r\n  new=%r" % (f, o[3].get(f), n[3].get(f))
                     for f in sorted(set(o[3]) | set(n[3])) if o[3].get(f) != n[3].get(f)]
            diffs.append("== %s :: council %s\n%s" % (name, " ".join(args), "\n".join(what)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--new", required=True, help="the worktree whose bin/council is the new side")
    parser.add_argument("--cases", required=True, help="a .py file with CASES = [build, ...]")
    parser.add_argument("--out", required=True, help="your own scratch folder for repos, marks and the diffs")
    parser.add_argument("only", nargs="*")
    a = parser.parse_args()
    out = os.path.abspath(a.out)
    setup(out)
    sys.modules["oldnew"] = sys.modules[__name__]       # a cases file's `import oldnew` gets this ENV
    spec = importlib.util.spec_from_file_location("cases", a.cases)
    cases = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cases)
    counts = {"cases": 0, "calls": 0, "same": 0, "crlf-only": 0, "diff": 0}
    diffs, calls_log = [], []
    started = time.time()
    for build in cases.CASES:
        if not a.only or build.__name__ in a.only:
            pair(build.__name__, build, a.new, os.path.join(out, "repos"), counts, diffs, calls_log)
    with open(os.path.join(out, "diffs.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(diffs))
    with open(os.path.join(out, "calls.txt"), "w", encoding="utf-8") as fh:   # each call as the old side answered
        fh.write("\n".join(calls_log))
    print("cases=%(cases)d calls=%(calls)d same=%(same)d crlf-only=%(crlf-only)d diff=%(diff)d" % counts,
          "in %.0fs; diffs: %s" % (time.time() - started, os.path.join(out, "diffs.txt")))
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
