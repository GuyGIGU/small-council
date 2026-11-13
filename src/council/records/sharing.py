"""The `- sharing:` line of council.config.md (D16): how it reads (the helper's configured_sharing),
whether one is written, and the config with it set (council sharing just-me|team)."""
from __future__ import annotations

import re
from pathlib import Path

from council.records import config


def sharing(home: str | Path) -> str:
    """configured_sharing: 'just me' for just me, just-me or private; 'team' for anything else or none."""
    found = config.first(home, config.SPACE + "*-" + config.SPACE + "*sharing:" + config.SPACE + "*(.*)")
    value = found.group(1).replace("\r", "").translate(config.ASCII_LOWER) if found else ""
    words = ("just me", "just-me", "private")
    if any(value == word or value.startswith(word + " ") for word in words):
        return "just me"
    return "team"


def has_sharing(home: str | Path) -> bool:
    """A `- sharing:` line is written at all (council sharing says whether team is the config's or the default)."""
    return config.first(home, config.SPACE + "*-" + config.SPACE + "*sharing:") is not None


def with_sharing(data: bytes, label: str) -> bytes:
    """The config with `- sharing: <label>` in its own line endings: replaced where the first such line is,
    else added under ## Run preferences, else in a new Run preferences section at the end."""
    cr = b"\r" if b"\r" in data else b""
    records = data.split(b"\n")
    if data.endswith(b"\n") or not data:
        records.pop()
    bare = [line[:-1] if line.endswith(b"\r") else line for line in records]
    has = next((i for i, t in enumerate(bare) if re.match(rb"[ \t]*-[ \t]*sharing:", t)), None)
    head = next((i for i, t in enumerate(bare) if re.fullmatch(rb"##[ \t]+Run preferences[ \t]*", t)), None)
    line = b"- sharing: " + label.encode("utf-8") + cr
    out = []
    for i, record in enumerate(records):
        out.append(line if i == has else record)
        if has is None and i == head:
            out.append(line)
    if has is None and head is None:
        out += [cr, b"## Run preferences" + cr, line]
    return b"".join(record + b"\n" for record in out)
