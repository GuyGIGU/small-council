"""The names the status gives seats and checks, so the user reads "Tests", not a slug."""
from __future__ import annotations

import re
from typing import Any

from council.views.snapshot import brief_names


def seat_name(snap: dict[str, Any], slug: str) -> str:
    """A seat in plain words: the brief's name for it, else its slug made readable."""
    named = brief_names(snap).get(slug)
    if named:
        return named
    for prefix, word in (("verify-", "Verifier"), ("diagnose-", "Diagnosis"), ("task-", "Task")):
        if slug.startswith(prefix) and len(slug) > len(prefix):
            return "{} {}".format(word, slug[len(prefix):])
    words = re.sub(r"[-_.]+", " ", slug).strip()
    return words[:1].upper() + words[1:] if words else slug


def check_name(name: str) -> str:
    """A check in plain words: a build's after-check is the fix's check, not a name to decode."""
    if name.startswith("after-") and len(name) > 6:
        return "fix check for task " + name[6:]
    return name
