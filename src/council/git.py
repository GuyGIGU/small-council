"""Running git: `output` for a caller that must stop on a failure, `text` for one that reads a failure as unknown."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


class GitError(RuntimeError):
    """A git command that failed; the message is git's own stderr."""


def output(repo: str | Path, *args: str, allow_error: bool = False) -> bytes:
    """git -C repo <args>'s stdout as bytes; a failure raises GitError unless allow_error."""
    result = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True)
    if result.returncode and not allow_error:
        raise GitError(result.stderr.decode("utf-8", "replace").strip() or "git failed")
    return result.stdout


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


def files_tree(top: str | Path) -> str:
    """The tree id of a working tree's files as they are on disk: committed, staged, unstaged and untracked
    alike (what .gitignore ignores is left out, and so is the council home, .council/, committed or not,
    which the council writes as it works). Taken with `git add -A` into a copy of the index, then
    `git write-tree`, so the real index is never touched; the blobs of changed files land in the object
    store as loose objects, which git's own gc prunes. Two trees with the same files have the same id,
    whatever was committed or staged. '' outside git, or when git fails."""
    import shutil      # only council gate takes a tree: never loaded by the commands that don't (D34)
    import tempfile
    index = text(top, "rev-parse", "--git-path", "index")
    if not index:
        return ""
    real = index if os.path.isabs(index) else os.path.join(str(top), index)
    handle, copy = tempfile.mkstemp(prefix="council-tree-", suffix=".index")
    os.close(handle)
    try:
        if os.path.isfile(real):
            shutil.copy2(real, copy)        # its stat cache and its time: git rechecks an entry as new as the index
        else:
            os.remove(copy)                 # a repo with nothing staged yet: git starts a new index
        given = {"GIT_INDEX_FILE": copy}
        if text(top, "add", "-A", "--", ":(top)", ":(top,exclude).council", extra=given, timeout=600) is None \
                or text(top, "rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", ":(top).council",
                        extra=given) is None:     # committed council files too: a log or memory line is no code
            return ""
        return text(top, "write-tree", extra=given) or ""
    except OSError:
        return ""
    finally:
        for left in (copy, copy + ".lock"):
            if os.path.exists(left):
                os.remove(left)
