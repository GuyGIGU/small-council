"""The council home, run folders, and the guarded reads and atomic writes every council file goes through."""

import os
from pathlib import Path
import stat
import tempfile
from typing import BinaryIO, Callable, List, Optional, Union

from council import git

MAX_FILE = 4 * 1024 * 1024
BOM = chr(0xFEFF)
STATE = "session-state.md"


class RecordError(Exception):
    """A council file that cannot be read or written safely; the message names it."""


# --- where the council lives -----------------------------------------------------------------------------
def worktrees(porcelain: str) -> List[str]:
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


def council_home(cwd: Union[str, Path]) -> Path:
    """The .council/ of the main checkout, shared by every linked worktree; ./.council outside git."""
    top = git.text(cwd, "rev-parse", "--show-toplevel")
    if not top:
        return Path(os.path.abspath(str(cwd))) / ".council"
    superproject = git.text(cwd, "rev-parse", "--show-superproject-working-tree") or ""
    porcelain = git.text(cwd, "worktree", "list", "--porcelain") or ""
    return Path(home_from(top, superproject, porcelain, os.path.exists))


def home_of(run: Path) -> Optional[Path]:
    """The council home a run folder sits in (<home>/runs/<run>), or None for a run kept elsewhere."""
    run = Path(run)
    return run.parent.parent if run.parent.name == "runs" else None


def is_run(folder: Path, refuse_links: bool = True) -> bool:
    """A run folder: a directory holding session-state.md, and itself no link when refuse_links."""
    folder = Path(folder)
    if refuse_links and linked(folder):
        return False
    return folder.is_dir() and (folder / STATE).is_file()


def run_folders(home: Path, newest: Optional[int] = None, require_state: bool = True) -> List[Path]:
    """The run folders under <home>/runs, oldest first by name, links left out; the newest N when given.
    With require_state, a folder without session-state.md is no run and is not counted."""
    runs = Path(home) / "runs"
    if not runs.is_dir() or linked(runs):
        return []
    found = [p for p in runs.iterdir() if p.is_dir() and not linked(p)
             and (not require_state or (p / STATE).is_file())]
    found.sort(key=lambda p: p.name)
    return found[-newest:] if newest else found


# --- reading without getting in a live run's way ----------------------------------------------------------
def linked(path: Union[str, Path]) -> bool:
    """True when path itself is a symlink or a Windows junction (its parent may be linked; that is fine)."""
    path = Path(path)
    try:
        return path.is_symlink() or os.path.realpath(str(path)) != os.path.join(os.path.realpath(str(path.parent)), path.name)
    except (OSError, ValueError):
        return True


def contained(path: Union[str, Path], root: Union[str, Path]) -> bool:
    """True when path, links and junctions resolved, stays inside root, also resolved."""
    try:
        real, base = os.path.realpath(str(path)), os.path.realpath(str(root))
    except (OSError, ValueError):
        return False
    return real == base or real.startswith(base.rstrip("\\/") + os.sep)


def open_shared(path: Union[str, Path]) -> Optional[BinaryIO]:
    """On Windows, the file opened with read, write and delete sharing, so the helper's rename of a file
    being read still succeeds. None where that is not available."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        import msvcrt
        from ctypes import wintypes
    except ImportError:
        return None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.restype = wintypes.HANDLE
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    # GENERIC_READ; FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE; OPEN_EXISTING; FILE_ATTRIBUTE_NORMAL
    handle = create(str(path), 0x80000000, 0x7, None, 3, 0x80, None)
    if handle is None or handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), "cannot open", str(path))
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    except OSError:
        kernel.CloseHandle(wintypes.HANDLE(handle))
        raise
    return os.fdopen(descriptor, "rb")


def read_bytes(path: Union[str, Path], limit: int) -> bytes:
    """Up to limit + 1 bytes of the file (one more than allowed, so a caller can tell it is too large)."""
    handle = open_shared(path) or open(str(path), "rb")
    with handle:
        return handle.read(limit + 1)


def text_of(path: Union[str, Path], root: Optional[Union[str, Path]] = None, limit: int = MAX_FILE,
            errors: str = "replace") -> str:
    """A small regular file's text, BOM dropped, or '' when it is missing, a link, outside root, too
    large or unreadable (or, with errors='strict', not UTF-8)."""
    path = Path(path)
    try:
        if linked(path) or not path.is_file() or (root is not None and not contained(path, root)):
            return ""
        data = read_bytes(path, limit)
    except OSError:
        return ""
    if len(data) > limit:
        return ""
    try:
        return data.decode("utf-8", errors=errors).lstrip(BOM)
    except UnicodeError:
        return ""


def too_large(path: Union[str, Path], limit: int = MAX_FILE) -> bool:
    """True when path is a file over limit bytes."""
    try:
        return Path(path).is_file() and Path(path).stat().st_size > limit
    except OSError:
        return False


def megabytes(limit: int) -> str:
    """A byte limit as the refusals say it: '1 MB', '4 MB'."""
    return "{} MB".format(limit // (1024 * 1024))


def artifact(path: Path, limit: int, required: bool = True) -> Optional[bytes]:
    """A run artifact's bytes, refusing a link (the file or its folder), a non-regular file and one over
    limit; None when it is missing and not required."""
    path = Path(path)
    if path.is_symlink() or path.parent.is_symlink():
        raise RecordError("symlink artifact is not allowed: " + str(path))
    if not path.exists():
        if required:
            raise RecordError("missing artifact: " + str(path))
        return None
    if not path.is_file() or path.stat().st_size > limit:
        raise RecordError("artifact is not a regular file under {}: {}".format(megabytes(limit), path))
    return path.read_bytes()


def universal(text: str) -> str:
    """Text with every line ending made a newline, as Python's text mode reads a file."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


# --- writing ----------------------------------------------------------------------------------------------
def current_umask() -> int:
    """This process's umask (read by setting it and putting it back)."""
    mask = os.umask(0)
    os.umask(mask)
    return mask


def atomic_write(path: Path, data: bytes, prefix: str, suffix: str = "", keep_mode: bool = False,
                 refuse_link: bool = False) -> None:
    """Replace path with data through a temporary file beside it, so no reader sees half a file.
    keep_mode keeps the file's permissions (a new file gets the usual ones); otherwise the file has the
    temporary file's own (owner only). refuse_link refuses to write through a link."""
    path = Path(path)
    if refuse_link and path.is_symlink():
        raise RecordError("symlink output is not allowed: " + str(path))
    mode = None
    if keep_mode:
        mode = stat.S_IMODE(os.stat(str(path)).st_mode) if path.exists() else 0o666 & ~current_umask()
    fd, temporary = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
