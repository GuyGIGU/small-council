# Stage 7 — Judge

Your judgment, written down.

## Steps

1. **Raw ledger first.** From every seat file's `## Index`, list every raw item — before merging
   anything and before re-reading any source. Open an item's full text only when you need it to
   judge that item.
2. **Merge** by owner (your mode's owner rules) and by root cause. Keep every author:
   "from hunt#3, collina#1".
3. **Conflict pass.** List the pairs that contradict each other or rest on incompatible "Assumes"
   lines. Settle what the code settles; the rest become rulings for the user. After a war room, each
   point's line records how it ended — agreed, settled by the code, to the verifier, or FORK — and
   `from:` names round-1 items only.
4. **Rank by concrete cost in this project at this scale** — the Carmack filter: a real problem
   here, or pattern-matching? Still-applicable settled memory entries are never findings.
5. **Cut to your mode's cap.** Keep the cut list, with a reason for each item.
6. **Write `<run>/synthesis.md`** in the format below. In review, plan and research, every kept
   and cut claim carries a declared `state:` and `from:` as specified in
   `references/evidence-model.md`; a `REPRODUCED` claim also names saved `proof:`. Do not upgrade
   an inference to observation because several seats agreed. Post-game keeps its request-quote
   format instead. Everything after this stage reads the file, not your memory of it.
7. **For review, plan and research, build the provisional claim index** with
   `council evidence build` when Python 3.8+ is available. Missing verifier links at this stage
   are expected, never a pass.

## synthesis.md

```
# Synthesis — <run title>
## Kept
1 · P1 · <principle> · <path:line> · <title> · state: OBSERVED · from: hunt#3, collina#1
2 · …
## Cut
C1 · P2 · <principle> · <path:line> · <title> · why: <reason> · state: INFERRED · from: leach#2
## Conflicts
- hunt#2 vs fowler#4: <one line> → <how it was settled | RULING NEEDED>
## Rulings needed
1. <question> — <the options> — <why it matters>
## Not covered
- <in-scope files or lenses nobody covered, and why>
```

Kept and cut lines use the index-line format, so `council check` can read them: one line per item,
no tables and no headings. With nothing kept, write `(none) — <why>` under `## Kept`.

## Done when

synthesis.md is on disk. → `council state phase=challenge`
