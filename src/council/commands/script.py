"""A scripts/ entry point run inside the command's own Python process, its main() called with the words the helper
gave it: the repair loop for `council gate`, the seat advice for `council ledger advice`, the impact graph for
`council index`, the memory drafts for `council memory`. The scripts are loaded by path until they move into the
package (S9)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import traceback
from pathlib import Path
from types import ModuleType

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
_LOADED: dict[str, ModuleType] = {}


def load(name: str) -> ModuleType:
    """scripts/<name>.py as a module, loaded once. It may set its own streams up as it loads; the command's stay."""
    if name not in _LOADED:
        spec = importlib.util.spec_from_file_location("council_script_" + name, str(SCRIPTS / (name + ".py")))
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        streams = sys.stdout, sys.stderr
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        for kept in (stream for stream in streams if hasattr(stream, "reconfigure")):
            kept.reconfigure(encoding="utf-8", errors="surrogateescape", newline="\n")  # type: ignore[attr-defined]
        _LOADED[name] = module
    return _LOADED[name]


def run(name: str, words: list[str], faults: tuple[type[BaseException], ...] = ()) -> int:
    """`python scripts/<name>.py <words>` here: its exit code, an argparse refusal's 2 among them. A fault it would
    have printed and exited 2 on, as its own `__main__` does, is printed the same way."""
    module = load(name)
    argv, sys.argv = sys.argv, [name + ".py"] + list(words)
    try:
        try:
            code = module.main()
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
        sys.argv = argv
        sys.stdout.flush()
    return int(code or 0)


def captured(name: str, words: list[str], faults: tuple[type[BaseException], ...] = (),
             keep_errors: bool = True) -> tuple[int, str, str]:
    """run(), with what it printed on stdout and stderr kept rather than shown."""
    load(name)                                           # before the streams are swapped: it sets them up as it loads
    said, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(said), contextlib.redirect_stderr(errors if keep_errors else io.StringIO()):
        code = run(name, words, faults)
    return code, said.getvalue(), errors.getvalue()
