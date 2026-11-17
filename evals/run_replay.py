#!/usr/bin/env python3
"""The Chair drill eval (#70): `council run audit` over saved runs, whose step order must hold.

The evals cover the helper and the hooks; what the Chair does between its calls was checked only by the audit of a
real run, so a skill-text regression showed up as a FAIL on the user's next job. This replays saved run folders
(evals/fixtures/runs/<name>/: the files the audit reads and the session's transcript.jsonl, as
`council run export --anon` writes them) through the audit itself, the one checker of the Chair's steps:
- each fixture must pass: no item FAILs, and every one of the Chair's steps is read (the size and cost before the
  first dispatch, the status card at it, the rulings as one question, Deliver before the close, the closing card);
- each planted mutation must FAIL on the step it breaks, and on that step alone: the status card dropped, the
  close put before Deliver, an agent dispatched before the size and cost were recorded;
- no fixture holds a path, a user name or an e-mail address from the machine that made it.
No model is called. Each fixture is replayed from a copy, so nothing in the tree changes.

    python evals/run_replay.py             # the replay (a few seconds)
    python evals/run_replay.py --remake    # make the fixtures again: drive the real helper through a review and an
                                           # implement run in scratch repos, then export each with --anon
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "evals" / "fixtures" / "runs"
AUDIT = (str(ROOT / "src" / "council" / "commands" / "script.py"), "audit")
STEPS = ("Size and cost before the first dispatch", "Status card at the first dispatch", "Rulings as one question",
         "Closed after Deliver", "Closing card")
PRIVATE = re.compile(r"[A-Za-z]:[\\/]|/(?:c|Users|home|tmp|mnt|private|var)/|\bUsers\b|[\w.+-]+@[\w-]+\.[\w.]+")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
checks = []


def check(name, good, detail=""):
    checks.append((name, bool(good), detail))
    print("[%s] %s%s" % ("PASS" if good else "FAIL", name, "" if good else "  (%s)" % str(detail).strip()[:1500]),
          flush=True)


def audit(folder):
    """The audit's exit code, and each item's verdict and words by label."""
    proc = subprocess.run([sys.executable, *AUDIT, "--run", str(folder), "--transcript",
                           str(folder / "transcript.jsonl")], capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    items = dict((label, (verdict, words)) for verdict, label, words in
                 re.findall(r"^  (pass|warn|FAIL|later)\s+([^:]+): (.*)$", proc.stdout, re.MULTILINE))
    return proc.returncode, items, proc.stdout + proc.stderr


def copy(fixture, base, name):
    """The fixture in a scratch folder, every file given one time (a checkout gives none it can be trusted with)."""
    folder = base / name / fixture.name
    shutil.copytree(str(fixture), str(folder))
    stamp = 1_700_000_000
    for path in folder.iterdir():
        os.utime(str(path), (stamp, stamp))
    return folder


def transcript(folder):
    return [json.loads(line) for line in (folder / "transcript.jsonl").read_text(encoding="utf-8").splitlines()]


def save_transcript(folder, lines):
    (folder / "transcript.jsonl").write_text("".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines),
                                             encoding="utf-8", newline="\n")


def blocks(line):
    content = line["message"]["content"]
    return content if isinstance(content, list) else []


def use_of(line, test):
    return any(b.get("type") == "tool_use" and test(b) for b in blocks(line))


def drop_card(folder):
    """No status card at the first dispatch: every show_widget call and its result gone."""
    lines = transcript(folder)
    ids = set(b["id"] for line in lines for b in blocks(line) if b.get("type") == "tool_use"
              and "show_widget" in b.get("name", ""))
    save_transcript(folder, [line for line in lines if not any(b.get("id") in ids or b.get("tool_use_id") in ids
                                                               for b in blocks(line))])


def close_before_deliver(folder):
    """The close recorded before Deliver: the step into Deliver moved after run.closed, the stream renumbered."""
    rows = (folder / "events.tsv").read_text(encoding="utf-8").splitlines()
    head, body = rows[0], [r.split("\t") for r in rows[1:] if r.strip()]
    deliver = [r for r in body if r[3] == "run.phase_changed" and r[5] == "deliver"]
    rest = [r for r in body if r not in deliver]
    end = next(n for n, r in enumerate(rest) if r[3] == "run.closed")
    moved = rest[:end + 1] + [r[:2] + [rest[end][2]] + r[3:] for r in deliver] + rest[end + 1:]
    (folder / "events.tsv").write_text("\n".join([head] + ["\t".join(r[:1] + [str(n)] + r[2:])
                                                           for n, r in enumerate(moved, 1)]) + "\n",
                                       encoding="utf-8", newline="\n")


def dispatch_before_size(folder):
    """The size and cost recorded only after the first agent went out: that Bash call moved past the first Agent."""
    lines = transcript(folder)
    sized = next(n for n, line in enumerate(lines) if use_of(line, lambda b: re.search(
        r"\bcouncil state size=", str((b.get("input") or {}).get("command", "")))))
    pair = lines[sized:sized + 2]
    rest = lines[:sized] + lines[sized + 2:]
    agent = next(n for n, line in enumerate(rest) if use_of(line, lambda b: b.get("name") == "Agent"))
    for line in pair:
        line["timestamp"] = rest[agent + 1].get("timestamp", line.get("timestamp"))
    save_transcript(folder, rest[:agent + 2] + pair + rest[agent + 2:])


MUTATIONS = (("the status card dropped", drop_card, "Status card at the first dispatch", "not shown"),
             ("the close put before Deliver", close_before_deliver, "Closed after Deliver", "without entering Deliver"),
             ("an agent dispatched before the size and cost", dispatch_before_size,
              "Size and cost before the first dispatch", "before the run's size and cost were recorded"))


def replay(base):
    fixtures = sorted(p for p in FIXTURES.iterdir() if p.is_dir()) if FIXTURES.is_dir() else []
    check("fixtures: at least a review run and an implement run are saved", {"council-review", "council-implement"}
          <= set(re.search(r"^mode: (\S+)", (f / "session-state.md").read_text(encoding="utf-8"), re.MULTILINE)
                 .group(1) for f in fixtures), [f.name for f in fixtures])
    for fixture in fixtures:
        names = [re.escape(n) for n in {Path.home().name, os.environ.get("USERNAME", ""), os.environ.get("USER", "")}
                 if len(n) >= 3]
        private = re.compile(PRIVATE.pattern + "".join(r"|\b%s\b" % n for n in names), re.IGNORECASE)
        leaks = ["%s: %s" % (p.name, m.group(0)) for p in sorted(fixture.iterdir())
                 for m in private.finditer(p.read_text(encoding="utf-8", errors="replace"))]
        check("%s: holds no path, user name or e-mail address from the machine that made it" % fixture.name,
              not leaks, leaks[:5])
        code, items, out = audit(copy(fixture, base, "as-saved"))
        fails = [label for label, (verdict, _) in items.items() if verdict == "FAIL"]
        check("%s: the audit passes the run as saved (exit 0, nothing FAILs)" % fixture.name, code == 0 and not fails,
              out)
        check("%s: every one of the Chair's steps is read, and passes" % fixture.name,
              all(items.get(step, ("",))[0] == "pass" for step in STEPS), out)
        for name, mutate, step, words in MUTATIONS:
            folder = copy(fixture, base, mutate.__name__)
            mutate(folder)
            code, items, out = audit(folder)
            fails = [label for label, (verdict, _) in items.items() if verdict == "FAIL"]
            check("%s, %s: the audit FAILs on %s, naming it, and on nothing else" % (fixture.name, name, step),
                  code == 1 and fails == [step] and words in items[step][1], out)


def main():
    if "--remake" in sys.argv:
        sys.path.insert(0, str(ROOT / "evals"))
        import replay_runs                                       # the fixture maker drives bash and git
        return replay_runs.remake(FIXTURES)
    with tempfile.TemporaryDirectory(prefix="council-replay-") as temporary:
        replay(Path(os.path.realpath(temporary)))
    passed = sum(1 for _, good, _ in checks if good)
    print("\n%d/%d checks passed" % (passed, len(checks)))
    return 0 if checks and passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
