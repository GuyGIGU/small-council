# Stage 10 — Learn and close

## Memory proposals — at most 8

- **Accepted patterns:** deliberate code to stop flagging. A REFUTED finding that turned out to be
  deliberate design is the best candidate.
- **Enforced conventions:** always/never rules the user adopted along with the fixes.
- **Observed failures:** evidence-backed history that would prevent a repeat; it is not a new rule.
  Propose the observation and its verdict, not a guessed cause; a future run reads it as law 11 says.
- **Write each one in plain words, with evidence and effect:**
  `- PROPOSED accepted pattern: stop flagging <X> in <paths> — <why it's deliberate> (evidence: <path:line>; scope: <paths or seat slugs>; from <deliverable path>, <date>)`
- A failure proposal names the observed failure, scope, origin, evidence path, verdict and the
  future check it changes. Which verdicts and scopes get one served: the memory file's
  `## Observed Failures` comment (`references/templates/conventions.md`).
- **Draft a failure from the run's own record when there is one:** a claim the blind verifier
  REFUTED or MISCITED (`council memory propose claim <id>`, after `council evidence build`), or a
  build task's recorded gate failures (`council memory propose repair <task> --scope <paths>`). The
  helper fills the entry from those records, not from your summary, writes it under `## Proposed`,
  and refuses one that could not be served. Otherwise write the proposal by hand.
- **Preserve the support level.** A proposal from a refuted or uncertain claim names that verdict
  and verifier file. A remembered decision is the user's ruling, not an agent's assumption: keep the
  dated words and origin. Never turn an `INFERRED` or `ASSUMED` note into settled memory because it
  appeared in synthesis.
- **Admission rule:** propose only what would change a future run if it were missing — never what
  the code, manifests or CI already say.
- **A lesson about the council's own process** is scoped to its mode (`scope: council-plan`):
  `council memory select` counts the run's mode as in scope, so only that mode's runs read it.
- **Check memory first.** Grep the confirmed entries, `## Proposed` and `## Rejected`: already
  covered → skip it; already proposed → add "· seen again <date>" to that line; rejected → never
  propose it again.
- **Write them to memory's `## Proposed` section now**, then list them, numbered, in the chat.
- **On the user's answer:**
  - Yes → move the entry into its section with the next number, carrying **Scope:** (its scope),
    **Origin:** and **Anchor:** (if one exists); an F entry also **Failure:**, **Evidence:** and
    **Verdict:**.
  - No → move it to `## Rejected` as title · date · their reason.
  - A drafted F entry: `council memory accept F-<n> --user-said "<their words>"` on a yes,
    `council memory reject …` on a no — only after they answered in the chat: it records their
    words and the date, and checks the entry would be served before filing it.
- **When the helper warns about memory** — over its budget (`- memory budget:`, 25 KB by default;
  `council memory tidy` lists what reading alone can find), or `council memory check` lists a stale
  anchor or an `UNSUPPORTED` failure — read the upkeep rules in the head of
  `${CLAUDE_PLUGIN_ROOT}/references/templates/conventions.md` and propose each fix as they say.
  Anchor new entries to a path or a symbol; a line number drifts unnoticed.

## Close

`council run close` stamps the status and the actual cost and, for a completed run, adds each
seat's row to the ledger — counted from the seat files, synthesis.md's `from:` lines and the verify
tables, so keep those exact. Its warnings are for the user: tell them. `council ledger` shows the record: Convene estimates from it. `council ledger advice` says how much it supports,
seat by seat; a council-init refresh proposes roster changes only where the advice clears its bar.
- A run stopped for good → `--status abandoned`.
- A run the user paused, "stop for tonight" too → `--status paused`; to bring it back,
  `council run resume --run <folder>`.

**Close every run you open** — in order:
1. `council run close`. It prints each FAIL of `council run audit --run <folder>` and keeps the whole report as `<run>/audit.md`.
2. **Show the closing card, once,** then send the owner's alert — each as the close's own lines say
   (a closed run needs `--run <folder>`).
3. Tell the user each FAIL line, in plain words.
