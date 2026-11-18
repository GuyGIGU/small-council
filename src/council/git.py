"""Running git: `output` for a caller that must stop on a failure, `text` for one that reads a failure as unknown,
`run` for one that reads the exit code itself."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


class GitError(RuntimeError):
    """A git command that failed; the message is git's own stderr."""


def output(repo: str | Path, *args: str, allow_error: bool = False, extra: dict[str, str] | None = None) -> bytes:
    """git -C repo <args>'s stdout as bytes, with `extra` added to its environment; a failure raises GitError
    unless allow_error."""
    env = dict(os.environ, **extra) if extra else None
    result = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, env=env)
    if result.returncode and not allow_error:
        raise GitError(result.stderr.decode("utf-8", "replace").strip() or "git failed")
    return result.stdout


def run(repo: str | Path, *args: str, given: bytes = b"", names: bool = False,
        extra: dict[str, str] | None = None) -> tuple[int, bytes]:
    """git -C repo <args>'s exit code and stdout, its stderr dropped, `given` its only input and `extra` added to its
    environment; with names, a path is printed as it is (core.quotePath off). 127 and b'' when git can't start."""
    quote = ["-c", "core.quotePath=false"] if names else []
    env = dict(os.environ, **extra) if extra else None
    try:
        done = subprocess.run(["git", "-C", str(repo)] + quote + list(args), input=given, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, env=env)
    except OSError:
        return 127, b""
    return done.returncode, done.stdout


def text(repo: str | Path, *args: str, extra: dict[str, str] | None = None, timeout: int = 20) -> str | None:
    """git -C repo <args>'s stdout as stripped text, or None when git fails, is missing or takes over 20 s
    (or the timeout given). It takes no optional lock, so a reader never blocks the user's own git."""
    try:
        env = os.environ.copy()
        env["GIT_OPTIONAL_LOCKS"] = "0"
        env.update(extra or {})
        # A diff carries the project's own bytes, which the locale's code page may not decode; only
        # git's ASCII headers are parsed, so an undecodable byte is replaced rather than fatal.
        result = subprocess.run(["git", "-C", str(repo)] + list(args), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, encoding="utf-8", errors="replace", timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


# Python's bytecode, which running a project's tests writes beside its code: never a change, ignored or not. The add
# skips it, so an untracked one never enters the tree and a committed one stays as committed.
CACHES = (":(top,exclude,glob)**/__pycache__/**", ":(top,exclude,glob)**/*.py[co]")


def between(*under: str) -> tuple[str, ...]:
    """What follows a diff of two trees (files_tree's ids, a round's or a commit's): `--`, the pathspecs named (else
    the whole tree), then the council home and CACHES left out on both sides. A round saved by a helper from before
    CACHES (#121) kept the bytecode in its tree, so without it every cache read as deleted. Every comparison of two
    trees ends with it."""
    return ("--",) + (under or (":(top)",)) + (":(top,exclude).council",) + CACHES


def files_tree(top: str | Path) -> str:
    """The tree id of a working tree's files as they are on disk: committed, staged, unstaged and untracked
    alike (what .gitignore ignores is left out, and so is the council home, .council/, committed or not,
    which the council writes as it works, and Python's bytecode, CACHES). Taken with `git add -A` into a copy of
    the index, then `git write-tree`, so the real index is never touched; the blobs of changed files land in the object
    store as loose objects, which git's own gc prunes. Two trees with the same files have the same id,
    whatever was committed or staged. '' outside git, or when git fails."""
    import shutil      # only council gate takes a tree: never loaded by the commands that don't (D34)
    import tempfile
    index = text(top, "rev-parse", "--git-path", "index")
    if not index:
        return ""
    real = os.path.join(str(top), index)              # git prints it relative to top, or whole: join keeps a whole one
    handle, copy = tempfile.mkstemp(prefix="council-tree-", suffix=".index")
    os.close(handle)
    try:
        if os.path.isfile(real):
            shutil.copy2(real, copy)        # its stat cache and its time: git rechecks an entry as new as the index
        else:
            os.remove(copy)                 # a repo with nothing staged yet: git starts a new index
        given = {"GIT_INDEX_FILE": copy}
        # No exclude pathspec for .council on the add: on a just-me council .council/ is in .git/info/exclude, and
        # git add exits 1 on a pathspec that names an ignored path. The rm that follows takes the council files out
        # (committed ones too: a log or memory line is no code), so the tree is the same either way.
        if text(top, "add", "-A", "--", ":(top)", *CACHES, extra=given, timeout=600) is None \
                or text(top, "rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", ":(top).council",
                        extra=given) is None:
            return ""
        return text(top, "write-tree", extra=given) or ""
    except OSError:
        return ""
    finally:
        for left in (copy, copy + ".lock"):
            if os.path.exists(left):
                os.remove(left)


# The bytes on disk, as a gate reads them: no line-end conversion (core.autocrlf, core.eol) and no attribute (a
# .gitattributes text, eol or filter rule), so a CRLF-only edit is a change. fsmonitor and ignoreStat off: every file's
# own stat decides whether it is read again.
RAW = ("-c", "core.autocrlf=false", "-c", "core.eol=lf", "-c", "core.safecrlf=false", "-c", "core.fsmonitor=false",
       "-c", "core.ignoreStat=false")
EMPTY = {"sha1": "4b825dc642cb6eb9a060e54bf8d69288fbee4904",       # the empty tree: --attr-source reads no rule from it
         "sha256": "6ef19b41225c5369f1c104d45d8d85efa9b057b53b14b4b9b939dd74decc5321"}


def disk_tree(top: str | Path) -> str:
    """The tree id of the files a gate reads, byte for byte: files_tree's files (ignored ones, .council/ and CACHES
    left out; a file git tracks that an ignore rule names kept), each as its bytes on disk, with no line-end
    conversion or .gitattributes rule applied. Taken with `git add -A` into an index of the council's own in the
    worktree's git folder (council-disk.index), which starts empty, so its stat cache is of the raw bytes: only a file
    whose stat changed is read again, and the first call reads every file once. '' outside git, when git fails or is
    older than 2.40 (no --attr-source), when .git/info/attributes holds a rule it can't turn off, or when a submodule
    has modified or untracked files (its files are no blob in the tree): a gate with no tree always runs."""
    import shutil      # only council gate and council check take a tree: never loaded by the commands that don't (D34)
    import tempfile
    said = (text(top, "rev-parse", "--absolute-git-dir", "--git-path", "info/attributes", "--show-object-format")
            or "").splitlines()
    if len(said) != 3 or said[2] not in EMPTY or _rules(os.path.join(str(top), said[1])):
        return ""
    kept = os.path.join(said[0], "council-disk.index")
    try:
        handle, copy = tempfile.mkstemp(prefix="council-disk-", suffix=".index", dir=said[0])
        os.close(handle)
    except OSError:
        return ""
    try:
        if os.path.isfile(kept):
            shutil.copy2(kept, copy)        # its stat cache and its time: git rechecks an entry as new as the index
        else:
            os.remove(copy)                 # the first call: every file read once
        tree = _raw_tree(top, copy, EMPTY[said[2]], os.path.join(said[0], "council-no-attributes"))
        if tree:
            os.replace(copy, kept)
        return tree
    except OSError:
        return ""
    finally:
        for left in (copy, copy + ".lock"):
            if os.path.exists(left):
                os.remove(left)


def _rules(path: str) -> bool:
    """Whether .git/info/attributes holds a rule: --attr-source turns off only the worktree's .gitattributes."""
    try:
        with open(path, "rb") as held:
            return any(line.strip() and not line.lstrip().startswith(b"#") for line in held)
    except OSError:
        return False


def _raw_tree(top: str | Path, index: str, empty: str, nothing: str) -> str:
    """add -A of the files as their bytes into index (the council home left out, and so is a tracked file an
    ignore rule names only when it is the home's), then write-tree; '' on a fault or a dirty submodule."""
    given = {"GIT_INDEX_FILE": index}
    raw = RAW + ("-c", "core.attributesFile=" + nothing, "--attr-source=" + empty)
    home = text(top, "check-ignore", "-q", "--no-index", "--", ".council") is None    # not ignored: leave it out here
    if text(top, *raw, "add", "-A", "--", ":(top)", *((":(top,exclude).council",) if home else ()), *CACHES,
            extra=given, timeout=600) is None:
        return ""
    code, forced = run(top, "ls-files", "-z", "--cached", "--ignored", "--exclude-standard", "--", ":(top)",
                       ":(top,exclude).council", *CACHES)
    if code or (forced and run(top, *raw, "add", "-f", "--pathspec-from-file=-", "--pathspec-file-nul",
                               given=forced, extra=given)[0]):
        return ""
    tree = text(top, *raw, "write-tree", extra=given) or ""
    return tree if tree and not _dirty_submodule(top, index) else ""


def _dirty_submodule(top: str | Path, index: str) -> bool:
    """A submodule (any gitlink in the tree) with modified or untracked files: git status's S.M. or S..U."""
    code, listed = run(top, "ls-files", "-s", "-z", extra={"GIT_INDEX_FILE": index})
    links = [entry.split(b"\t", 1)[1].decode("utf-8", "surrogateescape") for entry in listed.split(b"\0")
             if entry.startswith(b"160000 ")]
    if code or not links:
        return bool(code)
    code, said = run(top, "status", "--porcelain=v2", "-z", "--ignore-submodules=none", "--", *links,
                     extra={"GIT_OPTIONAL_LOCKS": "0"})
    states = [entry.split(b" ")[2] for entry in said.split(b"\0") if entry[:2] in (b"1 ", b"2 ")]
    return bool(code) or any(state.startswith(b"S") and (b"M" in state[2:] or b"U" in state[2:]) for state in states)


def unchanged_under(top: str | Path, old: str, new: str, pathspecs: tuple[str, ...]) -> bool:
    """Whether no file under these git pathspecs (relative to top) differs between two trees (files_tree's ids).
    Renames read as a delete and an add, so a file moved out from under them counts as a change. False when git
    can't read a tree (pruned, or never in this object store) or a pathspec: a fault is never 'unchanged'."""
    if not old or not new or not pathspecs:
        return False
    changed = text(top, "diff", "--no-ext-diff", "--no-renames", "--name-only", old, new, *between(*pathspecs),
                   timeout=120)
    return changed == ""


def unmatched(top: str | Path, pathspecs: tuple[str, ...]) -> list[str]:
    """The pathspecs that match no file under top (tracked, or untracked and not ignored): nothing under one ever
    changes, so a gate covering it is never taken on it (gate_reuse), and council doctor names it. A pathspec git
    can't read counts as matching nothing."""
    return [path for path in pathspecs
            if not text(top, "ls-files", "--cached", "--others", "--exclude-standard", "--", path, timeout=60)]
