"""The agent gate's writability check (issue 51): a Small Council agent works from a brief and writes its
output under the council home, so one sent while this session can't write there would run with no brief.
That is refused before anything else is judged, naming the folder and the next step."""
from __future__ import annotations

from council.commands import resolve
from council.records import writable


def refusal(kind: str | None, home: str, run: str) -> str | None:
    """The reason a council-worker or council-verifier (kind) can't go out: the council home, or the run
    folder the dispatch names, is not writable from this session. None for any other agent (kind is None)."""
    if kind is None:
        return None
    folders = [("the council folder", home)]
    named = home + "/runs/" + run
    if run and "/" not in run and not run.startswith(".") and resolve.is_run(named):
        folders.append(("the run folder", named))
    for what, folder in folders:
        if writable.blocked(folder):
            return ("Small Council: %s %s is not writable from this session, so this %s could not write its output "
                    "there and would work with no brief or record. Open the session in the main checkout (the "
                    "folder that holds .council/), or fix the folder's permissions, then dispatch again."
                    % (what, folder, kind))
    return None
