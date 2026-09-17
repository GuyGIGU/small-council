# Stage 8 — Challenge

Catch what's wrong before the user sees it.

## Steps

1. **Mechanical pre-check.** `council check` reads synthesis.md: every place an item cites exists,
   and each item's origin comes from `git blame` and the change's own hunks against the base —
   introduced, touched (the change edited or removed lines in or next to it) or pre-existing. Write
   each origin into its item. Then, by verdict:
   - `missing-file` or `bad-line`: fix the citation if the intended line is obvious; otherwise drop
     the item.
   - unreadable: rewrite the citation as `path:line`.
   - `deleted`: the change removed that file. The item stands; its lines were checked against the base.
   - `no-line`: the path exists. Add the line when the item is about code.
   - not checked (a command, a link, no path): fine for research evidence or a plan's area; a review
     item needs a `path:line`.
2. **Blind verification.** Dispatch `small-council:council-verifier`:
   - Each **P1**, and each item on a **protected subject** — authorization, data loss, injection,
     secrets, concurrency or ordering, public contracts — gets its own verifier. The rest go in
     batches of up to 8.
   - A verifier gets only the item's synthesis number (1, 2 … or C1 for a cut item), a one-sentence
     claim and its `path:line` — never the seat, principle, reasoning or fix — plus the brief's path
     and the code root. It must trace a live path through the code, and it copies the number into
     its table's `#` column: the ledger matches verdicts to seats by it.
   - Include every cut P1: a lone dissenter may be right.
   - Each verifier writes its own file, `<run>/verify-<n>.md` (n counts verifiers, not items). Track them like workers
     (`council seat verify-<n> running`, then `done tokens=…`).
   - **Over the cap?** P1s and protected items get their own verifiers first; keep one for the
     batch of everything else. If even that doesn't fit, pair P1s two to a verifier. Tell the user
     what shared a verifier.
   - A claim whose evidence is a URL (research) goes to a verifier too; it fetches the page.
   - A war room's agreements are claims too. A post-game's verifiers check its parts against the
     user's request instead — council-postgame says how.
3. **Apply the verdicts** — in the deliverable. Never renumber or delete synthesis.md's lines; the
   ledger counts them at close.
   - CONFIRMED ships.
   - REFUTED drops. Keep it for memory: deliberate design is a candidate accepted pattern.
   - UNCERTAIN ships labelled, and is never dropped if its subject is protected.
   - MISCITED ships with the corrected location.
   - A cut P1 that comes back CONFIRMED is restored.
4. **Every shipped item has a verdict** — check before you move on.
5. **Verification gates**, for modes that changed code: `council gate --all --at verify`.

## Solo runs

Verify yourself, item by item, against the real code, with the same verdicts.

## Done when

Every shipped item has a verdict and the gates are recorded. → `council state phase=deliver`
