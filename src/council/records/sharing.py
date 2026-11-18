"""The `- sharing:` line of council.config.md (D16): how it reads, whether one is written, and the config with it
set (council sharing just-me|team)."""
from __future__ import annotations

from pathlib import Path

from council.records import cells, config

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
    else added under ## Run preferences, else in a new Run preferences section at the end."""
    cr = b"\r" if b"\r" in data else b""
    records = data.split(b"\n")
    if data.endswith(b"\n") or not data:
        records.pop()
    bare = [line[:-1] if line.endswith(b"\r") else line for line in records]
    has = next((i for i, t in enumerate(bare) if _key(t) == "sharing"), None)
    head = next((i for i, t in enumerate(bare) if cells.heading(t.decode("latin-1")) == "run preferences"), None)
    line = b"- sharing: " + label.encode("utf-8") + cr
    out = []
    for i, record in enumerate(records):
        out.append(line if i == has else record)
        if has is None and i == head:
            out.append(line)
    if has is None and head is None:
        out += [cr, b"## Run preferences" + cr, line]
    return b"".join(record + b"\n" for record in out)


def _key(line: bytes) -> str:
    """The key of a `- key:` line, as config.pref_of reads it ('' for any other line)."""
    found = config.pref_of(line.decode("latin-1"))
    return found.key if found else ""
