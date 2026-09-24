# Evidence model — Phase 6

This contract adds traceability to the council's existing Markdown. It does not replace the seat
files, synthesis, verifier tables, citation check or human-readable deliverable. The Chair still
judges; a machine-readable row does not establish truth.

## Vocabulary

The **evidence state** describes the support available when a claim is made, not the verifier's
decision:

| State | Meaning |
|---|---|
| `OBSERVED` | A person or worker inspected a named source and reports what it directly shows. |
| `REPRODUCED` | A repeatable check was run; `proof:` names its saved run artifact. Merely naming a command is not enough. |
| `INFERRED` | A conclusion from cited signals; the missing direct observation remains explicit. |
| `ASSUMED` | A premise accepted for this task, not established by the cited material. |
| `UNVERIFIED` | Support is absent, incomplete or not yet checked. The ledger uses this for legacy lines with no declared state. |

The independent **verdict** is separate: `CONFIRMED`, `REFUTED`, `UNCERTAIN` or `MISCITED`.
`UNVERIFIED` is the ledger's verdict until a verifier row exists. Multiple verifier rows for the
same claim are `CONFLICT` until the Chair resolves them. A citation or successful syntax check is
never promoted to `CONFIRMED` automatically.

## Source of truth and syntax

Under `synthesis.md`'s `## Kept` and `## Cut`, retain the existing index-line shape. Add the fields
after the title, with `from:` last so the existing seat ledger can still attribute work:

```text
1 · P1 · Principle 4 · src/auth.py:88 · Expired tokens stay valid · state: OBSERVED · from: hunt#3
2 · P2 · Principle 1 · src/orders.py:40 · Duplicate order is accepted · state: REPRODUCED · proof: gates/repro-2.json · from: leach#1, beck#2
C1 · P1 · Principle 3 · src/api.py:12 · Suspected bypass · why: lower priority · state: INFERRED · from: hunt#4
```

`from:` names each originating `seats/<slug>.md` item as `<slug>#<n>`. For a Solo judgment use
`from: chair`; for a finding discovered by a grounding gate use `from: gate:<name>`. If the claim
is `REPRODUCED`, `proof:` contains one or more comma-separated `gates/<name>.json` verdict paths
**inside this run**. `council evidence check` checks those paths exist, not whether the output
proves the claim; read the corresponding `.txt` output and command before making that judgment.
The citation field remains subject to `council check`, which checks places and origin.

The verifier receives only claim id, one-sentence claim and citation, plus the brief and code root.
It does **not** receive `from:`, the source seat or the evidence state. Its `verify-<n>.md` table
retains `| # | Item | Verdict | Evidence |`; the `#` is exactly the synthesis id. The Chair records
corrections in the readable deliverable rather than overwriting the verifier's words.

## Run-local index

After Judge, `council evidence build` writes `<run>/claims.jsonl` as a provisional snapshot. After
Challenge and `council check`, rebuild it, run `council evidence check`, then inspect it with
`council evidence show`. The check rejects stale snapshots, absent evidence-state/provenance/citation
fields, missing seat item or reproduction artifacts, missing verdicts for kept claims or cut P1s,
unlinked verifier evidence, duplicate verifier rows and unknown claim ids. `UNCERTAIN` is a valid
verdict but must be labelled in the deliverable. `REFUTED` stays in the audit trail and is dropped
from shipped findings unless a later, recorded challenge reverses it.

Each JSONL row records schema `1`, id, kept/cut disposition and cut reason, claim text, citation, evidence state,
proof paths, source item ids, the synthesis line, the verifier table line(s), the verifier's
evidence and the final recorded verdict. Rows are regenerated deterministically from Markdown;
never edit them by hand. Existing runs remain readable without migration; auditing one with
`evidence check` may flag fields it predates. If Python 3.8+ is unavailable, use the
same Markdown fields and inspect each link manually; do not present a ledger as built.

This first version indexes synthesis claims in review, plan and research runs. Build tasks and
post-game request parts retain their own before/after gates and verifier tables; they use the
same evidence-state vocabulary in prose but are not squeezed into this claim schema.
