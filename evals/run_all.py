#!/usr/bin/env python3
"""Run every free suite CI runs, several at a time, and say how each one did.

    python evals/run_all.py            # as many at a time as the machine has CPUs
    python evals/run_all.py --jobs 1   # one after another
    python evals/run_all.py --list     # the jobs, without running them

Each suite runs as its own process with the same command CI used to run it on its own, so each keeps
its own temporary folders. The helper evals (run_cli.py) are the long pole, so they run as their
groups (run_cli.py --list), side by side. Suites and groups that time the helper or race its locks
run alone, before the rest start, so a busy machine can't make them fail. Every suite runs even when
another fails; each one's output is printed whole once it finishes, then a summary. Exits 1 if any
suite failed, or if an evals/run_*.py file is missing from the list below.

Python 3.8+, standard library only.
"""
import argparse
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

# (name, command, runs alone) in CI's old step order. "Runs alone": the suite times the helper or a hook
# against a limit, or races its locks, so it runs with nothing else running.
SUITES = [
    ("Validate plugin", ["scripts/quick_validate.py"], False),
    ("Structural evals", ["evals/run_structural.py"], False),
    ("Helper evals", ["evals/run_cli.py"], False),   # split into its groups; see helper_jobs()
    ("Model routing evals", ["evals/run_model_routing.py"], False),
    ("Impact evals", ["evals/run_impact.py"], False),
    ("Context evals", ["evals/run_context.py"], False),
    ("Context delivery pilot (byte accounting, no model calls)", ["evals/run_context_pilot.py"], False),
    ("Evidence model evals", ["evals/run_evidence.py"], False),
    ("Repair loop evals", ["evals/run_repair.py"], False),
    ("Memory evals", ["evals/run_memory.py"], False),
    ("Seat learning evals", ["evals/run_seats.py"], False),
    ("Run cockpit evals", ["evals/run_tui.py"], True),     # a rename race and a watcher's timing
    ("Status and accounting evals", ["evals/run_status.py"], False),
    ("Run history evals", ["evals/run_history.py"], False),
    ("Finding outcomes evals", ["evals/run_outcomes.py"], False),
    ("Tuning evals", ["evals/run_tune.py"], False),
    ("Benchmark harness self-test (no model calls)", ["evals/bench.py", "self-test"], False),
    ("Hook evals", ["evals/run_hook.py"], True),           # hooks timed against their 15 s limit
    ("Phrase checks (advisory, never fails)", ["evals/run_phrases.py"], False),
]


class Job:
    def __init__(self, name, args, alone):
        self.name, self.args, self.alone = name, args, alone
        self.code, self.seconds, self.output = None, 0.0, b""

    @property
    def command(self):
        return "python " + " ".join(self.args)

    def checks(self):
        found = re.findall(rb"^(\d+)/(\d+) checks passed", self.output, re.MULTILINE)
        return (int(found[-1][0]), int(found[-1][1])) if found else None


def helper_jobs(name, args):
    """One job per run_cli.py group. If the groups can't be listed, the whole suite as one job."""
    listing = subprocess.run([PY, *args, "--list"], cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
    groups = [line.split("\t") for line in listing.stdout.splitlines() if line.count("\t") == 2]
    if listing.returncode != 0 or not groups:
        return [Job(name, args, False)], "%s --list failed (exit %s): %s" % (
            " ".join(args), listing.returncode, (listing.stdout + listing.stderr).strip()[:400])
    return [Job("%s: %s" % (name, group), [*args, "--group", group], how == "alone")
            for group, how, _ in groups], None


def unlisted():
    """evals/run_*.py files that no entry runs: a suite added without adding it here would never run."""
    listed = {Path(args[0]).as_posix() for _, args, _ in SUITES}
    return sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "evals").glob("run_*.py")
                  if p.relative_to(ROOT).as_posix() not in listed and p.name != "run_all.py")


def run(job, say):
    say(None, "[start] %s" % job.name)
    started = time.monotonic()
    proc = subprocess.run([PY, *job.args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    job.code, job.output, job.seconds = proc.returncode, proc.stdout, time.monotonic() - started
    say(job)


def main():
    parser = argparse.ArgumentParser(description="Run every free suite CI runs, several at a time.")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 2,
                        help="how many suites run at the same time (default: the number of CPUs)")
    parser.add_argument("--list", action="store_true", help="print the jobs and their commands; run nothing")
    opts = parser.parse_args()

    jobs, problems = [], []
    for name, args, alone in SUITES:
        if args[0] == "evals/run_cli.py":
            more, problem = helper_jobs(name, args)
            jobs += more
            if problem:
                problems.append(problem)
        else:
            jobs.append(Job(name, args, alone))
    problems += ["%s is not in evals/run_all.py's list, so it would never run" % f for f in unlisted()]
    if opts.list:
        for job in jobs:
            print("%-6s %-60s %s" % ("alone" if job.alone else "shared", job.name, job.command))
        for problem in problems:
            print("PROBLEM: " + problem)
        return 1 if problems else 0

    actions = os.environ.get("GITHUB_ACTIONS") == "true"
    lock = threading.Lock()

    def say(job, line=None):
        with lock:
            if job is None:
                print(line, flush=True)
                return
            verdict = "passed" if job.code == 0 else "FAILED (exit %d)" % job.code
            title = "%s: %s in %.0f s" % (job.name, verdict, job.seconds)
            print(("::group::" if actions else "\n===== ") + title, flush=True)
            sys.stdout.buffer.write(job.output if job.output.endswith(b"\n") or not job.output else job.output + b"\n")
            sys.stdout.buffer.flush()
            print("::endgroup::" if actions else "===== end of " + job.name, flush=True)

    started = time.monotonic()
    width = max(1, opts.jobs)
    print("%d jobs: %d run alone first, then the rest %d at a time" % (
        len(jobs), sum(j.alone for j in jobs), width), flush=True)
    for job in [j for j in jobs if j.alone]:
        run(job, say)
    rest = sorted((j for j in jobs if not j.alone), key=lambda j: -weight(j))   # longest first
    with ThreadPoolExecutor(max_workers=width) as pool:
        for future in [pool.submit(run, job, say) for job in rest]:
            future.result()
    wall = time.monotonic() - started

    print("\nSummary (%s)" % ("one at a time" if width == 1 else "%d at a time" % width))
    print("%-62s %-7s %6s  %s" % ("suite", "result", "time", "checks"))
    for job in jobs:
        counts = job.checks()
        print("%-62s %-7s %5.0fs  %s" % (job.name[:62], "pass" if job.code == 0 else "FAIL", job.seconds,
                                         "%d/%d" % counts if counts else "-"))
    helper = [j.checks() for j in jobs if j.args[0] == "evals/run_cli.py"]
    if helper and all(helper):
        print("%-62s %-7s %6s  %d/%d" % ("Helper evals, all groups", "", "", sum(c[0] for c in helper),
                                          sum(c[1] for c in helper)))
    failed = [j for j in jobs if j.code != 0]
    print("\n%d jobs, %d failed, %.0f s in all (%.0f s of suite time)" % (
        len(jobs), len(failed), wall, sum(j.seconds for j in jobs)))
    if os.environ.get("GITHUB_STEP_SUMMARY"):   # the same table on the run's summary page
        rows = ["| %s | %s | %.0f s | %s |" % (j.name, "pass" if j.code == 0 else "**FAIL**", j.seconds,
                                               "%d/%d" % j.checks() if j.checks() else "-") for j in jobs]
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write("| suite | result | time | checks |\n|---|---|---|---|\n" + "\n".join(rows) +
                      "\n\n%d jobs, %d failed, %.0f s in all\n" % (len(jobs), len(failed), wall))
    for job in failed:
        print(("::error title=%s failed::" % job.name if actions else "FAILED: ") + "rerun it with: " + job.command)
    for problem in problems:
        print(("::error::" if actions else "PROBLEM: ") + problem)
    return 1 if failed or problems else 0


# Rough seconds each job took on CI's Windows leg, so the longest start first. A job missing here
# still runs; it just starts after the ones listed.
WEIGHTS = {"Helper evals: runs": 345, "Helper evals: requests": 313, "Status and accounting evals": 196,
           "Helper evals: collect": 191, "Helper evals: filing": 155, "Helper evals: gates": 137,
           "Helper evals: citations": 115, "Memory evals": 105, "Tuning evals": 75}


def weight(job):
    return WEIGHTS.get(job.name, 10)


if __name__ == "__main__":
    sys.exit(main())
