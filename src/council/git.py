"""Running git: `output` for a caller that must stop on a failure, `text` for one that reads a failure as unknown."""

import os
import subprocess
from pathlib import Path
from typing import Optional, Union


class GitError(RuntimeError):
    """A git command that failed; the message is git's own stderr."""


def output(repo: Union[str, Path], *args: str, allow_error: bool = False) -> bytes:
    """git -C repo <args>'s stdout as bytes; a failure raises GitError unless allow_error."""
    result = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True)
    if result.returncode and not allow_error:
        raise GitError(result.stderr.decode("utf-8", "replace").strip() or "git failed")
    return result.stdout


def text(repo: Union[str, Path], *args: str) -> Optional[str]:
    """git -C repo <args>'s stdout as stripped text, or None when git fails, is missing or takes over 20 s.
    It takes no optional lock, so a reader never blocks the user's own git."""
    try:
        env = os.environ.copy()
        env["GIT_OPTIONAL_LOCKS"] = "0"
        # A diff carries the project's own bytes, which the locale's code page may not decode; only
        # git's ASCII headers are parsed, so an undecodable byte is replaced rather than fatal.
        result = subprocess.run(["git", "-C", str(repo)] + list(args), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, encoding="utf-8", errors="replace", timeout=20, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None
