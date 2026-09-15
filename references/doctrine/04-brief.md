# Stage 4 — Brief

One set of orders that every seat can act on with no other context. Write it to `<run>/brief.md`
with the Write tool. A permission prompt here, before any fan-out, is expected: allow edits under
`.council/` for the session, so the workers can write their files.

## The format — edge-ordered: what matters most goes at the top and the bottom

```
# Brief — <run title>
Deliverable: <the one thing this run produces, and its path>
Intent: <what the author or user is trying to achieve>
Question for every seat: <the one question each seat answers in its lane>
Out of scope: <…>
Code root: <abs> · Council home: <abs> · Run: <abs> · Base: <sha, if there is a diff>

## Landscape
<the system in 2–3 lines, from map.md · the scope with sizes · the change index path ·
 grounding gate results · earlier council findings on these paths, as ids + one line>

## Seats
### <slug> — <what it checks> (<Seat name>)
- ref: <absolute path to the seat's card, else its reference doc, else none; a paired seat has one - ref: line each>
- doc: <absolute path of the full doc behind each card — the worker opens it for the principles it cites>
- out: seats/<slug>.md
- slice: <paths and globs — this seat's only>
- cap: <item cap, default 8> · budget: <~tool calls>
- objective: <this seat's version of the question, in one sentence>
- key questions: <two or three>
- start at: <index entries, surface markers, hot spots>

## Seats not called
- <slug> — <what it checks>: <reason>

## Hard constraints — do not forget
- <the config's hard rules, word for word>
- Settled, never a finding: <the entries `council memory select` printed, one line each>
- Not a finding: <your mode's list, from its `## At Brief`>
- Cite path:line or drop the item. Plain English, no code. Stay in your lane. Read-only.
```

## Rules

- **Write for a worker with zero context.** If a fact isn't in the brief or the worker's reference
  doc, the worker doesn't have it.
- **Keep the seat blocks exact.** `council collect` reads the `### <slug>` headings and their `ref:`,
  `out:` and `cap:` lines. A paired worker gets one block that names both lenses, with one `- ref:`
  line per reference doc; its file must carry one `ref:` line for each.
- **Cards first.** A seat with a card (`<home>/cards/<slug>.md`) gets the card as its `ref:`: its
  principles translated to this project. Its `- doc:` line gives the full doc's absolute path (the
  card's `source:` line names it relative to the plugin or repo), and the worker opens it for the
  principles it cites. A worker that covers several roster seats — a pair, or a split `hunt-a` —
  gets each seat's card and doc.
- **Memory in scope, never the whole file.** Before writing, `council memory select`: with no
  arguments it reads the index and the seats Assign recorded; a run without a diff also passes its
  target paths. Quote what it prints in the bottom block.
- **Hard rules go in word for word** — workers also load the project's CLAUDE.md, but the brief is
  the orders they must not miss.

## Done when

brief.md is written. → `council state phase=work`
