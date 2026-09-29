# Finding outcomes

`council outcomes [--json]` compares file citations in closed runs' `claims.jsonl` with commits made
after the run closed. It groups the five outcomes by run, mode and originating seat, and shows Cut
claims separately as a comparison group. `council history` includes the number of Kept and Cut
citations whose cited lines changed.

The comparison is deliberately conservative. It uses each run's recorded `code-root:` repository,
then finds its latest commit at or before the run's `closed:` time. An unavailable recorded code root
is `can't tell`; older runs without one use the caller's repository. `base:` is the change index's
merge-base and does not need to match the close-time commit. If
the saved `index.md` records `+ uncommitted changes`, the run's claims become `can't tell`. Missing
or unreadable claims, missing Git history, or an invalid citation also becomes `can't tell`. A cited
file deleted or renamed after close is `file gone or renamed`. A diff hunk overlapping the citation's
original line span is `changed at cited lines`; a change elsewhere in that file is `file changed
elsewhere`; no diff is `unchanged`.

These are timing observations. A line changing after a run does not prove the council found the issue,
that the finding caused the change, or that the change was correct. The comparison is especially weak
when Kept and Cut lines change at similar rates. The saved index can identify a dirty tree when it was
created; Git cannot reconstruct later uncommitted edits at review time if the index did not record
them. Treat results as a comparison of committed snapshots, not proof of causation or correctness.
The command reads run records and Git history and writes nothing.
