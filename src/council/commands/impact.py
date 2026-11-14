"""council impact: the run's impact graph — the changed files since the run's base, their direct importers and the
tests linked to them — into the run's impact.tsv (scripts/impact.py). `council index` refreshes it after the change
index; a failure removes the old table, so nothing stale is read."""
from __future__ import annotations

import contextlib
import os
from pathlib import Path

from council.commands import cli, resolve, script
from council.records import home as where
from council.records.run_files import IMPACT


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "impact")
    cli.no_words("impact", words)
    return refresh(resolve.run_folder(args))


def refresh(run: Path, top: str = "") -> int:
    """impact.tsv from the run's base and code root: 0 when it was written, 1 (and no table) when it wasn't."""
    top = top or resolve.field(run, "code-root") or where.this_tree()
    base = resolve.field(run, "base")
    if not base:
        raise cli.Refusal("impact needs a change baseline — run council index first")
    output = run / IMPACT
    code = script.run("impact", ["--root", top, "--base", base, "--output", str(output)],
                      faults=(OSError, RuntimeError, ValueError))
    if code == 0:
        return 0
    with contextlib.suppress(OSError):
        os.remove(str(output))
    return 1
