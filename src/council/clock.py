"""The times council files carry: the helper's UTC event stamps and its local minute and second stamps."""

from datetime import datetime, timezone
import re
from typing import Optional


def event_clock(stamp: str) -> str:
    """An event's UTC time ('2026-09-30T10:14:16Z') as local HH:MM:SS; its own characters 11-19 when it
    does not parse."""
    try:
        moment = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return moment.astimezone().strftime("%H:%M:%S")
    except (ValueError, OverflowError, OSError):
        return stamp[11:19]


def utc_moment(text: Optional[str]) -> Optional[datetime]:
    """The helper's UTC stamp ('2026-09-30T10:14:16Z') as an aware time, or None."""
    try:
        return datetime.strptime((text or "").strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError):
        return None


def iso_moment(value: Optional[str]) -> Optional[datetime]:
    """A UTC ISO time, with or without fractions and a Z or +00:00 (a transcript's ...16.894Z), or None."""
    match = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.\d+)?(?:Z|\+00:00)?$", (value or "").strip())
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def local_moment(text: Optional[str]) -> Optional[datetime]:
    """A helper's local 'YYYY-MM-DD HH:MM[:SS]' stamp as an aware time, or None."""
    text = (text or "").strip()[:19]
    for form in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, form).astimezone()
        except (ValueError, OverflowError, OSError):
            continue
    return None
