"""Header fields set as `council state <key>=<value>` sets one that records no event: `council index`'s base= and
`council ask save`'s ask= and ask-saved=, through state_write.change, the one state writer."""
from __future__ import annotations

from pathlib import Path

from council.records.state_write import StateError, change

__all__ = ["StateError", "put", "put_all"]


def put(run: Path, key: str, value: str) -> None:
    """Set the header field key to value. StateError when the run is closed or the state can't be written."""
    put_all(run, [(key, value)])


def put_all(run: Path, fields: list, after_close: bool = False) -> None:
    """Set each header field in turn, in one write. A closed run takes only what change lets it (deliverable=,
    decision=, ask= and ask-saved=), so after_close changes nothing."""
    change(run, ["%s=%s" % pair for pair in fields])
