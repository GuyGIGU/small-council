"""A tool's entry, its main() called with the words the helper gave it, run inside the command's own Python process:
the repair loop for `council gate`, the claim index for `council evidence`, the memory drafts for `council memory`.
A tool is a module of this package (TOOLS); the five view scripts are still loaded from scripts/ by path.

A caller outside the helper (the seat-gate hook, the evals) runs a tool by path, through the same run():
    python src/council/commands/script.py <tool> <words>"""
from __future__ import annotations

import builtins
import contextlib
import importlib
import importlib.util
import io
import sys
import traceback
from functools import reduce
from pathlib import Path
from types import ModuleType
from typing import Callable

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
TOOLS = {"audit": "audit", "chair_usage": "chair_usage", "evidence": "evidence", "memory": "memory_draft",
         "repair": "repair_trail", "tune": "tune_knobs"}
FAULTS = {  # what a tool says as '<tool>: <fault>' and exits 2 on, as its own process did; names in its module
    "evidence": "EvidenceError paths.RecordError UnicodeError OSError ValueError",
    "history": "ledger.LedgerError OSError ValueError",
    "memory": "MemoryError_ evidence.EvidenceError repair.RepairError evidence.paths.RecordError OSError UnicodeError "
              "ValueError",
    "repair": "RepairError paths.RecordError OSError UnicodeError ValueError TypeError",
    "tune": "TuneError paths.RecordError OSError UnicodeError ValueError",
}
_LOADED: dict[str, ModuleType] = {}


def load(name: str) -> ModuleType:
    """A tool's module; a view script is loaded once as its own process had it: scripts/ on the path, no
    bytecode, our streams."""
    if name in TOOLS:
        return importlib.import_module("council.commands." + TOOLS[name])
    if name not in _LOADED:
        sys.dont_write_bytecode = True
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
        spec = importlib.util.spec_from_file_location("council_script_" + name, str(SCRIPTS / (name + ".py")))
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        streams = sys.stdout, sys.stderr
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        for kept in (stream for stream in streams if hasattr(stream, "reconfigure")):
            kept.reconfigure(encoding="utf-8", errors="surrogateescape", newline="\n")  # type: ignore[attr-defined]
        _LOADED[name] = module
    return _LOADED[name]


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
        return guarded(name, (lambda: module.main(list(words))) if name in TOOLS else module.main, faults)
    finally:
        sys.argv = argv


def captured(name: str, words: list[str]) -> tuple[int, str, str]:
    """run(), with what it printed on stdout and stderr kept rather than shown."""
    load(name)                                 # before the streams are swapped: a script sets them as it loads
    said, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(said), contextlib.redirect_stderr(errors):
        code = run(name, words)
    return code, said.getvalue(), errors.getvalue()


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.path[0] = str(Path(__file__).resolve().parents[2])      # the package's folder, not this file's
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.exit(run(sys.argv[1], sys.argv[2:]))
