"""Times, spans, counts and token figures in plain words, said one way by the status and its card."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from council.records import usage


def iso(moment: datetime | None) -> str | None:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def clock(moment: datetime | None, ref: datetime) -> str:
    """HH:MM on the reference's day, else 'Sep 26 15:49' — both in local time."""
    if not moment:
        return "?"
    local, day = moment.astimezone(), ref.astimezone()
    if local.date() == day.date():
        return local.strftime("%H:%M")
    return "{} {} {}".format(local.strftime("%b"), local.day, local.strftime("%H:%M"))


def span(minutes: float) -> str:
    minutes = max(0, int(minutes))
    if minutes < 1:
        return "under a minute"
    if minutes < 60:
        return "{} min".format(minutes)
    hours, rest = divmod(minutes, 60)
    if hours < 48:
        return "{} h {} min".format(hours, rest) if rest else "{} h".format(hours)
    return "{} days".format(hours // 24)


def tokens_text(value: int | None) -> str:
    """A display form of an exact token count; the stored value is never rounded."""
    if value is None:
        return "unknown"
    return usage.token_text(value)


def cut(text: str, limit: int) -> str:
    """At most limit characters: whole when it fits, else ended on a whole word, then "…" (a single word longer
    than the limit is cut inside it)."""
    if len(text) <= limit:
        return text
    space = text[:limit].rfind(" ")      # a word ending right before it still leaves room for "…"
    return (text[:space] if space > 0 else text[:limit - 1]).rstrip(" ,;:·—-") + "…"


def plural(n: int, one: str, many: str | None = None) -> str:
    return "{} {}".format(n, one if n == 1 else (many or one + "s"))


def listing(names: Iterable[str], limit: int = 4) -> str:
    names = list(names)
    if len(names) <= limit:
        return ", ".join(names)
    return "{} and {} more".format(", ".join(names[:limit]), len(names) - limit)
