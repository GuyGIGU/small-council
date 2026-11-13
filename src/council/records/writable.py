"""Whether this session can write into a folder: try to make a file there and remove it. os.access answers
for the file's mode, not for the session, so it lies on Windows and under a sandbox."""
from __future__ import annotations

import contextlib
import errno
import os

DENIED = {errno.EACCES, errno.EPERM, errno.EROFS}


def blocked(folder: str) -> bool:
    """True only when the folder is there and the system says this session may not create a file in it.
    A folder that isn't there, or any other failure of the probe (a full disk, a name clash), is not an answer."""
    probe = "%s/.write-probe-%d-%s" % (folder, os.getpid(), os.urandom(4).hex())
    try:
        handle = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as exc:
        return exc.errno in DENIED and os.path.isdir(folder)
    os.close(handle)
    with contextlib.suppress(OSError):
        os.unlink(probe)                        # made, and so writable; a stray empty file is no harm
    return False
