"""Run folders, and the guarded reads and atomic writes every council file goes through (the council
home itself is found by records/home.py)."""
from __future__ import annotations

import os
import stat
import time
from pathlib import Path
from typing import BinaryIO, Callable, Optional

MAX_FILE = 4 * 1024 * 1024
BOM = chr(0xFEFF)
STATE = "session-state.md"
Reader = Callable[[Path], Optional[str]]   # a caller's own read policy, such as one that refuses


class RecordError(Exception):
    """A council file that cannot be read or written safely; the message names it."""


def is_run(folder: Path, refuse_links: bool = True) -> bool:
    """A run folder: a directory holding session-state.md, and itself no link when refuse_links."""
    folder = Path(folder)
    if refuse_links and linked(folder):
        return False
    return folder.is_dir() and (folder / STATE).is_file()


# --- reading without getting in a live run's way ----------------------------------------------------------
def linked(path: str | Path) -> bool:
    """True when path itself is a symlink or a Windows junction (its parent may be linked; that is fine)."""
    path = Path(path)
    try:
        return path.is_symlink() or os.path.normcase(os.path.realpath(str(path))) != os.path.normcase(
            os.path.join(os.path.realpath(str(path.parent)), path.name))
    except (OSError, ValueError):
        return True


def contained(path: str | Path, root: str | Path) -> bool:
    """True when path, links and junctions resolved, stays inside root, also resolved."""
    try:
        real, base = os.path.realpath(str(path)), os.path.realpath(str(root))
    except (OSError, ValueError):
        return False
    return real == base or real.startswith(base.rstrip("\\/") + os.sep)


def open_shared(path: str | Path) -> BinaryIO | None:
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


def read_bytes(path: str | Path, limit: int) -> bytes:
    """Up to limit + 1 bytes of the file (one more than allowed, so a caller can tell it is too large)."""
    shared = open_shared(path)
    with shared if shared is not None else open(str(path), "rb") as handle:
        return handle.read(limit + 1)


def contents(path: str | Path) -> bytes | None:
    """The whole file's bytes, None when it can't be read; unguarded (read_bytes and text_of are the guarded reads)."""
    try:
        with open(str(path), "rb") as handle:
            return handle.read()
    except OSError:
        return None


def text_of(path: str | Path, root: str | Path | None = None, limit: int = MAX_FILE,
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


def run_text(run: Path, name: str, read: Reader | None = None, limit: int = MAX_FILE) -> str:
    """A run file's text by the guarded read (a link, a file outside the run, one over limit or a missing
    one reads as ''), unless `read` gives a caller's own policy."""
    file = Path(run) / name
    return text_of(file, run, limit) if read is None else read(file) or ""


def too_large(path: str | Path, limit: int = MAX_FILE) -> bool:
    try:
        return Path(path).is_file() and Path(path).stat().st_size > limit
    except OSError:
        return False


def megabytes(limit: int) -> str:
    """A byte limit as the refusals say it: '1 MB', '4 MB'."""
    return "{} MB".format(limit // (1024 * 1024))


def artifact(path: Path, limit: int, required: bool = True) -> bytes | None:
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


# --- writing ----------------------------------------------------------------------------------------------
def current_umask() -> int:
    """This process's umask (read by setting it and putting it back)."""
    mask = os.umask(0)
    os.umask(mask)
    return mask


def append_row(file: Path, head: str, cells: tuple[str, ...]) -> None:
    """One TSV row: the head first in a new or empty file, never joined to a torn last line. OSError."""
    old = file.read_bytes() if file.is_file() else b""
    lead = "" if old.endswith(b"\n") else "\n" if old else head
    with open(str(file), "ab") as out:
        out.write((lead + "\t".join(cells) + "\n").encode("utf-8", "surrogateescape"))


def swap_in(temporary: str | Path, path: str | Path) -> None:
    """Move temporary over path as mv did; Windows refuses while a reader has path open, so try again for ~1 s."""
    for wait in (0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.3, 0):
        try:
            os.replace(str(temporary), str(path))
            return
        except PermissionError:
            if not wait:
                raise
            time.sleep(wait)


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
    import tempfile   # here, not at the top: only a command that writes pays for it
    fd, temporary = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        if mode is not None:
            os.chmod(temporary, mode)
        swap_in(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
