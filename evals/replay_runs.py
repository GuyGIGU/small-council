"""The replay's fixtures made again (python evals/run_replay.py --remake): a review run and an implement run driven
through the real helper in scratch repos, as a Chair that follows its mode's steps would drive them, each written
down as the session transcript Claude Code would keep, then exported with `council run export --anon` into
evals/fixtures/runs/<name>/. No agent runs: an agent's dispatch is its Agent call and the seat records the helper
keeps; its work is the files it would write. Needs bash and git, as the helper's evals do.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASH = os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash")
SESSION = "replay-session-0001"
WORKER, VERIFIER, BUILDER = ("small-council:council-" + n for n in ("worker", "verifier", "builder"))


class Chair:
    """Drives the helper in one repo and keeps the main thread's transcript of it."""

    def __init__(self, repo: Path, cache: Path) -> None:
        self.repo, self.lines, self.n = repo, [], 0
        marks = cache / "small-council" / "sessions"
        marks.mkdir(parents=True, exist_ok=True)
        (marks / SESSION).write_text("")
        self.env = dict(os.environ, XDG_CACHE_HOME=str(cache), CLAUDE_CODE_SESSION_ID=SESSION,
                        GIT_AUTHOR_NAME="eval", GIT_AUTHOR_EMAIL="eval@example.invalid",
                        GIT_COMMITTER_NAME="eval", GIT_COMMITTER_EMAIL="eval@example.invalid")
        for var in ("COUNCIL_RUN", "COUNCIL_ALLOW_NO_HOOKS", "CLAUDE_PLUGIN_ROOT"):
            self.env.pop(var, None)

    def _line(self, kind: str, content: object) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        self.lines.append({"type": kind, "timestamp": stamp, "isSidechain": False, "sessionId": SESSION,
                           "message": {"role": kind, "content": content}})

    def prompt(self, words: str) -> None:
        self._line("user", words)

    def say(self, words: str) -> None:
        self._line("assistant", [{"type": "text", "text": words}])

    def tool(self, name: str, given: dict, output: str = "", error: bool = False) -> None:
        self.n += 1
        ident = "toolu_%03d" % self.n
        self._line("assistant", [{"type": "tool_use", "id": ident, "name": name, "input": given}])
        self._line("user", [{"type": "tool_result", "tool_use_id": ident, "content": output, "is_error": error}])

    def helper(self, *words: str) -> tuple[int, str, str]:
        """A council call outside the Chair's transcript (the agent gate's, a builder's)."""
        proc = subprocess.run([BASH, str(ROOT / "bin" / "council"), *words], cwd=str(self.repo), env=self.env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        if proc.returncode not in (0, 1):
            raise RuntimeError("council %s: exit %d\n%s%s" % (" ".join(words), proc.returncode, proc.stdout,
                                                            proc.stderr))
        return proc.returncode, proc.stdout, proc.stderr

    def council(self, *words: str) -> str:
        """A council call the Chair makes, kept in the transcript with what it printed; its stdout."""
        self.n += 1
        ident = "toolu_%03d" % self.n
        self._line("assistant", [{"type": "tool_use", "id": ident, "name": "Bash",
                                  "input": {"command": " ".join(["council"] + [typed(w) for w in words]),
                                            "description": "council " + words[0]}}])
        code, out, err = self.helper(*words)
        self._line("user", [{"type": "tool_result", "tool_use_id": ident, "content": (out + err).strip(),
                             "is_error": code != 0}])
        return out

    def dispatch(self, kind: str, seat: str, agent: str, run: Path, file: str = "") -> str:
        """An agent sent for a seat: the agent gate's count, the Agent call, the seat recorded running."""
        self.helper("cap", "check", "--session", SESSION, "Agent", "type=" + kind, "seat=" + seat, "run=" + run.name,
                    *(["file=" + file] if file else []))
        self.tool("Agent", {"subagent_type": kind, "description": seat, "prompt": "Seat: %s\nRun: %s" % (seat, run),
                            "run_in_background": True}, "Async agent launched. agentId: " + agent)
        return self.council("seat", seat, "running", "agent=" + agent)

    def card(self) -> None:
        widget = self.council("status", "--widget")
        self.tool("mcp__visualize__show_widget", {"widget_code": widget[:200]}, "shown")

    def closing(self, run: Path) -> None:
        out = self.council("status", "--run", run.name)
        status = next((line for line in out.splitlines() if line.startswith("Status:")), "Status: done")
        self.say("**%s** The run is closed; the audit's lines are above." % status)
        self.council("status", "--line", "--run", run.name)

    def rulings(self, question: str, answer: str) -> None:
        self.tool("AskUserQuestion", {"questions": [{"question": question}]}, answer)
        self.council("state", "decision=" + answer)

    def save(self, path: Path) -> None:
        path.write_text("".join(json.dumps(line, ensure_ascii=False) + "\n" for line in self.lines), encoding="utf-8")


def typed(word: str) -> str:
    """A word as a Chair types it on a command line: key="free words" quoted after the =, anything else as shlex
    quotes it."""
    key, sep, value = word.partition("=")
    if sep and key.isidentifier() and shlex.quote(value) != value:
        return '%s="%s"' % (key, value.replace("\\", "\\\\").replace('"', '\\"').replace("$", r"\$"))
    return shlex.quote(word)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def git(repo: Path, *words: str) -> None:
    subprocess.run(["git", *words], cwd=str(repo), check=True, capture_output=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="eval", GIT_AUTHOR_EMAIL="eval@example.invalid",
                            GIT_COMMITTER_NAME="eval", GIT_COMMITTER_EMAIL="eval@example.invalid"))


def project(base: Path, name: str, files: dict) -> Path:
    repo = base / name
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    for path, text in dict(files, **{".council/council.config.md": "# Council config\n"}).items():
        write(repo / path, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def plan(run: Path, mode: str, size: str, seats: dict, tokens: int) -> None:
    """The run plan: the run's size and estimate, and each selected seat with its role (seats: slug -> role)."""
    rows = [("schema", "plan", "version", "1"), ("run", "run", "id", run.name), ("run", "run", "mode", mode),
            ("run", "run", "size", size), ("assessment", "run", "risk", "medium"),
            ("assessment", "run", "complexity", "medium"), ("assessment", "run", "uncertainty", "low"),
            ("budget", "run", "agent-cap", "10"), ("budget", "run", "estimated-tokens", str(tokens)),
            ("verification", "run", "level", "independent")]
    for slug, role in seats.items():
        rows += [("seat", slug, "disposition", "selected"), ("seat", slug, "role", role),
                 ("context", slug, "level", "full" if role == "chair" else "focused"),
                 ("budget", slug, "tool-calls", "40")]
    write(run / "run-plan.tsv", "# Small Council run plan v1.\nkind\tid\tfield\tvalue\treason\n"
          + "".join("%s\t%s\t%s\t%s\tchosen for this run\n" % row for row in rows))


def review(chair: Chair) -> Path:
    """A squad review run through its ten stages: two workers, one verifier, a finding confirmed and delivered."""
    chair.prompt("/council-review the change on this branch")
    chair.council("run", "status")
    chair.say("Squad review: Hunt and Tests, then one blind verifier — est. ~250k tokens. Going ahead.")
    run = Path(chair.council("run", "open", "council-review").strip().splitlines()[-1])
    write(run / "ask.md", "# Ask — review the change\nsource: said at the time\n## In your words\n"
          "the change on this branch\n")
    plan(run, "council-review", "squad", {"chair": "chair", "hunt": "worker", "tests": "worker",
                                          "verify-1": "verifier"}, 250000)
    chair.council("run", "plan", "check")
    chair.council("state", "size=squad — 2 seats + 1 verifier, est. ~250k tokens")
    chair.council("state", "phase=prepare")
    chair.council("gate", "tests", "--", "true")
    for phase in ("assign", "brief", "work"):
        chair.council("state", "phase=" + phase)
    chair.dispatch(WORKER, "hunt", "a1b2c3d4e5f6a7b8c", run)
    chair.card()
    chair.dispatch(WORKER, "tests", "a2b3c4d5e6f7a8b9c", run)
    write(run / "seats" / "hunt.md", "# Hunt\nref: hunt\n## Index\n1 · P1 · Principle 1 · app.py:2 · Expiry skipped\n")
    chair.council("seat", "hunt", "done", "tokens=58211")
    write(run / "seats" / "tests.md", "# Tests\nref: tests\n## Index\n")
    chair.council("seat", "tests", "done", "tokens=41377")
    for phase in ("collect", "judge"):
        chair.council("state", "phase=" + phase)
    write(run / "synthesis.md", "# Synthesis\n## Kept\n"
          "1 · P1 · Principle 1 · app.py:2 · Expiry skipped · state: OBSERVED · from: hunt#1\n")
    chair.council("state", "phase=challenge")
    chair.dispatch(VERIFIER, "verify-1", "v9f8e7d6c5b4a3f2e", run)
    write(run / "verify-1.md", "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| 1 | Expiry skipped | CONFIRMED | app.py:2 never reads the expiry |\n")
    chair.council("seat", "verify-1", "done", "tokens=39504")
    chair.council("evidence", "build")
    deliver(chair, run, ".council/reviews/%s-review.md" % run.name[:10], "Fix the expiry finding now?")
    return run


def implement(chair: Chair) -> Path:
    """A build of two tasks: a builder per task, each proved by a before/after pair, one verifier at converge."""
    chair.prompt("/council-implement build the two tasks")
    chair.council("run", "status")
    chair.say("Build: two tasks, a builder each, one verifier at converge — est. ~520k tokens. Going ahead.")
    run = Path(chair.council("run", "open", "council-implement").strip().splitlines()[-1])
    write(run / "ask.md", "# Ask — build the two tasks\nsource: said at the time\n## In your words\n"
          "build the two tasks\n")
    plan(run, "council-implement", "squad", {"chair": "chair", "task-1": "worker", "task-2": "worker",
                                             "verify-1": "verifier"}, 520000)
    chair.council("run", "plan", "check")
    chair.council("state", "size=squad — 2 builders + 1 verifier, est. ~520k tokens")
    chair.council("state", "phase=prepare")
    chair.council("gate", "tests", "--", "true")
    chair.council("state", "phase=build")
    for task, agent in ((1, "b1c2d3e4f5a6b7c8d"), (2, "b2c3d4e5f6a7b8c9d")):
        chair.council("seat", "task-%d" % task, "queued")
        chair.dispatch(BUILDER, "task-%d" % task, agent, run, "report-%d" % task)
        if task == 1:
            chair.card()
        build(chair, run, task)
        chair.council("seat", "task-%d" % task, "done", "tokens=%d" % (180000 + task * 1111))
    chair.council("state", "phase=challenge")
    chair.dispatch(VERIFIER, "verify-1", "v1f2e3d4c5b6a7f8e", run)
    write(run / "verify-1.md", "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| 1 | Task 1 | OK | done-1.txt is there |\n| 2 | Task 2 | OK | done-2.txt is there |\n")
    chair.council("seat", "verify-1", "done", "tokens=61203")
    chair.council("check")
    log = ".council/logs/%s-build.md" % run.name[:10]
    write(chair.repo / log, "# Build log\nRun: %s\n## Converge\n| Task | Result |\n|---|---|\n| 1 | OK |\n| 2 | OK |\n"
          "## Shortcuts and concessions\nnone\n" % run.name)
    deliver(chair, run, log, "Commit the two tasks now?")
    return run


def build(chair: Chair, run: Path, task: int) -> None:
    """One builder's round, as its own calls (not the Chair's): the before check red, the change, the after check
    green, the report and the saved round."""
    proof = "test -f done-%d.txt" % task
    chair.helper("gate", "before-%d" % task, "--", "bash", "-c", proof)
    write(chair.repo / ("done-%d.txt" % task), "task %d\n" % task)
    chair.helper("gate", "after-%d" % task, "--", "bash", "-c", proof)
    write(run / ("report-%d.md" % task), "Cause: none\nOwner: done-%d.txt\nRemoved: none\nAssumed: nothing\n\n"
          "Wrote the file the task asks for.\n" % task)
    chair.helper("patch", "save", str(task))


def deliver(chair: Chair, run: Path, deliverable: str, question: str) -> None:
    """Deliver, the rulings as one question, Learn and the close, then the closing card."""
    chair.council("state", "phase=deliver")
    chair.council("ask", "save")
    write(chair.repo / deliverable, "---\ntitle: %s\nrun: %s\n---\n# %s\n" % (run.name, run.name, run.name))
    chair.council("state", "deliverable=" + deliverable)
    chair.rulings(question, "yes, go ahead")
    chair.council("state", "phase=learn")
    chair.council("run", "close")
    chair.closing(run)


def remake(fixtures: Path) -> int:
    if not BASH or not shutil.which("git"):
        print("bash and git are needed to make the fixtures again")
        return 3
    with tempfile.TemporaryDirectory(prefix="council-remake-") as temporary:
        base = Path(os.path.realpath(temporary))
        for name, files, drive in (("review-squad", {"app.py": "def check(token):\n    return True\n"}, review),
                                   ("implement-two-tasks", {"app.txt": "app\n"}, implement)):
            chair = Chair(project(base, name, files), base / "cache")
            run = drive(chair)
            chair.prompt("thanks")
            log = base / (name + ".jsonl")
            chair.save(log)
            dest = fixtures / name
            if dest.exists():
                shutil.rmtree(str(dest))
            code, out, err = chair.helper("run", "export", "--anon", str(run), str(dest), "--transcript", str(log))
            print(out + err, end="")
            if code:
                return code
    return 0


if __name__ == "__main__":
    sys.exit(remake(ROOT / "evals" / "fixtures" / "runs"))
