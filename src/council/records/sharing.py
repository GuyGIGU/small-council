"""The `- sharing:` line of council.config.md (D16): how it reads, whether one is written, and the config with it
set (council sharing just-me|team)."""
from __future__ import annotations

from pathlib import Path

from council.records import config

JUST_ME = ("just me", "just-me", "private")


def word(value: str) -> str:
    """'just me' for just me, just-me or private (words may follow them); 'team' for team; '' for anything else."""
    if any(value == said or value.startswith(said + " ") for said in JUST_ME):
        return "just me"
    return "team" if value == "team" else ""


def sharing(home: str | Path) -> str:
    """'just me' or 'team' from the `- sharing:` line (config.pref); team with no line, or (said once on stderr)
    with a value it can't read."""
    found = config.pref(home, "sharing")
    said = word(found.value) if found else ""
    if found and not said:
        config.unread(found, "team")
    return said or "team"


def has_sharing(home: str | Path) -> bool:
    """A `- sharing:` line is written at all (council sharing says whether team is the config's or the default)."""
    return config.pref(home, "sharing", empty=True) is not None


def with_sharing(data: bytes, label: str) -> bytes:
    """The config with `- sharing: <label>` in its own line endings: replaced where the first such line is,
    else added right under ## Run preferences, else in a new Run preferences section at the end (config.with_pref)."""
    return config.with_pref(data, "sharing", label)
