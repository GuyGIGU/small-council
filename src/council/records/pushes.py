"""The `- pushes:` line of council.config.md, the push freeze (issue 49): on, off, or off until a date.

There is no bash copy: the bash gate asks `council pushes check`, and the closing card reads it here.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from council.records import config

HELD = "push and PR held by the freeze"
SETTINGS = "on, off or off until <YYYY-MM-DD>"


def pushes(home: str | Path | None, today: date | None = None) -> tuple[str, str]:
    """(held, reading): held is 'push and PR held by the freeze[ until <date>]' while the freeze holds, else '';
    reading is the setting as it is shown. Missing means on; a value it can't read is on too, and `off until` a
    date holds before that date and is on from it; the reading says which."""
    setting = config.folded(home, "pushes")
    dated = re.fullmatch(r"off until ([0-9]{4})-([0-9]{2})-([0-9]{2})", setting)
    try:
        end = date(*(int(part) for part in dated.groups())).isoformat() if dated else ""
    except ValueError:                  # 2026-02-30
        end = ""
    if setting == "off" or end > (today or date.today()).isoformat():
        return HELD + (end and " until " + end), setting + " (config)"
    if setting == "on" or end:
        return "", "on (config{})".format(end and ": the freeze ended " + end)
    if not setting:
        return "", "on (default)"
    return "", "on (default; '{}' is not a setting — {})".format(setting, SETTINGS)
