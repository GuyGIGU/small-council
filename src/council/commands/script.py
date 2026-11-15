"""A tool's or a view's entry, its main() called with the words the helper gave it, run inside the command's own
Python process: the repair loop for `council gate`, the claim index for `council evidence`, the memory drafts for
`council memory`, the card for `council status`. Each is a module of the package (TOOLS): a tool in commands/, a
view in views/.

A caller outside the helper (the seat-gate hook, the council view, the evals) runs one by path, through
the same run():
    python src/council/commands/script.py <tool> <words>"""
from __future__ import annotations

import builtins
import contextlib
import importlib
import io
import sys
import traceback
from functools import reduce
from pathlib import Path
from types import ModuleType
from typing import Callable

TOOLS = {"audit": "commands.audit", "chair_usage": "commands.chair_usage", "evidence": "commands.evidence",
         "memory": "commands.memory_draft", "repair": "commands.repair_trail", "status": "views.status"}
FAULTS = {  # what a tool says as '<tool>: <fault>' and exits 2 on, as its own process did; names in its module
    "evidence": "EvidenceError paths.RecordError UnicodeError OSError ValueError",
    "memory": "MemoryError_ evidence.EvidenceError repair.RepairError evidence.paths.RecordError OSError UnicodeError "
              "ValueError",
    "repair": "RepairError paths.RecordError OSError UnicodeError ValueError TypeError",
}


def load(name: str) -> ModuleType:
    return importlib.import_module("council." + TOOLS[name])


def guarded(name: str, call: Callable[[], int | None], faults: tuple[type[BaseException], ...]) -> int:
    """call() as the tool's own process ran it: its exit code, an argparse refusal's 2 among them; a fault it
    names said as '<name>: <fault>' with 2; any other, its traceback with 1."""
    try:
        try:
            code = call()
        except SystemExit as stop:
            code = stop.code if isinstance(stop.code, int) else (0 if stop.code is None else 1)
        except faults as fault:
            sys.stdout.flush()
            print("%s: %s" % (name, fault), file=sys.stderr)
            code = 2
        except Exception:  # noqa: BLE001 — as its own process would: the traceback, and exit 1
            sys.stdout.flush()
            traceback.print_exc()
            code = 1
    finally:
        sys.stdout.flush()
    return int(code or 0)


def run(name: str, words: list[str]) -> int:
    """`<name> <words>` here, as its own process ran it (guarded)."""
    module = load(name)
    faults = tuple(reduce(getattr, fault.split("."), builtins if hasattr(builtins, fault) else module)
                   for fault in FAULTS.get(name, "").split())
    argv, sys.argv = sys.argv, [name + ".py"] + list(words)     # argparse names the tool by it
    try:
        return guarded(name, lambda: module.main(list(words)), faults)
    finally:
        sys.argv = argv


def captured(name: str, words: list[str]) -> tuple[int, str, str]:
    """run(), with what it printed on stdout and stderr kept rather than shown."""
    said, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(said), contextlib.redirect_stderr(errors):
        code = run(name, words)
    return code, said.getvalue(), errors.getvalue()


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.path[0] = str(Path(__file__).resolve().parents[2])      # the package's folder, not this file's
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:                                  # a windowless Python (pythonw) may have none
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.exit(run(sys.argv[1], sys.argv[2:]))
