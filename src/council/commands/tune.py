"""council tune [propose] [--json] | tune apply|revert budget … --user-said "…": conservative self-tuning
(scripts/tune.py). propose only reads; apply and revert change the config's estimate per worker, only with the
user's words, redacted here first and logged in tuning.md."""
from __future__ import annotations

import os
import shutil

from council.commands import cli
from council.commands.script_cmds import run_script
from council.records import home as where
from council.records import redact

USAGES = {"propose": (1, "usage: council tune [propose] [--json]"),
          "apply": (3, "usage: council tune apply budget <the value council tune showed, e.g. 150k> --user-said "
                       "\"<the user's words>\""),
          "revert": (2, "usage: council tune revert budget --user-said \"<the user's words>\"")}


def main(args: cli.Args, words: list[str]) -> int:
    action = words[0] if words and words[0] else "propose"
    if action not in USAGES:
        raise cli.Refusal("usage: council tune [propose] [--json] | tune apply budget <value> --user-said \"…\" | "
                          "tune revert budget --user-said \"…\"")
    propose = action == "propose"
    cli.takes_flags(args, "tune" if propose else "tune " + action, "json" if propose else "user-said")
    count, usage = USAGES[action]
    if len(words) > count if propose else len(words) != count:
        raise cli.Refusal(usage)
    if args.value("run"):
        raise cli.Refusal("tune reads this council home's record; it does not take --run")
    said = args.value("user-said")
    if not propose and not said:
        raise cli.Refusal("tune %s needs --user-said \"<the user's own words>\" — their answer, not a summary of it"
                          % action)
    home = where.council_home()
    if not os.path.isdir(where.native(home)):
        raise cli.Refusal("no council here (no %s) — run council-init" % home)
    if propose:
        return run_script("tune", ["propose", "--home", home] + (["--json"] if args.value("json") else []))
    import tempfile
    try:
        folder = where.here(tempfile.mkdtemp())
    except OSError:
        raise cli.Refusal("cannot make a temporary folder") from None
    try:
        with open(folder + "/said", "wb") as out:
            out.write((redact.said(said, line_breaks_only=True) + "\n").encode("utf-8", "surrogateescape"))
    except OSError:
        shutil.rmtree(folder, ignore_errors=True)
        raise cli.Refusal("cannot write " + folder) from None
    value = ["--value", words[2]] if action == "apply" else []
    try:
        return run_script("tune", [action, words[1]] + value + ["--home", home, "--said", folder + "/said"])
    finally:
        shutil.rmtree(folder, ignore_errors=True)
