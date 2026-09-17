# Stage 6 — Collect

Prove every seat reported before anyone judges.

## Steps

1. **`council collect`** — one row per seat: its file, item count against the cap, size, whether its
   `ref:` lines match its reference docs (proof they were read), whether its citations resolve, and
   the tokens it spent. It also flags a seat whose worker is still running, failed or blocked, an
   index with no items and no `(none)` line, and index lines it can't read. A war room's round-2
   files, named in `debate.md`, are checked the same way.
2. **Fix failing rows.** A row that is only `state:running` isn't failing: that worker is still
   answering, so wait for it. Otherwise, first resume the same worker — SendMessage to its agent id, naming what
   failed. If that isn't possible, re-dispatch it once and record the new agent:
   `council seat <slug> running agent=<new id>` (its earlier tokens are kept). Still failing → tell
   the user which lens is missing. Never judge over a hole.
   - A row whose only flag is `broken-cites` needs neither: the work is there. `council check <seat
     file>` names each bad citation; fix those lines in place.
   - `no-line(N)` and `unchecked(N)` are notes, not failures: N items cite a path with no line, or
     nothing the helper can check (a command, a link, an area).
3. **Coverage.** In-scope files no seat's coverage line mentions, sitting in a hot spot → one bounded
   extra pass by the closest seat. Anything else goes on the deliverable's "not covered" list.

## Partial delivery

The user may say "enough — give me what you have". Then judge what's in, mark the deliverable
**PARTIAL** with the missing seats listed, and record the ruling under Decisions so far.

## Done when

`council collect` is clean, or the user ruled a partial delivery. → `council state phase=judge`
