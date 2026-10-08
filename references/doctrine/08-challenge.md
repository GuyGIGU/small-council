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
   - not checked (a command, a link, an area or no path): fine for research evidence or a plan's
     area — including a file the plan would still write ("nothing on disk by that name"). A review
     item needs a `path:line`, and `no-citation` says it has none: add one, or drop the item.
   - origin `origin unknown`: the helper could not tell whether the change made the line (a citation
     outside the repository, a file blame can't read, a line-ending rewrite). Treat it as the
     change's own unless you check it yourself — never drop it for the label.
   - Item lines it can't read, or a Kept section with no items and no `(none)` line: rewrite them in
     the index-line format and run the check again.
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
     (`council seat verify-<n> running agent=<id>`, then `done tokens=…`). One stopped at its
     60-turn limit may leave no file: resume it with SendMessage ("write your file now, then
     finish"), never re-dispatch it.
   - **If these verifiers are the run's first dispatch** (a Chair-only Squad, a post-game), show
     the user the run's status now, once — Work, "Right after dispatching", step 2. The helper's
     reminder says when.
   - A Workflow of verifiers is one seat `verify-<n>` recorded with `agents=N`, and planned with
     `budget/verify-<n>/agent-runs` — each of its agents counts against the cap, and takes items the
     same way: a P1 or protected item alone, the rest in batches of up to 8. Each agent writes
     `<run>/verify-<n>-<letter>.md` in the run folder itself. Never merge, copy or move them:
     `council evidence build` reads every `verify-*.md` there. After `run close`, pass `--run <name>`.
     The seat-check hook never sees a Workflow's agents: give them the file rules in their prompt
     (line 1 `# Verification — <run title>`, the verdict table, under 16 KB; write the file first).
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
   - Any cut claim a verifier CONFIRMED (or MISCITED) is restored: move its line under `## Kept`,
     id unchanged (`C4`), and ship it under that id. If it truly stays cut, add `still-cut: <why>`
     before `from:`. `council evidence check` holds the run until one or the other is done.
4. **Every shipped item has a verdict** — check before you move on.
5. **Refresh the claim index.** After verifier files exist, `council evidence build`, then
   `council evidence check`. Run `evidence build`/`check`, `collect` and `check` on their own
   (or test their exit status);
   never chain them through `| tail`/`| head`/`| grep`, which can swallow a refusal.
   Fix missing provenance, evidence-state declarations, proof artifacts, verifier rows or conflicting
   rows (a plan's several rows for one recommendation are expected: the worst verdict stands).
   `UNCERTAIN` remains a disclosed verdict, not a hidden pass.
   If optional Python is unavailable, check the same links by hand. This applies to synthesis
   claims in review, plan and research; build and post-game keep their own proof contracts.
6. **Verification gates**, for modes that changed code: `council gate --all --at verify`.

## Solo runs

Verify yourself, item by item, against the real code, with the same verdicts. Write them to
`<run>/verify-self.md`: line 1 `# Self-check — <run title>`, then the same
`| # | Item | Verdict | Evidence |` table. The claim index and the closing card label them
self-checked, never independent. A run with any verifier is Squad, not Solo.

## Done when

Every shipped item has a verdict and the gates are recorded. → `council state phase=deliver`
