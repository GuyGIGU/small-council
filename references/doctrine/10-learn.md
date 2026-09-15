# Stage 10 — Learn and close

## Memory proposals — at most 8

- **Accepted patterns:** deliberate code to stop flagging. A REFUTED finding that turned out to be
  deliberate design is the best candidate.
- **Enforced conventions:** always/never rules the user adopted along with the fixes.
- **Write each one in plain words, with evidence and effect:**
  `- PROPOSED accepted pattern: stop flagging <X> in <paths> — <why it's deliberate> (evidence: <path:line>; from <deliverable path>, <date>)`
- **Admission rule:** propose only what would change a future run if it were missing — never what
  the code, manifests or CI already say.
- **Check memory first.** Grep the confirmed entries, `## Proposed` and `## Rejected`.
  - Already covered → skip it.
  - Already proposed → add "· seen again <date>" to that line.
  - Rejected → never propose it again.
- **Write them to memory's `## Proposed` section now**, then list them, numbered, in the chat.
- **On the user's answer:**
  - Yes → move the entry into its section with the next number.
  - No → move it to `## Rejected` as title · date · their reason.
  - **Decisions (D)** are recorded only in the user's own words.
- **Memory over ~25 KB** → propose a consolidation as numbered operations ("merge AP-7 into AP-3",
  "retire EC-2 — superseded by EC-9"). Apply them one by one on the user's yes. Never rewrite the
  file wholesale.

## Close

`council run close` stamps the status and the actual cost.
- A run stopped for good → `--status abandoned`.
- A run the user paused → `--status paused`.

**Close every run you open.**
