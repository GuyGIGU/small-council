"""Where the council lives: the council home (the helper's council_home), the folder a command runs in
(here), the working tree runs are compared with (this_tree), and a path argument as Python opens it."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

from council import git


def worktrees(porcelain: str) -> list[str]:
    """Every non-bare worktree of `git worktree list --porcelain`, the main one first, with "(bare)"
    first when the repository itself is bare (the helper's council_home reads it so)."""
    found, current, bare, count = [], "", False, 0
    for line in porcelain.split("\n"):
        if line.startswith("worktree "):
            if current and not bare:
                found.append(current)
            current, bare, count = line[len("worktree "):], False, count + 1
        elif line == "bare":
            bare = True
            if count == 1:
                found.append("(bare)")
    if current and not bare:
        found.append(current)
    return found


def home_from(top: str, superproject: str, porcelain: str, exists: Callable[[str], bool]) -> str:
    """The council home's path from git's answers, as the helper's council_home picks it. `exists`
    says whether a path is there (a folder or a file; the names make clear which is asked)."""
    if superproject:
        return top + "/.council"
    listed = worktrees(porcelain)
    main = listed[0] if listed else ""
    if main == "(bare)":
        trees = [tree for tree in listed if tree and tree != "(bare)"]
        configured = next((tree for tree in trees if exists(tree + "/.council/council.config.md")), "")
        main = configured or next((tree for tree in trees if exists(tree + "/.council")), "")
    main = main or top
    if not exists(main + "/.council") and exists(top + "/.council"):
        main = top                                   # a 0.1 council inside a worktree
    return main + "/.council"


def council_home(cwd: str | Path = ".") -> str:
    """The .council/ of the main checkout, shared by every linked worktree; ./.council outside git. The
    path is written as the helper prints it (git's form: C:/… with / on Windows)."""
    top = git.text(cwd, "rev-parse", "--show-toplevel")
    if not top:
        return here(cwd) + "/.council"
    superproject = git.text(cwd, "rev-parse", "--show-superproject-working-tree") or ""
    porcelain = git.text(cwd, "worktree", "list", "--porcelain") or ""
    return home_from(top, superproject, porcelain, os.path.exists)


def here(cwd: str | Path = ".") -> str:
    """A folder as the helper's here() prints it: on Windows its full path with / (pwd -W); elsewhere
    $PWD when it names the folder, as bash's pwd keeps the path it was reached by, else the real path."""
    folder = os.path.abspath(str(cwd))
    if os.name == "nt":
        return folder.replace("\\", "/")
    logical = os.environ.get("PWD", "")
    if str(cwd) == "." and logical.startswith("/") and not {".", ".."} & set(logical.split("/")):
        try:
            if os.path.samefile(logical, folder):
                return logical
        except OSError:
            pass
    return folder


def this_tree(cwd: str | Path = ".") -> str:
    """The working tree a run's code-root is compared with: git's top level, else the folder itself."""
    return git.text(cwd, "rev-parse", "--show-toplevel") or here(cwd)


def native(value: str) -> str:
    """A path from the command line as this Python can open it. bin/council hands arguments over as
    typed (Git Bash would rewrite free text that looks like a path), so on Windows an MSYS path such as
    /c/Users/… is turned into C:/Users/… here, and another MSYS path (/tmp/…) by cygpath when it is there."""
    if os.name != "nt" or not value.startswith("/") or value.startswith("//"):
        return value
    if len(value) >= 2 and value[1].isalpha() and (len(value) == 2 or value[2] == "/"):
        return value[1].upper() + ":" + (value[2:] or "/")
    try:
        found = subprocess.run(["cygpath", "-m", value], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return value
    return found.stdout.strip() if found.returncode == 0 and found.stdout.strip() else value
