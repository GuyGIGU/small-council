# Stage 7 — Judge

Your judgment, written down.

## Steps

1. **Raw ledger first.** From every seat file's `## Index`, list every raw item — before merging
   anything and before re-reading any source. Open an item's full text only to judge that item.
2. **Merge** by owner (your mode's owner rules) and by root cause. Keep every author:
   "from hunt#3, collina#1".
3. **Conflict pass.** List the pairs that contradict each other or rest on incompatible "Assumes"
   lines. Settle what the code settles; the rest become rulings for the user.
4. **Rank by concrete cost in this project at this scale** — the Carmack filter: a real problem
   here, or pattern-matching? Still-applicable settled memory entries are never findings.
5. **Cut to your mode's cap.** Keep the cut list, with a reason for each item.
6. **Write `<run>/synthesis.md`** in the format below. In review, plan and research, every kept
   and cut claim carries a declared `state:` and `from:` (`references/run/evidence-model.md`); a
   `REPRODUCED` claim also names saved `proof:`. Several seats agreeing never upgrades an inference
   to an observation. Everything after this stage reads the file, not your memory of it.

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
no tables and no headings. With nothing kept, write `(none) — <why>` under `## Kept`. `from:` names
seat items (`hunt#3`); a Solo run writes `from: chair`, and a grounding-gate finding `from: gate:<name>`.

## Done when

synthesis.md is on disk. → `council state phase=challenge`
