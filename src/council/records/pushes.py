"""The `- pushes:` line of council.config.md, the push freeze (issue 49): on, off, or off until a date.

There is no bash copy: the bash gate asks `council pushes check`, and the closing card reads it here. The line is
read as every setting is (config.pref), and the freeze fails safe: a value it can't read holds push and PR.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from council.records import config

HELD = "push and PR held by the freeze"
SETTINGS = "on, off or off until <YYYY-MM-DD>"


def _until(value: str) -> str | None:
    """The date of `off until <YYYY-MM-DD>` (a real date), else None."""
    dated = re.fullmatch(r"off until ([0-9]{4})-([0-9]{2})-([0-9]{2})", value)
    try:
        return date(*(int(part) for part in dated.groups())).isoformat() if dated else None
    except ValueError:                  # 2026-02-30
        return None


def readable(value: str) -> bool:
    """A `- pushes:` value the freeze reads: on, off, or off until a real date (lower case, notes off)."""
    return value in ("on", "off") or _until(value) is not None


def pushes(home: str | Path | None, today: date | None = None) -> tuple[str, str]:
    """(held, reading): held is 'push and PR held by the freeze[ until <date>]' while the freeze holds, else '';
    reading is the setting as it is shown. Missing means on; `off until` a date holds before that date and is on
    from it. A value it can't read holds, as off does, and both name the line: a freeze written a little
    differently must never let a push through."""
    found = config.pref(home, "pushes")
    setting = found.value if found else ""
    end = _until(setting) or ""
    if setting == "off" or end > (today or date.today()).isoformat():
        return HELD + (end and " until " + end), setting + " (config)"
    if setting == "on" or end:
        return "", "on (config{})".format(end and ": the freeze ended " + end)
    if not found:
        return "", "on (default)"
    return (HELD + " — %s line %d isn't %s, so it counts as off" % (config.NAME, found.line, SETTINGS),
            "%s (read as off; '%s' is not a setting — %s)" % (setting, found.said, SETTINGS))
