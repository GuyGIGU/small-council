# Stage 10 — Learn and close

## Memory proposals — at most 8

- **Accepted patterns:** deliberate code to stop flagging. A REFUTED finding that turned out to be
  deliberate design is the best candidate.
- **Enforced conventions:** always/never rules the user adopted along with the fixes.
- **Write each one in plain words, with evidence and effect:**
  `- PROPOSED accepted pattern: stop flagging <X> in <paths> — <why it's deliberate> (evidence: <path:line>; scope: <paths or seat slugs>; from <deliverable path>, <date>)`
- **Admission rule:** propose only what would change a future run if it were missing — never what
  the code, manifests or CI already say.
- **Check memory first.** Grep the confirmed entries, `## Proposed` and `## Rejected`.
  - Already covered → skip it.
  - Already proposed → add "· seen again <date>" to that line.
  - Rejected → never propose it again.
- **Write them to memory's `## Proposed` section now**, then list them, numbered, in the chat.
- **On the user's answer:**
  - Yes → move the entry into its section with the next number, carrying **Scope:** (its scope)
    and **Anchor:** (its evidence) so later runs read it only where it applies.
  - No → move it to `## Rejected` as title · date · their reason.
  - **Decisions (D)** are recorded only in the user's own words.
- **Memory over ~25 KB** → propose a consolidation as numbered operations ("merge AP-7 into AP-3",
  "retire EC-2 — superseded by EC-9"). Apply them one by one on the user's yes. Never rewrite the
  file wholesale.
- **Stale anchors:** `council memory check` lists entries whose anchored file, line or symbol is
  gone. Propose re-anchoring or retiring each, as operations like the ones above. Anchor new entries
  to a path or a symbol where you can — a line number can drift without anyone noticing.

## Close

`council run close` stamps the status and the actual cost. For a completed run it also adds each
seat's row to the ledger — items raised, kept, cut and refuted, and tokens — counted from the seat
files, synthesis.md's `from:` lines and the verify tables, so keep those exact. `council ledger`
shows the record: Convene estimates from it, and a council-init refresh proposes roster changes
from it.
- A run stopped for good → `--status abandoned`.
- A run the user paused → `--status paused`.

**Close every run you open.**
