# Finding outcomes

`council outcomes [--json]` compares file citations in closed runs' `claims.jsonl` with commits made
after the run closed. It groups the five outcomes by run, mode and originating seat, and shows Cut
claims separately as a comparison group. `council history` includes the number of Kept and Cut
citations whose cited lines changed.

The comparison is deliberately conservative. A run needs a close timestamp and a recorded Git base
that matches the commit at close. Missing or unreadable claims, missing Git history, an invalid
citation, or a baseline mismatch becomes `can't tell`. A cited file deleted or renamed after close
is `file gone or renamed`. A diff hunk overlapping the citation's original line span is `changed at
cited lines`; a change elsewhere in that file is `file changed elsewhere`; no diff is `unchanged`.

These are timing observations. A line changing after a run does not prove the council found the issue,
that the finding caused the change, or that the change was correct. The comparison is especially weak
when Kept and Cut lines change at similar rates. Uncommitted changes at the time of the review cannot
be reconstructed from Git history; use the result as a conservative record of committed changes only.
The command reads run records and Git history and writes nothing.
