"""The times council files carry: the helper's UTC event stamps and its local minute and second stamps."""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone


def now_date() -> str:
    return time.strftime("%Y-%m-%d")


def now_min() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


def now_sec() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def utc_moment(text: str | None) -> datetime | None:
    """The helper's UTC stamp ('2026-09-30T10:14:16Z') as an aware time, or None."""
    try:
        return datetime.strptime((text or "").strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError):
        return None


def iso_moment(value: str | None) -> datetime | None:
    """A UTC ISO time, with or without fractions and a Z or +00:00 (a transcript's ...16.894Z), or None."""
    match = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.\d+)?(?:Z|\+00:00)?$", (value or "").strip())
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def local_moment(text: str | None) -> datetime | None:
    """A helper's local 'YYYY-MM-DD HH:MM[:SS]' stamp as an aware time, or None."""
    text = (text or "").strip()[:19]
    for form in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, form).astimezone()
        except (ValueError, OverflowError, OSError):
            continue
    return None
