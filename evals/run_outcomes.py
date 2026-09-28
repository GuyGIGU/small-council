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
