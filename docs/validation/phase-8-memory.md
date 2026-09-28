# Phase 8 — scoped, provenance-aware memory foundation

## Boundary

Small Council already keeps approved patterns, enforced conventions and the user's decisions in
`conventions.md`, with scoped selection and stale-anchor checks. This slice keeps that file and
its existing formats. It does not add a database, rewrite legacy entries, auto-approve a lesson,
or let a historical failure override current code or the user's ruling.

`council memory select` now includes an entry's one-line Pattern, Rule or Decision and Origin when
present. Older title-only entries remain selectable. A new `## Observed Failures (F)` section can
hold user-confirmed, scoped historical observations. An F entry requires Failure, Scope, Origin,
Evidence and Verdict; incomplete entries are indexed as NOT SERVED. Selected F entries are
explicitly labelled "observed failure, not a rule" with their verdict and evidence. The Chair
puts them in a separate brief block and checks applicability against current evidence.

## Why

Previously, selection printed only an entry's title and scope. The brief could therefore lose the
actual rule and its origin. A prior failure also had no distinct memory category: turning it into
an enforced convention would overstate its authority, while leaving it only in a run log made it
hard to retrieve by scope. The new category is evidence, not policy.

## Hardening review (2026-09-26)

A review of the first slice found four ways an unsupported failure could still reach every brief.
Each was reproduced with the helper before it was fixed:

| Gap in the first slice | Now |
|---|---|
| Any non-empty verdict was accepted, so `INFERRED`, `ASSUMED` or a guess was served as history. | The verdict must establish the failure: `OBSERVED`, `REPRODUCED`, or a verifier's `CONFIRMED`, `REFUTED`, `MISCITED`, `REGRESSION`, `INCOMPLETE`, `SCOPE-CREEP`. |
| "Required" scope accepted `none`, `all`, `*` or `.`, which the matcher reads as every run — so the entry reached unrelated runs. | A scope item that means every run keeps the entry out. |
| Any Pattern/Rule/Decision field satisfied the Failure requirement, and a `**Rule:**` was shown as the meaning of an entry labelled "not a rule". | Only `**Failure:**` (or `**Observation:**`) counts, and it is the only meaning shown. |
| Evidence was a recorded string: an entry citing a file that never existed was served, and `memory check` reported nothing. | Every `index`, `select` and `check` opens the cited files (below). |

**Provenance audit.** For each observed failure the helper reads the `**Evidence:**` paths — from the
repo root, then the council home, never outside them — in one pass for the whole memory. It does not
take the entry's word for anything. An entry reaches no brief when its evidence names no file, when
none of its files can be read as cited (missing, or a cited line past the end), or when a verifier's
verdict word appears on none of the cited lines (anywhere in a file cited whole). OBSERVED and
REPRODUCED name artifacts, not a verdict line, so for them the files must exist. `select` names each
entry it leaves out and why; `memory check` prints `EVIDENCE` for each missing or mis-cited piece and
`UNSUPPORTED` for each entry no longer served, and fails; `council doctor` counts both. An entry
with one missing piece and another that still shows its verdict stays served, with the note.
Settled AP/EC/D entries are not audited: their authority is the user's approval, not a file.

These checks are mechanical. A file that still shows `REFUTED` does not prove the old observation
applies to today's code — the brief still labels F entries as leads to check, never as rules.

### Independent review of the hardening (2026-09-26)

One blind verifier agent (about 224k tokens) was asked to refute the new rules by running the helper
on hostile memory files. It upheld one claim — memories without observed failures, and older AP/EC/D
formats, behave exactly as before — and found eleven defects in the rest. Each was reproduced by a
new check in `evals/run_memory.py` before it was fixed:

| Found | Fixed by |
|---|---|
| A cited line number past 2^53 made `select`, `check`, `index` and `doctor` loop forever (adding one to it no longer changed it), so one hand-edited entry could stall every brief. | Numbers of more than nine digits are refused as lines no file has. |
| Two entries sharing an id were audited as one, so a bad copy was served beside a good one; `propose` could also reuse an id written `f4`. | A shared id keeps both out; drafts are numbered past every spelling the parser reads; `accept`, `reject` and the file replacement refuse an id used more than once. |
| Scopes such as `**/`, `all/`, `?*`, `{**,x}`, `res://*` or `src/** *` reached every run past a guard that compared raw text. | The audit reads each scope with the select matcher's own functions and refuses any item that covers every path. |
| Evidence written as words around a URL gave the entry no audit row at all, so it was served. | Every observed failure now gets a verdict, even one with no usable evidence. |
| A verdict matched as a substring in any case: `UNCONFIRMED`, or prose saying "confirmed", counted as CONFIRMED. | The verdict must appear as the verifier writes it — a whole word in capitals — on a cited line, or anywhere in a file cited whole. |
| An entry could cite the memory file, even its own Verdict line, as evidence. | The memory file is never evidence. |
| A directory link or junction inside the project let the audit read a file outside it. | A cited file is used only if its real location is inside the project, and never if it is itself a link. |
| `***Verdict:***` or `***Scope:***` in copied text (and `<!---`) reassembled into a field or a comment after a one-pass replacement; a citation's text reached the Scope line unfiltered. End to end this made an accepted entry every-run, or turned REFUTED into CONFIRMED. | Runs of asterisks and dashes collapse in one pass; the default scope and anchor come only from cited places that are real files of the project; the helper's own fields follow all copied text. |
| A private key in copied text lost its end marker when the text was cut short, so its body survived redaction. | Private-key blocks are removed whole before the text is flattened. |
| `**Failure:** —` or `**Origin:** -` counted as present. | Placeholders (`-`, `—`, `none`, `n/a`, `tbd`, `?`) count as missing. |
| A rule filed under Observed Failures got a garbled reason. | It now says only F entries belong there. |

The stricter verdict match has a cost: a review deliverable's "Refuted by verification" heading no
longer counts as showing REFUTED, so an entry whose verifier row has gone (with its run folder) drops
out of briefs until its evidence is re-anchored. The reviewer ran only gawk (including its POSIX and
traditional modes), not bash 3.2 or BSD awk.

## From verified run evidence to a user-approved entry

Before this, an F entry had to be written by hand from the Chair's reading of the run, so its
fields carried the Chair's summary rather than the run's records. Now, at Learn:

1. `council memory propose claim <id>` drafts an entry from a synthesis claim the blind verifier
   **REFUTED** or **MISCITED** — the classic council failure. It refuses a CONFIRMED finding (a real
   defect, not a council failure), an UNCERTAIN, unverified or conflicting claim, and a
   `claims.jsonl` older than the Markdown it indexes. `council memory propose repair <task> --scope
   <paths>` drafts one from a build task's recorded gate failures after `repair check`'s integrity
   rules pass; the scope is the Chair's judgment and is required.
2. The helper fills Failure, Scope (default: the cited file), Origin, Evidence (the exact verifier
   row plus the tracked deliverable; or each saved failed-gate output), Verdict and Anchor from those
   records, with a `**Drafted:**` line naming the source. Text copied from artifacts cannot write a
   field or open a comment in the memory file, and secret-looking strings are redacted before
   anything is written. A draft that would not be served once accepted — a scope of every run,
   evidence that does not show its verdict — is refused before the file is touched. So is evidence
   the memory already cites (an entry, a proposal or a rejected line): nothing is proposed twice.
3. The draft goes under `## Proposed`, where no brief reads it, and the run's event stream gets
   `memory.proposed`.
4. Only the user's answer files it: `council memory accept F-<n> --user-said "<their words>"` moves
   it under Observed Failures with an `**Approved:**` line holding the date and those words;
   `reject` leaves one Rejected line with the words and the evidence, which blocks a re-proposal.
   Both refuse without the user's words, refuse anything that is not a proposal, and check the
   result before writing: the moved entry must be served (evidence audit included), every other
   entry must read exactly as before, and the memory file must not have changed meanwhile. The
   file keeps its own line endings.

The helper cannot know that the user said yes: the doctrine allows `accept` only after their answer
in the chat, and the recorded words make an unapproved entry a visible fabrication rather than a
silent one. Python 3.8+ is optional here as elsewhere; without it the manual path in
`references/doctrine/10-learn.md` remains.

## The "stalled" broad helper suite

`evals/run_cli.py` was reported as stalled during the first slice. The earlier session's log shows it
was killed twice while still running: once on Windows after about eight minutes, once inside WSL on
the `/mnt/c` checkout after about four, and `bin/council` was being edited while the first run was
reading it. Rerun unchanged in an isolated worktree on 2026-09-26, it passed **520/520 in 16 min
39 s** on Windows Git Bash (bash 5.3.9): about 900 helper calls at roughly one second each, the
slowest 14 s, no timeouts. It had printed nothing until the end; it now prints each result as it
finishes. WSL was not used or shut down for this investigation (its `wsl -l -v` hung during this
session and was left alone).

## Compatibility and tests

- Existing AP/EC/D headings and bullets remain readable; missing new fields do not silence them.
- Proposed, rejected and retired entries are still excluded. Incomplete F entries are visible in
  `council memory` with the reason, but do not reach a brief.
- A memory with no observed failures is parsed, selected and checked exactly as before; the audit
  runs only when an F entry is served.
- `evals/run_memory.py` (54 checks) covers selection with meaning and origin, scoped retrieval,
  each refusal above, the provenance audit's served and unserved cases (a path with a blank, a
  path outside the project, prose instead of a file, a partial loss), the doctor warning, legacy
  formats, and the proposal path end to end through real helper runs: a review run whose verifier
  refuted two claims and confirmed one, a build run with two recorded gate failures, and each
  refusal (confirmed finding, stale ledger, every-run scope, duplicate, missing words, not a
  proposal, a saved gate output edited afterwards), field and comment injection from copied text,
  secret redaction and a byte-order-marked CRLF memory file, plus one check for each defect the
  independent review found. Nine of the hardening checks fail against the first slice's helper.
  Of the fifteen review checks, twelve failed on the code before their fixes; the hang check hung
  (its runaway awk was stopped by hand, and the rest were then rerun with an ordinary line number
  in its place); one passed only vacuously there, because the draft it inspects had the wrong id.
  `evals/run_cli.py` keeps its own Phase 8 cases with a real evidence file.
- With this change, the structural (600), hook (135), repair (37) and evidence (21) suites pass on
  Windows. Update 2026-09-28: the released code also passed macOS (bash 3.2, BSD awk)
  and Linux CI in runs `36305577961` and `36319880515`; automatic checks are not live validation.
- No live Claude run or claim of improved findings is part of this slice. The Phase 7 live check
  remains open; context packs remain opt-in.

## Limitations and next work

The parser captures one-line labelled fields. A long multiline explanation still needs the source
file; authors should make the selected first line self-contained. An F id at the start of a plain
bullet (for example `- F-16 jets …` in prose) is now reported as a line that looks like an entry
but is not read. Evidence inside `.council/runs/` is local and untracked, so it can vanish with the
run folder or be absent on another clone; an entry then drops out of briefs, with a warning, until
its evidence is re-anchored to a tracked file. A file cited whole (the review deliverable) only has
to mention the verdict somewhere, so it is weaker support than a cited verifier row. Proposals come
from review, plan and research claims and from build gate trails; a build verifier's REGRESSION or
INCOMPLETE rows and post-game findings are not drafted by the helper yet and stay hand-written.
Nothing here shows that remembered failures improve later runs — that needs the benchmark. No
automatic memory promotion is present: every entry still needs the user's yes.
