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

## Compatibility and tests

- Existing AP/EC/D headings and bullets remain readable; missing new fields do not silence them.
- Proposed, rejected and retired entries are still excluded. Incomplete F entries are visible in
  `council memory` but do not reach a brief.
- `evals/run_cli.py` covers content and origin in selection, scoped F retrieval, missing-evidence
  exclusion, and unapproved F exclusion. `evals/run_structural.py` guards the doctrine boundary.
- No live Claude run or claim of improved findings is part of this slice. The Phase 7 live check
  remains open; context packs remain opt-in.

## Limitations and next work

The parser captures one-line labelled fields. A long multiline explanation still needs the source
file; authors should make the selected first line self-contained. `Origin`, `Evidence` and `Verdict`
are recorded strings, not independently verified truths. Later Phase 8 work can add an audit that
checks referenced provenance without trusting old agent claims, and a controlled path from a
verified run failure into a user-confirmed F proposal. No automatic memory promotion is present.
