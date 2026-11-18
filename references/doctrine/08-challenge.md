# Stage 8 — Challenge

Catch what's wrong before the user sees it.

## Steps

1. **Mechanical pre-check.** `council check` reads synthesis.md: every place an item cites exists,
   and each item's origin comes from `git blame` and the change's own hunks against the base —
   introduced, touched (the change edited or removed lines in or next to it) or pre-existing. Write
   each origin into its item. Then, by verdict:
   - `missing-file` or `bad-line`: fix the citation if the intended line is obvious; else drop the item.
   - unreadable: rewrite the citation as `path:line`.
   - `deleted`: the change removed that file; the item stands, checked against the base.
   - `no-line`: the path exists; add the line when the item is about code.
   - not checked (a command, a link, an area or no path): fine for research evidence or a plan's
     area, even a file the plan would still write ("nothing on disk by that name"). A review item
     needs a `path:line`: on `no-citation`, add one or drop the item.
   - `origin unknown` (a citation outside the repository, a file blame can't read, a line-ending
     rewrite): treat it as the change's own unless you check it yourself — never drop it for the label.
   - Item lines it can't read, or a Kept section with no items and no `(none)` line: rewrite them in
     the index-line format and run the check again.
2. **Blind verification.** Dispatch `small-council:council-verifier`:
   - Each **P1**, and each item on a **protected subject** (context-core, Limits), gets its own
     verifier. The rest go in batches of up to 8.
   - A verifier gets only the item's synthesis number (1, 2 … or C1 for a cut item), a one-sentence
     claim and its `path:line` — never the seat, principle, reasoning or fix — plus the brief's path
     and the code root. How it traces and numbers is its contract.
   - Include every cut P1: a lone dissenter may be right.
   - Each verifier writes its own file, `<run>/verify-<n>.md` (n counts verifiers, not items). Track them like workers
     (`council seat verify-<n> running agent=<id>`, then `done tokens=…`). One stopped at its turn
     limit: context-core, Limits.
   - **If these verifiers are the run's first dispatch** (a Chair-only Squad, a post-game), show
     the user the run's status now, once (Work, "Right after dispatching", step 2).
   - A Workflow of verifiers: `${CLAUDE_PLUGIN_ROOT}/references/run/workflow.md`, Challenge. Each agent writes
     `<run>/verify-<n>-<letter>.md` in the run folder itself. Never merge, copy or move them:
     `council evidence check` reads every `verify-*.md` there. After `run close`, pass `--run <name>`.
   - **Over the cap?** P1s and protected items get their own verifiers first; keep one for the
     batch of everything else. If even that doesn't fit, pair P1s two to a verifier. Tell the user
     what shared a verifier.
   - A post-game's verifiers check its parts against the user's request instead — council-postgame
     says how.
3. **Apply the verdicts** — in the deliverable. Never renumber or delete synthesis.md's lines; the
   ledger counts them at close.
   - CONFIRMED ships.
   - REFUTED drops: move its line under `## Cut`, id unchanged (`council evidence check` holds the
     run while it is kept). Keep it for memory: deliberate design is a candidate accepted pattern.
   - UNCERTAIN ships labelled, and is never dropped if its subject is protected.
   - MISCITED ships with the corrected location.
   - Any cut claim a verifier CONFIRMED (or MISCITED) is restored: move its line under `## Kept`,
     id unchanged (`C4`), and ship it under that id. If it truly stays cut, add `still-cut: <why>`
     before `from:`. `council evidence check` holds the run until one or the other is done.
4. **Every shipped item has a verdict** — check before you move on.
5. **The claim index.** After verifier files exist, `council evidence check`: it builds the index
   from synthesis.md and the verify files, then judges it. Run `evidence check`, `collect` and
   `check` on their own (or test their exit status), never through a pipe (context-core, The helper).
   Fix missing provenance, evidence-state declarations, proof artifacts, verifier rows or conflicting
   rows. `UNCERTAIN` remains a disclosed verdict, not a hidden pass. This step is for synthesis
   claims in review, plan and research; build and post-game keep their own proof contracts.

## Solo runs

Verify yourself, item by item, against the real code, with the same verdicts. Write them to
`<run>/verify-self.md`: line 1 `# Self-check — <run title>`, then the same
`| # | Item | Verdict | Evidence |` table. The claim index and the closing card label them
self-checked, never independent. A run with any verifier is Squad, not Solo.

## Done when

Every shipped item has a verdict (a build: its final gates are recorded too). → `council state phase=deliver`
