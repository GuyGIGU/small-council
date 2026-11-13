"""One run-audit item for scripts/audit.py: every seat that was an agent run has a token figure.

Graded FAIL, as the audit grades the other gaps in a run's own record (a seat never recorded, an agent
recorded only when it finished): the Chair left the run total, the ledger and council tune short, and it can
put the figure right with council correct.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from council.records import usage, usage_gaps  # noqa: E402
from council.records.audit_file import FAIL, PASS  # noqa: E402


def token_figures(run, say):
    label = "Token figures"
    if run.status != "complete":
        say(PASS, label, "not checked: the run did not complete")
        return
    gaps = usage_gaps.unfigured(usage.seat_list(run.folder), skip=usage_gaps.chairs(run.roles))
    if not gaps:
        say(PASS, label, "every agent run's tokens are on record")
        return
    fix = 'council correct <seat> tokens=<exact> agents=<exact> evidence="<source>" --run ' + run.name
    lead = "%d seat(s) ran as agents with no token figure, so the run total, the ledger and council tune leave them out"
    say(FAIL, label, "%s: %s; put one right with %s" % (lead % len(gaps), usage_gaps.words(gaps), fix))
