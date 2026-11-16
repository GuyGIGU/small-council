"""council check's revert check on a build (references/build-proof.md, Read the result). A change proof that reads ok,
of a task with saved rounds, is run once more without the change. The tree of the files on disk is written to a
scratch folder outside the project and the run folder, and the after-check's recorded command runs there under the
gate time limit, first with the change still on: the control. If it doesn't pass there, the copy can't run this
check (it needs files the copy leaves out), and nothing more is tried. Then the task's rounds come off, newest
first (its test files kept, so the test that proved the change is the one that runs), and the command runs again.
It should fail. A rerun that still passes means the test proves nothing about the change; a check that can't be
made is said, and never counts as a pass. The outputs are kept as gates/reverted/after-<n>-with-change.txt and
after-<n>.txt, where no reader takes them for a gate; the scratch folder is removed whatever happened. Nothing in
the project changes."""
from __future__ import annotations

import contextlib
import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import NamedTuple

from council import git
from council.commands import check_proofs, gate_exec, gate_output, gate_run, patch_apply, patch_checks, proof_reach
from council.commands import resolve
from council.records import home as where
from council.records import patches

PASSED = "REVERT-PASSED"
FOLDER = "reverted"


def check(run: Path, top: str, number: str, command: str) -> tuple[str, str, str]:
    """(the proof's state, the row's words on the revert check, why it could not be made or '') for task <number>,
    whose change proof reads ok and which has saved rounds."""
    if proof_reach.RUNS in command or ".council/" in command:
        return _unmade("its command runs files under .council/, which a copy of the project leaves out")
    tree = git.files_tree(top)
    if not tree:
        return _unmade("the files in %s can't be read as a git tree" % top)
    scratch = Path(tempfile.mkdtemp(prefix="council-revert-"))
    try:
        if any(_under(scratch, Path(folder)) for folder in (where.native(top), run)):
            return _unmade("the scratch folder %s is inside the project or the run folder" % scratch.as_posix())
        why = write_copy(top, tree, scratch)
        return _unmade(why) if why else _decided(run, top, number, command, scratch)
    finally:
        _remove(scratch)


def _unmade(why: str) -> tuple[str, str, str]:
    return "ok", "revert check not made: " + why, why


def _under(path: Path, folder: Path) -> bool:
    inner, outer = os.path.realpath(str(path)), os.path.realpath(str(folder))
    return inner == outer or inner.startswith(outer.rstrip(os.sep) + os.sep)


def write_copy(top: str, tree: str, scratch: Path) -> str:
    """The tree of the files on disk now, written into scratch from its own blobs: git's bytes, which the saved
    rounds' patches were taken between, whatever line ends the checkout has (core.autocrlf). A submodule is
    copied from disk. '' when done, else why not."""
    try:
        listed = git.output(top, "ls-tree", "-r", "-z", "--full-tree", tree).decode("utf-8", "surrogateescape")
        entries = [entry.split("\t", 1)[0].split(" ") + [entry.split("\t", 1)[1]]
                   for entry in listed.split("\0") if "\t" in entry]
        blobs = _blobs(top, [sha for _, kind, sha, _ in entries if kind == "blob"])
        for mode, kind, sha, path in entries:
            target = scratch / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if kind == "commit":
                shutil.copytree(os.path.join(where.native(top), path), str(target), symlinks=True,
                                ignore=shutil.ignore_patterns(".git"))
            elif mode == "120000":
                _link(blobs[sha], target)
            else:
                target.write_bytes(blobs[sha])
                if mode == "100755":
                    target.chmod(target.stat().st_mode | 0o111)
    except (git.GitError, OSError, KeyError, ValueError) as failure:
        return "the files could not be copied to a scratch folder (%s)" % failure
    return ""


def _blobs(top: str, shas: list[str]) -> dict[str, bytes]:
    """Each blob's bytes, read in one git cat-file --batch."""
    code, data = git.run(top, "cat-file", "--batch", given="".join(sha + "\n" for sha in shas).encode("ascii"))
    if code:
        raise OSError("git cat-file exited %d" % code)
    found, at = {}, 0
    while at < len(data):
        end = data.index(b"\n", at)
        sha, _, size = data[at:end].decode("ascii").split(" ")
        found[sha] = data[end + 1:end + 1 + int(size)]
        at = end + 2 + int(size)
    return found


def _link(text: bytes, target: Path) -> None:
    """A symlink as git holds it; a file holding its target where this system makes none."""
    try:
        os.symlink(text.decode("utf-8", "surrogateescape"), str(target))
    except (OSError, NotImplementedError):
        target.write_bytes(text)


def _undo(run: Path, top: str, task: int, command: str, scratch: Path) -> str:
    """Task <task>'s rounds taken off the copy, newest first, its test files and the test the proof names kept;
    '' when done, else which round would not come off and its files."""
    found = patches.rounds(run, task)
    tests = {path for one in found for path in one.files if patch_checks.TEST_PATH.search(path)}
    tests |= {proof_reach.test_path(top, command)} - {""}
    for one in reversed(found):
        patch = patches.folder(run) / (patches.name(task, one.round) + ".patch")
        if not patch.is_file():
            return "the patch of round %d is not in %s" % (one.round, patches.folder(run).as_posix())
        wrong = patch_apply.undo(scratch, patch, tuple(sorted(tests)), raw=True)
        if wrong:
            return "round %d does not come off the files on disk cleanly: %s" % (one.round, ", ".join(wrong))
    return ""


class Ran(NamedTuple):
    """One run of the after-check's command in the copy: its exit, why it shows nothing ('' when it may count) and
    where its output is kept."""

    code: int
    why: str
    kept: str


def _decided(run: Path, top: str, number: str, command: str, scratch: Path) -> tuple[str, str, str]:
    """The control first: the check must pass in the copy with the change still on, or the copy can't run it.
    Then the task's rounds come off and the rerun decides: it fails (the proof stands) or passes (REVERT-PASSED)."""
    control = _run(run, number, command, scratch, "after-%s-with-change.txt" % number)
    if control.why:
        return _unmade("the check doesn't run in a scratch copy even with the change on — %s (%s)"
                       % (control.why, control.kept))
    if control.code:
        return _unmade("the check doesn't pass in a scratch copy even with the change on (exit %d) — it needs files "
                       "the copy leaves out (%s)" % (control.code, control.kept))
    why = _undo(run, top, int(number), command, scratch)
    if why:
        return _unmade(why)
    rerun = _run(run, number, command, scratch, "after-%s.txt" % number)
    if rerun.why:
        return _unmade("the rerun with task %s's rounds taken off — %s (%s)" % (number, rerun.why, rerun.kept))
    if rerun.code == 0:
        return PASSED, ("revert check: after-%s still passes with task %s's rounds taken off (its tests kept), so the "
                        "test doesn't show the change — make it fail without the change, run before-%s and after-%s "
                        "again, then council check (%s)" % (number, number, number, number, rerun.kept)), ""
    return "ok", ("revert check: passes in a scratch copy with the change on, fails with task %s's rounds taken off "
                  "(exit %d), so the test shows the change (%s)" % (number, rerun.code, rerun.kept)), ""


def _run(run: Path, number: str, command: str, scratch: Path, name: str) -> Ran:
    """The after-check's command, run in the copy under the gate time limit; its output kept in gates/reverted/."""
    out = Path(run) / "gates" / FOLDER / name
    out.parent.mkdir(parents=True, exist_ok=True)
    call = gate_run.Call(Path(run).as_posix(), where.council_home(), str(scratch), True, None, "", False)
    most, _ = gate_run.limit(call, "after-" + number)
    code, timed_out = gate_exec.execute(str(scratch), resolve.field(Path(run), "base"),
                                        gate_run.windows_command(command) if gate_run.WINDOWS_BASH else command,
                                        str(out), most)
    content = gate_output.text(out)
    module = gate_output.missing_module(content) if code == 1 else ""
    why = ("it timed out at %ss" % most if timed_out else
           "the scratch copy could not be entered" if code == gate_exec.NO_ROOT else
           "it never ran: a command it calls was not found (exit 127)" if code == 127 else
           "it never ran: Python has no module %s" % module if module else
           "cmd opened its prompt and ran nothing" if gate_output.never_ran(content) else
           "it ran no test" if check_proofs.nothing_ran(out) and (code == 0 or not gate_output.blank(content)) else "")
    return Ran(code, why, "output: %s" % out.as_posix())


def _remove(scratch: Path) -> None:
    """The scratch folder gone: a read-only file (a copied git object, a checkout on Windows) made writable first."""
    try:
        shutil.rmtree(str(scratch))
    except OSError:
        for folder, _, names in os.walk(str(scratch)):
            for name in names:
                with contextlib.suppress(OSError):
                    os.chmod(os.path.join(folder, name), stat.S_IWRITE)
        shutil.rmtree(str(scratch), ignore_errors=True)
