"""The names of the run-folder files that council collect, check and index read or write (architecture §4), held
with the records, as paths.STATE holds session-state.md's, so a command names a council file through one place."""
from __future__ import annotations

BRIEF = "brief.md"            # the seats a run dispatched (collect)
DEBATE = "debate.md"          # a war room's round-2 seats (collect)
SYNTHESIS = "synthesis.md"    # the chair's merged answer (check)
CHECK = "check.md"            # check's table and verdict (check writes it)
INDEX = "index.md"            # the change index (index writes it)
