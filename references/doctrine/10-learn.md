# Stage 10 — Learn and close

## Memory proposals — at most 8

- **Accepted patterns:** deliberate code to stop flagging. A REFUTED finding that turned out to be
  deliberate design is the best candidate.
- **Enforced conventions:** always/never rules the user adopted along with the fixes.
- **Observed failures:** evidence-backed history that would prevent a repeat; it is not a new rule.
  Propose the observation and its verdict, not a guessed cause; a future run treats it as a lead to
  check, never as proof.
- **Write each one in plain words, with evidence and effect:**
  `- PROPOSED accepted pattern: stop flagging <X> in <paths> — <why it's deliberate> (evidence: <path:line>; scope: <paths or seat slugs>; from <deliverable path>, <date>)`
- For a failure proposal, name the observed failure, scope, origin, evidence path, verdict and the
  future check it changes. The helper serves an F entry only with a verdict that establishes it
  (OBSERVED, REPRODUCED, or a verifier's CONFIRMED, REFUTED, MISCITED, REGRESSION, INCOMPLETE,
  SCOPE-CREEP), a scope narrower than every run, and evidence files that still show it.
- **Draft a failure from the run's own record when there is one:** a claim the blind verifier
  REFUTED or MISCITED (`council memory propose claim <id>`, after `council evidence build`), or a
  build task's recorded gate failures (`council memory propose repair <task> --scope <paths>`). The
  helper fills the entry from those records, not from your summary, writes it under `## Proposed`,
  and refuses one that could not be served. Otherwise write the proposal by hand.
- **Preserve the support level.** A proposal derived from a refuted or uncertain claim names that
  verdict and verifier file. A remembered decision is the user's ruling, not an agent's assumption;
  retain the dated words and origin. Never turn an `INFERRED` or `ASSUMED` note into settled memory
  just because it appeared in synthesis.
- **Admission rule:** propose only what would change a future run if it were missing — never what
  the code, manifests or CI already say.
- **A lesson about the council's own process** is scoped to its mode (`scope: council-plan`), so only
  that mode's runs read it — `council memory select` counts the run's mode as in scope.
- **Check memory first.** Grep the confirmed entries, `## Proposed` and `## Rejected`.
  - Already covered → skip it.
  - Already proposed → add "· seen again <date>" to that line.
  - Rejected → never propose it again.
- **Write them to memory's `## Proposed` section now**, then list them, numbered, in the chat.
- **On the user's answer:**
  - Yes → move the entry into its section with the next number, carrying **Scope:** (its scope),
    **Origin:** and **Anchor:** (if one exists). An F entry also needs **Failure:**, **Evidence:**
    and **Verdict:** before selection will serve it.
  - No → move it to `## Rejected` as title · date · their reason.
  - A drafted F entry: `council memory accept F-<n> --user-said "<their words>"` on a yes,
    `council memory reject …` on a no. Run it only after they answered in the chat — it records
    their words and the date, and checks the entry would be served before filing it.
  - **Decisions (D)** are recorded only in the user's own words.
- **Memory over ~25 KB** → the helper warns at run open; propose a
  consolidation as numbered operations ("merge AP-7 into AP-3", "retire EC-2 — superseded by
  EC-9"), applied one by one on the user's yes. Never rewrite the file wholesale. To retire an entry, move it under `## Retired` with a
  `**Retired:** <date> — <why>` line; no run reads it after that.
- **Stale anchors:** `council memory check` lists entries whose anchored file, line or symbol is
  gone. Propose re-anchoring or retiring each, as operations like the ones above. Anchor new entries
  to a path or a symbol; a line number drifts unnoticed.
- **Unsupported failures:** the same check lists each observed failure whose evidence file is gone
  or whose cited lines no longer show its verdict (`UNSUPPORTED` — no brief gets it). Propose
  re-anchoring its evidence to a file that still shows it, or retiring it; never restore it by
  editing its verdict.

## Close

`council run close` stamps the status and the actual cost and, for a completed run, adds each
seat's row to the ledger — counted from the seat files, synthesis.md's `from:` lines and the verify
tables, so keep those exact. Its warnings are for the user: tell them. `council ledger` shows the record: Convene estimates from it. `council ledger advice` says how much it supports,
seat by seat; a council-init refresh proposes roster changes only where the advice clears its bar.
- A run stopped for good → `--status abandoned`.
- A run the user paused → `--status paused`. When they want it back, `council run resume --run <folder>`.

**Close every run you open** — in order:
1. `council run close`.
2. **Show the closing card, once,** then send the owner's alert — each as the close's own lines say
   (a closed run needs `--run <folder>`).
3. `council run audit --run <folder>` reads the run back against the method; tell the user each FAIL
   line, in plain words.
