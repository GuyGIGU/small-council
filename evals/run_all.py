#!/usr/bin/env python3
"""Run every free suite CI runs, several at a time, and say how each one did.

    python evals/run_all.py            # as many at a time as the machine has CPUs
    python evals/run_all.py --jobs 1   # one after another
    python evals/run_all.py --fast     # the fast tier only (FAST below): under two minutes, while you work
    python evals/run_all.py --list     # the jobs, and which are in the fast tier, without running them

Each suite runs as its own process with the same command CI used to run it on its own, so each keeps
its own temporary folders. The helper evals (run_cli.py, the long pole) and the hook evals run as
their groups (--list), side by side. Suites and groups that time the helper or a hook, or race the
helper's locks, run alone, before the rest start, so a busy machine can't make them fail. Every suite
runs even when another fails; each one's output is printed whole once it finishes, then a summary.
Exits 1 if any suite failed, or reported no "N/N checks passed" line or zero checks (a suite that
skipped everything), or if an evals/run_*.py file is missing from the list below.

The fast tier is validation, the structural evals, the ratchet and its self-test, the unit tests in
tests/py/ (skipped, and said so, while that folder doesn't exist) and the quickest scenario suites. It
is a first look, not the gate: the full run is the default, and it is what CI and a commit wait on.

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

# (name, command, how) in CI's old step order. "alone": the suite times the helper or a hook against a
# limit, or races its locks, so it runs with nothing else running. "groups": one job per group the suite
# lists (--list), each run with --group; the suite says which of its groups run alone.
SUITES = [
    ("Validate plugin", ["scripts/quick_validate.py"], "shared"),
    ("Structural evals", ["evals/run_structural.py"], "shared"),
    ("Ratchet (sizes and structure only go down)", ["evals/run_ratchet.py"], "shared"),
    ("Ratchet self-test", ["evals/run_ratchet.py", "--self-test"], "shared"),
    ("Unit tests (tests/py)", ["-m", "unittest", "discover", "-s", "tests/py"], "unit"),   # skipped while absent
    ("Helper evals", ["evals/run_cli.py"], "groups"),
    ("Model routing evals", ["evals/run_model_routing.py"], "shared"),
    ("Impact evals", ["evals/run_impact.py"], "shared"),
    ("Context evals", ["evals/run_context.py"], "shared"),
    ("Context delivery pilot (byte accounting, no model calls)", ["evals/run_context_pilot.py"], "shared"),
    ("Evidence model evals", ["evals/run_evidence.py"], "shared"),
    ("Repair loop evals", ["evals/run_repair.py"], "shared"),
    ("Memory evals", ["evals/run_memory.py"], "shared"),
    ("Seat learning evals", ["evals/run_seats.py"], "shared"),
    ("Run cockpit evals", ["evals/run_tui.py"], "alone"),     # a rename race and a watcher's timing
    ("Status and accounting evals", ["evals/run_status.py"], "shared"),
    ("Run history evals", ["evals/run_history.py"], "shared"),
    ("Finding outcomes evals", ["evals/run_outcomes.py"], "shared"),
    ("Tuning evals", ["evals/run_tune.py"], "shared"),
    ("Run audit evals", ["evals/run_audit.py"], "shared"),
    ("Benchmark harness self-test (no model calls)", ["evals/bench.py", "self-test"], "shared"),
    ("Repair drill trace checker self-test (no model calls)",
     ["evals/check_repair_trace.py", "--self-test", "--case", "evals/suite/build-repair-drill"], "shared"),
    ("Hook evals", ["evals/run_hook.py"], "groups"),
    ("Phrase checks (advisory, never fails)", ["evals/run_phrases.py"], "shared"),
]


# These say pass their own way (a validation line, a JSON measurement, advisory phrases), not with a
# "N/N checks passed" line; every other job must print one, with at least one check.
NO_COUNT = {"scripts/quick_validate.py", "evals/run_context_pilot.py", "evals/run_phrases.py"}

# The fast tier, by job name: each takes seconds on a Windows laptop with the others running beside it.
# Every group of the helper and hook evals takes minutes, so none is here.
FAST = {"Validate plugin", "Structural evals", "Ratchet (sizes and structure only go down)",
        "Ratchet self-test", "Unit tests (tests/py)", "Context delivery pilot (byte accounting, no model calls)",
        "Repair drill trace checker self-test (no model calls)", "Run history evals", "Seat learning evals",
        "Finding outcomes evals", "Repair loop evals", "Evidence model evals", "Context evals", "Impact evals",
        "Benchmark harness self-test (no model calls)", "Model routing evals"}
UNIT_TESTS = ROOT / "tests" / "py"


class Job:
    def __init__(self, name, args, alone):
        self.name, self.args, self.alone = name, args, alone
        self.code, self.seconds, self.output = None, 0.0, b""

    @property
    def command(self):
        return "python " + " ".join(self.args)

    def checks(self):
        found = re.findall(rb"^(\d+)/(\d+) checks passed", self.output, re.MULTILINE)
        if found:
            return int(found[-1][0]), int(found[-1][1])
        ran = re.findall(rb"^Ran (\d+) tests? in ", self.output, re.MULTILINE)   # unittest's own count
        if not ran:
            return None
        failed = re.search(rb"^FAILED \((.*)\)", self.output, re.MULTILINE)
        lost = sum(int(n) for n in re.findall(rb"(?:failures|errors)=(\d+)", failed.group(1))) if failed else 0
        return int(ran[-1]) - lost, int(ran[-1])

    @property
    def ok(self):
        """Exit 0 and, for a suite that counts its checks, at least one check run: a suite that skipped
        everything (no bash, say) has checked nothing, so it never counts as a pass."""
        counts = self.checks()
        return self.code == 0 and (self.args[0] in NO_COUNT or bool(counts and counts[1] > 0))

    @property
    def verdict(self):
        if self.code != 0:
            return "FAILED (exit %d)" % self.code
        return "passed" if self.ok else "FAILED (no checks ran)"


def group_jobs(name, args):
    """One job per group the suite lists. If it can't list them, the whole suite as one job, run alone."""
    listing = subprocess.run([PY, *args, "--list"], cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
    groups = [line.split("\t") for line in listing.stdout.splitlines() if line.count("\t") == 2]
    if listing.returncode != 0 or not groups:
        return [Job(name, args, True)], "%s --list failed (exit %s): %s" % (
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
    parser.add_argument("--fast", action="store_true", help="run only the fast tier (marked fast in --list)")
    parser.add_argument("--list", action="store_true", help="print the jobs and their commands; run nothing")
    opts = parser.parse_args()

    jobs, problems, skipped = [], [], []
    for name, args, how in SUITES:
        if opts.fast and name not in FAST:
            continue
        if how == "unit" and not UNIT_TESTS.is_dir():
            skipped.append("%s: skipped, tests/py/ does not exist yet" % name)
        elif how == "groups":
            more, problem = group_jobs(name, args)
            jobs += more
            if problem:
                problems.append(problem)
        else:
            jobs.append(Job(name, args, how == "alone"))
    problems += ["%s is not in evals/run_all.py's list, so it would never run" % f for f in unlisted()]
    if opts.list:
        for job in jobs:
            print("%-6s %-4s %-60s %s" % ("alone" if job.alone else "shared", "fast" if job.name in FAST else "",
                                          job.name, job.command))
        for line in skipped:
            print("SKIPPED: " + line)
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
            title = "%s: %s in %.0f s" % (job.name, job.verdict, job.seconds)
            print(("::group::" if actions else "\n===== ") + title, flush=True)
            sys.stdout.buffer.write(job.output if job.output.endswith(b"\n") or not job.output else job.output + b"\n")
            sys.stdout.buffer.flush()
            print("::endgroup::" if actions else "===== end of " + job.name, flush=True)

    started = time.monotonic()
    width = max(1, opts.jobs)
    print("%s%d jobs: %d run alone first, then the rest %d at a time" % (
        "The fast tier, a first look and not the gate: " if opts.fast else "", len(jobs),
        sum(j.alone for j in jobs), width), flush=True)
    for line in skipped:
        print("[skip] " + line, flush=True)
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
        print("%-62s %-7s %5.0fs  %s" % (job.name[:62], "pass" if job.ok else "FAIL", job.seconds,
                                         "%d/%d" % counts if counts else "-"))
    for name, args, how in SUITES:   # a split suite's groups add up to the suite
        counts = [j.checks() for j in jobs if j.args[0] == args[0]]
        if how == "groups" and len(counts) > 1 and all(counts):
            print("%-62s %-7s %6s  %d/%d" % (name + ", all groups", "", "", sum(c[0] for c in counts),
                                              sum(c[1] for c in counts)))
    for line in skipped:
        print(line)
    failed = [j for j in jobs if not j.ok]
    print("\n%d jobs%s, %d failed, %.0f s in all (%.0f s of suite time)" % (
        len(jobs), " in the fast tier" if opts.fast else "", len(failed), wall, sum(j.seconds for j in jobs)))
    if os.environ.get("GITHUB_STEP_SUMMARY"):   # the same table on the run's summary page
        rows = ["| %s | %s | %.0f s | %s |" % (j.name, "pass" if j.ok else "**FAIL**", j.seconds,
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
           "Helper evals: citations": 115, "Memory evals": 105, "Tuning evals": 75, "Hook evals: main": 60}


def weight(job):
    return WEIGHTS.get(job.name, 10)


if __name__ == "__main__":
    sys.exit(main())
