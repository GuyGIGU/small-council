"""A build's gate result is its own repair record (references/run/repair-loop.md): a failure is an attempt on the
current task, and the pass of a gate whose trail is open closes it — recorded here, so the stop after three
failures holds without a separate command. The gate's exit code never depends on this.

The repair loop itself is scripts/repair.py, loaded here by path until the scripts move into the package (S9)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import re
from pathlib import Path
from types import ModuleType

from council.commands import cli, resolve
from council.records import config

ENGINE = Path(__file__).resolve().parents[3] / "scripts" / "repair.py"
_LOADED: list[ModuleType] = []


def engine() -> ModuleType:
    """scripts/repair.py as a module, loaded once."""
    if not _LOADED:
        spec = importlib.util.spec_from_file_location("council_repair_engine", str(ENGINE))
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        _LOADED.append(module)
    return _LOADED[0]


def run_quietly(action: str, task: str | None, gate: str | None, run: str) -> tuple[int, str]:
    """One repair.py action, its stdout and refusal kept as the helper's $( … 2>&1 ) kept them."""
    repair, said = engine(), io.StringIO()
    with contextlib.redirect_stdout(said):
        try:
            code = repair.act(action, task, gate, repair.checked_run(Path(run)))
        except repair.ERRORS as exc:
            said.write("repair: %s\n" % exc)
            code = 2
    return code, said.getvalue().rstrip("\n")


def trail(run: str, name: str) -> str:
    """One gate's trail, "<state>\\t<task>\\t<seq>": none when the run keeps none, '' when it can't be read — a
    fault of the trail's own never stops a gate (it is said once)."""
    if not Path(run, "repairs.jsonl").is_file():
        return "none\t-\t-"
    code, said = run_quietly("trail", name, None, run)
    if code != 0:
        cli.warn("council: the repair trail could not be read, so no stop applies to gate %s — council repair check"
                 % name)
        return ""
    return said


def current_task(run: str) -> str:
    """The build task an attempt counts under: "task <n>" at the start of next:, as T<n>; '' when none."""
    found = re.match(r"[Tt]ask[ \t\n\v\f\r]*([0-9]+)", resolve.field(Path(run), "next"))
    return "T" + found.group(1) if found else ""


def alert(run: str, words: str) -> None:
    """Tell the Chair to alert the owner, unless the config turns notifications off."""
    home = run.rsplit("/runs/", 1)[0] if "/runs/" in run else None
    if config.notifications_off(home if home is not None else _home()):
        return
    cli.warn("council: %s — send the owner the line `council status --line --run %s` prints, once, with a "
             "PushNotification tool (it may be a deferred tool: search the tools for it first)"
             % (words, run.rstrip("/").split("/")[-1]))


def _home() -> str:
    from council.records import home
    return home.council_home()


def record(run: str, name: str, code: int, gate_trail: str, same: bool) -> None:
    """Record this gate's result on the build's repair trail, when it is one: never for a proof (before-,
    after-, regress-), nor a failure the baseline already had."""
    if resolve.field(Path(run), "mode") != "council-implement" or resolve.field(Path(run), "phase") != "build":
        return
    if name.startswith(("before-", "after-", "regress-")):
        return
    state = gate_trail.split("\t")[0]
    if code == 0 and state != "open":
        return
    if code != 0 and same and state != "open":
        cli.say("repair: not counted — the same tests fail as at the baseline, so this is no attempt on the task")
        return
    if not gate_trail and Path(run, "repairs.jsonl").is_file():
        return                                   # unreadable: trail() has said so, once
    task = _task(run, name, code, gate_trail)
    if task is None:
        return
    status, said = run_quietly("record", task, name, run)
    if status != 0:
        cli.say("repair: not counted — %s (council repair check)"
                % (said[len("repair: "):] if said.startswith("repair: ") else said))
        return
    cli.say(said)
    if "next stop" in said:
        alert(run, "the build is blocked: tell the user what failed and what is left")


def _task(run: str, name: str, code: int, gate_trail: str) -> str | None:
    """The task id this attempt counts under, or None (said) when there is none."""
    task, current = "", current_task(run)
    parts = gate_trail.split("\t")
    if parts[0] in ("open", "allowed"):          # the trail's own task: a pass always closes it, and a failure
        task = parts[1] if len(parts) > 1 else ""  # counts there while the build is still on it
        if code != 0 and current and not (task == current or task.startswith(current + "-")):
            task = ""
    if task:
        return task
    if not current:
        cli.say('repair: not counted — no task id: council state next="task <n>: <title>"')
        return None
    if not Path(run, "repairs.jsonl").is_file():
        return current
    status, said = run_quietly("free", current, name, run)
    if status != 0:
        cli.say("repair: not counted — the repair trail can't be read: council repair check")
        return None
    return said
