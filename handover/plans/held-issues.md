# The other held issues, after T3

Written 2026-11-16. Each issue was read on GitHub; none has comments. The facts map (Sonnet, about
155k) is in the session scratchpad. "Done" means on main, or in T3 (PR #116, open).

**#47, touched gates only: still worth doing, about 400-600k.**
- **Asked:** a gate runs only when its paths meet the diff; untouched gates say "not rerun" in the
  receipt and PR body.
- **Not done.** Main's #68 reuse skips a green gate on the same tree, which is a different job.
- **What it needs:** a paths column in the Gates table (`records/gate_table.py`), `council gate
  --touched`, and the "not rerun" lines. The Gates table's columns and the exit code 4 ("nothing
  checked") are frozen, so the column is a contract change, and the owner decides it.
- **Order:** do it after T5. Its receipt lines belong with the helper-written receipt T5 adds.

**The rest of #59, patch apply and revert: still worth doing, small, about 250k, inside T5.**
- **Done by T2:** saved rounds (`T<n>-<r>.patch`/`.json` with tree hashes) and the verifier reading
  the patch.
- **Left:** `council patch apply|revert` and a receipt listing patches per round.
- **Why inside T5:** T5's revert check needs the same reverse-apply in a scratch copy. Build them as
  one, keyed by task as T2 chose, not by seat. Drop `--round`: the round is in the file name.

**The rest of #60, what regressed per round: still worth doing, small, about 150k, with T5.**
- **Done by T2:** the history (`patches/T<n>.md`) and the third-round refusal (D38).
- **Left:** each round's history line names which gate went red and what regressed.
- **Note:** T3's pack part 5 lists other tasks' rounds, not this task's own history. T5's fix-round
  builder needs its own history, so the pack links `patches/T<n>.md` for a fix round. That is a small
  change to `context.py` (`earlier` skips the task's own rounds today).

**#57, standing builder rules: mostly done by T3. Drop the rest unless a real run shows the need.**
- **Done:** `references/run/builder-rules.md` (11 rules, every one the issue lists), linked from every
  pack. The pack also prints the config's gates, time limit and Hard rules.
- **Left:** a generated `.council/builder-rules.md` per project, its refresh, and `council check`
  refusing a brief that does not link it.
- **Why drop:** with T5 every builder gets its orders from the pack, so a brief that skips the rules
  cannot happen. A per-project copy would be a second copy to keep fresh.

**#61, the user's rulings so far: partly done by T3. The rest waits on one question.**
- **Done:** the pack's part 4 carries the user's `council state decision=` words and ask.md's Later
  lines.
- **Left:** `council ruling add`, a `rulings.md`, a receipt list and a `council check` flag.
- **The question first:** "ruling" means either the user's recorded words (D7) or the Chair's
  `Ruling:` lines (D10), which sit in a build log that nothing parses.
  - If the user's words: it is done, and the rest is a receipt line (about 100k).
  - If the Chair's: a reader in `records/` for the build log's `Ruling:` lines and their place in the
    pack (about 250k).
- **Recommendation:** the user's words only. A Chair's ruling that binds a builder should go through
  `council state decision=` on the user's yes.

**#67, doctrine by surface: seat side done by T3; Chair side still worth doing, about 500-700k.**
- **Done:** packs carry `Ref:` and `Domain:` paths, never inline text. 04-brief already says a seat
  gets only its own seats' cards and docs.
- **Left:** context-core still loads each stage's doctrine for the Chair (`skills/context-core/SKILL.md`
  lines 27 and 43; the method load is 55,266 of 59,407 bytes, D13), and `run close` records no doctrine
  bytes.
- **Order:** do it after T5. A builder agent takes the loop's doctrine out of the Chair's window
  anyway, and the bytes to cut are then measurable.

**The setup side of #93: done by T3. Two follow-ups, one belongs with #62.**
- **Done:**
  - **Built by T3:** council-init reads ADRs, `docs/decisions*`, `ARCHITECTURE.md` and the rules in
    `CLAUDE.md`/`AGENTS.md`, proposes each as a `- PROPOSED decision:` line citing `file:line`, and
    fills the one-way table (`references/roster/decision-records.md`).
  - **On main:** the plan check and the verifier's question (T1).
- **Left:**
  - A command to accept a proposed decision. Today the yes is moved by hand. That is fine until real
    runs show it is a chore, so drop it for now.
  - A check that the one-way table's anchors still exist. It belongs in #62's refresh (about 100k
    there).
  - The scenarios that plant a second way. They are T4, with S10.
