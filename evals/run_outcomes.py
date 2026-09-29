#!/usr/bin/env python3
"""No-model checks for conservative, read-only finding outcome history."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
GIT = shutil.which("git")
BASH = os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash") or (
    r"C:\Program Files\Git\bin\bash.exe" if Path(r"C:\Program Files\Git\bin\bash.exe").is_file() else None)
sys.path.insert(0, str(ROOT / "scripts"))
import outcomes  # noqa: E402
import history  # noqa: E402
import tune  # noqa: E402

checks = []


def check(name, good, detail=""):
    checks.append((name, good, detail))


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def run_git(repo, *args, env=None):
    result = subprocess.run([GIT, "-C", str(repo)] + list(args), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True, env=env, check=True)
    return result.stdout.strip()


def fingerprint(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def council(repo, *args):
    env = os.environ.copy()
    for var in ("COUNCIL_RUN", "CLAUDE_CODE_SESSION_ID"):
        env.pop(var, None)
    if os.environ.get("COUNCIL_EVAL_BASH"):
        env["PATH"] = str(Path(BASH).parent) + os.pathsep + env.get("PATH", "")
    words = [BASH, str(ROOT / "bin" / "council"), *args]
    if os.name == "nt":
        words = " ".join('"{}"'.format(word.replace('"', '\\"')) for word in words)
    result = subprocess.run(words, cwd=repo, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", env=env, timeout=60)
    return result.returncode, result.stdout, result.stderr


with tempfile.TemporaryDirectory(prefix="council-outcomes-") as temporary:
    temp = Path(temporary)
    repo = temp / "repo"
    home = repo / ".council"
    repo.mkdir()
    if GIT:
        run_git(repo, "init", "-q")
        run_git(repo, "config", "user.name", "Council eval")
        run_git(repo, "config", "user.email", "eval@example.invalid")
        files = {
            "src/changed.py": "first\ntarget\nthird\n",
            "src/elsewhere.py": "target\nsecond\nthird\n",
            "src/stable.py": "target\nsecond\n",
            "src/old.py": "target\nsecond\n",
        }
        for name, text in files.items():
            write(repo / name, text)
        run_git(repo, "add", ".")
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = "2020-01-01T10:00:00+00:00"
        env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"]
        run_git(repo, "commit", "-q", "-m", "baseline", env=env)
        base = run_git(repo, "rev-parse", "HEAD")
        write(repo / "src/between.py", "committed before close\n")
        run_git(repo, "add", ".")
        env["GIT_AUTHOR_DATE"] = "2020-01-02T11:00:00+00:00"
        env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"]
        run_git(repo, "commit", "-q", "-m", "before close", env=env)

        home.mkdir()
        write(home / "council.config.md", "# Council config\n")
        run = home / "runs" / "2020-01-02-120000-review"
        write(run / "session-state.md", "status: complete\nmode: council-review\nopened: 2020-01-02 10:00:00\n"
              "closed: 2020-01-02 12:00:00\nbase: {}\n".format(base))
        claims = [
            {"id": "1", "disposition": "kept", "citation": "src/changed.py:2", "provenance": ["hunt#1"]},
            {"id": "2", "disposition": "kept", "citation": "src/elsewhere.py:1", "provenance": ["hunt#2"]},
            {"id": "3", "disposition": "kept", "citation": "src/stable.py:1", "provenance": ["verify#1"]},
            {"id": "4", "disposition": "kept", "citation": "src/old.py:1", "provenance": ["chair"]},
            {"id": "5", "disposition": "kept", "citation": "-", "provenance": ["chair"]},
            {"id": "6", "disposition": "cut", "citation": "src/cut.py:1", "provenance": ["hunt#3"]},
            {"id": "7", "disposition": "cut", "citation": "src/changed.py:2", "provenance": ["hunt#4"]},
        ]
        write(run / "claims.jsonl", "".join(json.dumps(item) + "\n" for item in claims))

        write(repo / "src/changed.py", "first\nfixed\nthird\n")
        write(repo / "src/elsewhere.py", "target\nsecond\nthird changed\n")
        (repo / "src/old.py").replace(repo / "src/new.py")
        write(repo / "src/cut.py", "cut\n")
        run_git(repo, "add", "-A")
        env["GIT_AUTHOR_DATE"] = "2020-01-03T10:00:00+00:00"
        env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"]
        run_git(repo, "commit", "-q", "-m", "after close", env=env)

        before = fingerprint(temp)
        data = outcomes.outcomes(home, repo)
        after = fingerprint(temp)
        got = {claim["id"]: claim["outcome"] for claim in data["runs"][0]["claims"]}
        check("all five outcome classes are conservative and recognized", got == {
            "1": "changed at cited lines", "2": "file changed elsewhere", "3": "unchanged",
            "4": "file gone or renamed", "5": "can't tell", "6": "can't tell",
            "7": "changed at cited lines"}, got)
        check("Kept and Cut remain separate comparison groups", data["totals"]["kept"]["changed at cited lines"] == 1
              and data["totals"]["cut"]["changed at cited lines"] == 1, data["totals"])
        check("mode and originating seat breakdowns are present", "council-review" in data["by_mode"]
              and data["by_seat"]["hunt"]["kept"]["changed at cited lines"] == 1, data["by_seat"])
        check("each run summary keeps Kept and Cut as separate groups",
              data["runs"][0]["summary"]["kept"]["changed at cited lines"] == 1
              and data["runs"][0]["summary"]["cut"]["changed at cited lines"] == 1,
              data["runs"][0]["summary"])
        check("close commit comparison writes nothing", before == after)
        check("wording warns that time order does not establish cause", "does not show" in outcomes.render(data))
        mismatched_base_run = home / "runs" / "2020-01-02-123000-review"
        write(mismatched_base_run / "session-state.md", "status: complete\nmode: council-review\n"
              "closed: 2020-01-02 12:30:00\nbase: {}\n".format("0" * 40))
        write(mismatched_base_run / "claims.jsonl", json.dumps({"id": "8", "disposition": "kept",
              "citation": "src/stable.py:1", "provenance": ["hunt#5"]}) + "\n")
        uncertain = outcomes.outcomes(home, repo)
        row = next(r for r in uncertain["runs"] if r["run"] == mismatched_base_run.name)
        check("the diff base need not equal the commit at close", row["claims"][0]["outcome"] == "unchanged", row)

        bad_run = home / "runs" / "2020-01-04-120000-review"
        write(bad_run / "session-state.md", "status: complete\nmode: council-review\u001b[31m\n"
              "closed: 2020-01-04 12:00:00\nbase: {}\n".format("0" * 40))
        write(bad_run / "claims.jsonl", json.dumps(claims[0]) + "\n")
        write(bad_run / "index.md", "# Change index — review\nbase: abc · head: def + uncommitted changes\n")
        uncertain = outcomes.outcomes(home, repo)
        row = next(r for r in uncertain["runs"] if r["run"] == bad_run.name)
        check("dirty index means can't tell", row["claims"][0]["outcome"] == "can't tell", row)
        check("dirty index is can't tell and labels are sanitized",
              row["mode"] == "council-review [31m" and "\u001b" not in outcomes.render(uncertain),
              (row["mode"], outcomes.render(uncertain)))
        other = temp / "other-repo"
        other.mkdir()
        run_git(other, "init", "-q")
        run_git(other, "config", "user.name", "Council eval")
        run_git(other, "config", "user.email", "eval@example.invalid")
        write(other / "src/stable.py", "target\n")
        run_git(other, "add", ".")
        env["GIT_AUTHOR_DATE"] = "2020-01-02T11:00:00+00:00"
        env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"]
        run_git(other, "commit", "-q", "-m", "other before close", env=env)
        write(other / "src/stable.py", "changed\n")
        run_git(other, "add", ".")
        env["GIT_AUTHOR_DATE"] = "2020-01-03T11:00:00+00:00"
        env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"]
        run_git(other, "commit", "-q", "-m", "other after close", env=env)
        other_run = home / "runs" / "2020-01-02-130000-other"
        write(other_run / "session-state.md", "status: complete\nmode: council-review\n"
              "closed: 2020-01-02 13:00:00\ncode-root: {}\n".format(other))
        write(other_run / "claims.jsonl", json.dumps({"id": "other", "disposition": "kept",
              "citation": "src/stable.py:1", "provenance": ["hunt#6"]}) + "\n")
        other_data = outcomes.outcomes(home, repo)
        row = next(r for r in other_data["runs"] if r["run"] == other_run.name)
        check("each run compares against its recorded code root, not the caller's unchanged file",
              row["claims"][0]["outcome"] == "changed at cited lines", row)
        absent_run = home / "runs" / "2020-01-02-140000-missing"
        write(absent_run / "session-state.md", "status: complete\nmode: council-review\n"
              "closed: 2020-01-02 14:00:00\ncode-root: {}\n".format(temp / "missing-repo"))
        write(absent_run / "claims.jsonl", json.dumps({"id": "missing", "disposition": "kept",
              "citation": "src/changed.py:2", "provenance": ["hunt#7"]}) + "\n")
        absent_data = outcomes.outcomes(home, repo)
        row = next(r for r in absent_data["runs"] if r["run"] == absent_run.name)
        check("an unavailable recorded code root is can't tell, not a comparison with the caller",
              row["claims"][0]["outcome"] == "can't tell", row)

        # Line endings, colour settings and pure insertions, in a second fixture repository that its
        # run records as its code root (so history, run from any folder, compares with it too).
        edge = temp / "edge-repo"
        edge_home = edge / ".council"
        edge.mkdir()
        run_git(edge, "init", "-q")
        run_git(edge, "config", "user.name", "Council eval")
        run_git(edge, "config", "user.email", "eval@example.invalid")
        run_git(edge, "config", "core.autocrlf", "false")   # commit the CRLF bytes exactly as written
        eight = "".join("line {}\n".format(n) for n in range(1, 9)).encode("ascii")
        crlf = eight.replace(b"\n", b"\r\n")
        changes = {
            "crlf/only.py": crlf,                                                    # line endings only
            "crlf/at.py": crlf.replace(b"line 2\r", b"fixed 2\r"),                   # ... and an edit at line 2
            "crlf/elsewhere.py": crlf.replace(b"line 6\r", b"fixed 6\r"),            # ... and an edit at line 6
            "insert/inside.py": eight.replace(b"line 5\n", b"line 5\nguard\n"),      # after line 5 of 4-6
            "insert/after.py": eight.replace(b"line 2\n", b"line 2\nguard\n"),       # right after line 2
            "insert/before.py": eight.replace(b"line 3\n", b"line 3\nguard\n"),      # right before line 4
            "insert/away.py": eight.replace(b"line 4\n", b"line 4\nguard\n"),        # two lines past line 2
            "fix/target.py": eight.replace(b"line 2\n", b"fixed 2\n"),
            "text/bytes.py": eight.replace(b"line 2\n", "café Á ".encode("utf-8") + b"\xff\n"),
        }
        for name in changes:
            (edge / name).parent.mkdir(parents=True, exist_ok=True)
            (edge / name).write_bytes(eight)
        run_git(edge, "add", "--", *changes)
        env["GIT_AUTHOR_DATE"] = "2020-01-01T10:00:00+00:00"
        env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"]
        run_git(edge, "commit", "-q", "-m", "edge baseline", env=env)
        write(edge_home / "council.config.md", "# Council config\n")
        edge_run = edge_home / "runs" / "2020-01-02-120000-review"
        write(edge_run / "session-state.md", "status: complete\nmode: council-review\n"
              "closed: 2020-01-02 12:00:00\ncode-root: {}\n".format(edge))
        edge_claims = {"crlf-only": "crlf/only.py:2", "crlf-at": "crlf/at.py:2", "crlf-elsewhere": "crlf/elsewhere.py:2",
                       "insert-inside": "insert/inside.py:4-6", "insert-after": "insert/after.py:2",
                       "insert-before": "insert/before.py:4", "insert-away": "insert/away.py:2",
                       "fix-at": "fix/target.py:2", "fix-elsewhere": "fix/target.py:6", "fix-span": "fix/target.py:1-3",
                       "bytes": "text/bytes.py:2"}
        write(edge_run / "claims.jsonl", "".join(json.dumps({"id": ident, "disposition": "kept", "citation": cited,
                                                             "provenance": ["hunt#1"]}) + "\n"
                                                 for ident, cited in edge_claims.items()))
        for name, text in changes.items():
            (edge / name).write_bytes(text)
        run_git(edge, "add", "--", *changes)
        env["GIT_AUTHOR_DATE"] = "2020-01-03T10:00:00+00:00"
        env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"]
        run_git(edge, "commit", "-q", "-m", "edge after close", env=env)

        git_calls = []
        real_git = outcomes.git

        def counting_git(where, *args):
            git_calls.append(args)
            return real_git(where, *args)

        outcomes.git = counting_git
        try:
            plain = outcomes.outcomes(edge_home, edge)
        finally:
            outcomes.git = real_git
        edge_got = {claim["id"]: claim["outcome"] for claim in plain["runs"][0]["claims"]}
        for name, ident, want in (
                ("a file whose only change is LF to CRLF is unchanged", "crlf-only", "unchanged"),
                ("a CRLF rewrite with a real edit at the cited line is changed at cited lines", "crlf-at",
                 "changed at cited lines"),
                ("a CRLF rewrite with a real edit elsewhere is file changed elsewhere", "crlf-elsewhere",
                 "file changed elsewhere"),
                ("lines inserted strictly inside a cited span are changed at cited lines", "insert-inside",
                 "changed at cited lines"),
                ("lines inserted right after a one-line citation are changed at cited lines", "insert-after",
                 "changed at cited lines"),
                ("lines inserted right before a citation are changed at cited lines", "insert-before",
                 "changed at cited lines"),
                ("lines inserted two lines past a citation are file changed elsewhere", "insert-away",
                 "file changed elsewhere"),
                ("a diff holding bytes the locale cannot decode is still compared", "bytes",
                 "changed at cited lines")):
            check(name, edge_got.get(ident) == want, (ident, edge_got.get(ident)))
        diffs = [args for args in git_calls if args[0] == "diff" and args[-1] == "fix/target.py"]
        looks = [args for args in git_calls if args[0] == "cat-file" and args[-1].endswith(":fix/target.py")]
        check("claims citing one file share one diff and one tracked check at each commit",
              len(diffs) == 1 and len(looks) == 2 and [edge_got.get(i) for i in ("fix-at", "fix-elsewhere", "fix-span")]
              == ["changed at cited lines", "file changed elsewhere", "changed at cited lines"],
              (diffs, looks, edge_got))

        run_git(edge, "config", "color.diff", "always")
        colored = outcomes.outcomes(edge_home, edge)
        colored_got = {claim["id"]: claim["outcome"] for claim in colored["runs"][0]["claims"]}
        check("with color.diff always, a fix at the cited line still reads changed at cited lines, and every "
              "outcome matches the uncoloured comparison",
              colored_got.get("fix-at") == "changed at cited lines" and colored_got == edge_got, colored_got)

        compared = []
        real_outcomes = outcomes.outcomes

        def counting_outcomes(*args, **kwargs):
            compared.append(args)
            return real_outcomes(*args, **kwargs)

        outcomes.outcomes = counting_outcomes
        try:
            full = history.history(edge_home)
            on = len(compared)
            skipped = history.history(edge_home, outcomes=False)
            tune.proposals(edge_home)
            off = len(compared) - on
        finally:
            outcomes.outcomes = real_outcomes
        check("history compares finding outcomes by default; history(outcomes=False) and tune run no comparison",
              on == 1 and off == 0 and skipped["outcomes"] is None
              and full["outcomes"] == {"runs": 1, "kept": plain["totals"]["kept"], "cut": plain["totals"]["cut"]},
              (on, off, full["outcomes"], skipped["outcomes"]))
        if BASH:
            code, out, err = council(repo, "outcomes", "--json")
            try:
                cli_data = json.loads(out)
            except ValueError:
                cli_data = {}
            check("helper: council outcomes --json returns the schema", code == 0
                  and cli_data.get("schema") == "council.outcomes/1", out + err)
            code, out, err = council(repo, "history")
            check("helper: history includes finding outcome summary", code == 0
                  and "Finding outcomes:" in out and "does not prove cause" in out, out + err)
        else:
            print("[SKIP] bash unavailable — CLI integration checks skipped")
    else:
        print("[SKIP] Git unavailable — fixture-repository checks skipped")

passed = sum(good for _, good, _ in checks)
for name, good, detail in checks:
    print("[{}] {}".format("PASS" if good else "FAIL", name) + ("\n        {}".format(str(detail)[:900]) if not good else ""))
print("\n{}/{} checks passed".format(passed, len(checks)))
sys.exit(0 if passed == len(checks) else 1)
