#!/usr/bin/env python3
"""Focused no-model checks for the run-plan model override contract."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BASH = os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash")
if os.name == "nt" and not BASH:
    candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
    BASH = str(candidate) if candidate.is_file() else None
GIT = shutil.which("git")
CLI = str(ROOT / "bin" / "council")
ENV = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}   # never the session the eval runs in


def call(cwd, *args):
    result = subprocess.run([BASH, CLI, *args], cwd=str(cwd), capture_output=True, env=ENV,
                            text=True, encoding="utf-8", errors="replace", timeout=30)
    return result.returncode, result.stdout, result.stderr


def write_plan(run, model_rows=""):
    rows = [
        ("kind", "id", "field", "value", "reason"),
        ("schema", "plan", "version", "1", "test contract"),
        ("run", "run", "id", run.name, "bind to run"),
        ("run", "run", "mode", "council-review", "review"),
        ("run", "run", "size", "squad", "team"),
        ("assessment", "run", "risk", "low", "test"),
        ("assessment", "run", "complexity", "low", "test"),
        ("assessment", "run", "uncertainty", "low", "test"),
        ("budget", "run", "agent-cap", "10", "default"),
        ("budget", "run", "estimated-tokens", "100000", "test estimate"),
        ("verification", "run", "level", "independent", "test"),
    ]
    for slug, role in (("chair", "chair"), ("mapper", "worker"), ("verify-check", "verifier")):
        rows.extend([
            ("seat", slug, "disposition", "selected", "test"),
            ("seat", slug, "role", role, "test"),
            ("context", slug, "level", "focused", "test"),
            ("budget", slug, "tool-calls", "15", "test"),
        ])
    content = "\n".join("\t".join(row) for row in rows) + "\n" + model_rows
    (run / "run-plan.tsv").write_text(content, encoding="utf-8", newline="\n")


def main():
    if not BASH or not GIT:
        print("[SKIP] bash or git unavailable")
        return 0
    checks = []

    def check(name, passed, detail=""):
        checks.append((name, bool(passed), detail))

    with tempfile.TemporaryDirectory(prefix="council-model-routing-") as temporary:
        repo = Path(temporary) / "repo"
        repo.mkdir()
        subprocess.run([GIT, "init", "-q"], cwd=str(repo), check=True)
        home = repo / ".council"
        home.mkdir()
        config = home / "council.config.md"
        config.write_text("# Test council config\n", encoding="utf-8", newline="\n")
        code, out, err = call(repo, "run", "open", "council-review")
        check("run opens for the plan fixture", code == 0, out + err)
        run = Path(out.strip())
        write_plan(run, "seat\tmapper\tpurpose\tsurvey\troutine survey\n"
                   "seat\tmapper\tmodel\thaiku\troutine survey\n")
        code, out, err = call(repo, "run", "plan", "check")
        check("non-inherit choice is refused by default", code == 1 and "seat model overrides are off" in out,
              out + err)
        config.write_text("# Test council config\n- seat models: on\n", encoding="utf-8", newline="\n")
        code, out, err = call(repo, "run", "plan", "check")
        check("enabled worker model choice passes", code == 0, out + err)
        code, out, err = call(repo, "run", "plan", "show")
        check("plan display shows purpose and requested model", code == 0
              and "purpose survey" in out and "model haiku" in out, out + err)
        write_plan(run, "seat\tmapper\tmodel\thaiku\tmissing purpose\n")
        code, out, err = call(repo, "run", "plan", "check")
        check("override without a declared mapping or survey purpose is refused", code == 1
              and "needs seat/mapper/purpose = mapping or survey" in out, out + err)
        write_plan(run, "seat\tmapper\tpurpose\tother\timplementation work\n"
                   "seat\tmapper\tmodel\thaiku\tinvalid override\n")
        code, out, err = call(repo, "run", "plan", "check")
        check("override for declared other work is refused", code == 1
              and "needs seat/mapper/purpose = mapping or survey" in out, out + err)
        for slug, label in (("chair", "Chair"), ("verify-check", "verifier")):
            write_plan(run, "seat\t{}\tmodel\tsonnet\ttest invalid override\n".format(slug))
            code, out, err = call(repo, "run", "plan", "check")
            check("{} cannot use an override".format(label),
                  code == 1 and "only worker seats can use sonnet or haiku" in out, out + err)
        write_plan(run, "seat\tmapper\tmodel\topus\tinvalid alias\n")
        code, out, err = call(repo, "run", "plan", "check")
        check("unsupported model alias is refused", code == 1 and "must be inherit, sonnet or haiku" in out,
              out + err)

        config.write_text("# Test council config\n- seat models: off\n", encoding="utf-8", newline="\n")
        write_plan(run, "seat\tmapper\tpurpose\tsurvey\troutine survey\n"
                   "seat\tmapper\tmodel\thaiku\troutine survey\n")
        code, out, err = call(repo, "run", "plan", "check")
        check("an explicit seat models: off refuses an override", code == 1 and "seat model overrides are off" in out,
              out + err)
        for label, rows in (("no model row", ""), ("only inherit rows", "seat\tmapper\tmodel\tinherit\tdefault\n")):
            write_plan(run, rows)
            code, out, err = call(repo, "run", "plan", "show")
            check("routing unused ({}): plan display says nothing about models".format(label),
                  code == 0 and "seat" in out and "model" not in out, out + err)

        # A finished run is not judged by today's setting: turning seat models back off must not make
        # doctor call a closed run's plan invalid. An open run with the same plan is still flagged.
        routed = "seat\tmapper\tpurpose\tmapping\tcodebase map\nseat\tmapper\tmodel\thaiku\tcodebase map\n"
        config.write_text("# Test council config\n- seat models: on\n", encoding="utf-8", newline="\n")
        write_plan(run, routed)
        code, out, err = call(repo, "state", "phase=deliver")
        closed_ok = code == 0
        code, out, err = call(repo, "run", "close", "--status", "complete")
        check("a routed run reaches Deliver and closes", closed_ok and code == 0, out + err)
        code, out, err = call(repo, "run", "open", "council-review")
        second = Path(out.strip())
        write_plan(second, routed)
        code, out, err = call(repo, "state", "phase=deliver")
        check("a second routed run is open at Deliver", code == 0, out + err)
        config.write_text("# Test council config\n- seat models: off\n", encoding="utf-8", newline="\n")
        code, out, err = call(repo, "doctor")
        check("doctor: a closed run's plan stays valid after seat models go back off",
              "run {} has".format(run.name) not in out + err, out + err)
        check("doctor: an open run's override is still flagged once seat models are off",
              "run {} has an invalid run plan".format(second.name) in out + err, out + err)
        code, out, err = call(repo, "run", "plan", "check", "--run", run.name)
        check("plan check on the closed run still passes", code == 0, out + err)

    for name, passed, detail in checks:
        print("[{}] {}{}".format("PASS" if passed else "FAIL", name,
                                  " — " + detail.strip() if detail.strip() and not passed else ""))
    print("{}/{} checks passed".format(sum(passed for _, passed, _ in checks), len(checks)))
    return 0 if all(passed for _, passed, _ in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
