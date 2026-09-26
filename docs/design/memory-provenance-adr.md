# ADR: memory provenance and observed failures

## Problem

Memory decides what every later seat is told, so a wrong entry repeats itself. Settled entries
(accepted patterns, conventions, decisions) are the user's rulings. A past council failure — a
finding a verifier refuted, a gate that kept failing — is different: it is a fact about one run,
not a rule. Written as a rule it overstates its authority; left in a run log it is never found
again. Recorded as free text, an old agent guess could become permanent truth.

## Constraints

- Keep `conventions.md`, its sections and every older entry format working; no migration.
- The user approves every entry; the helper may draft but never decide.
- Selection runs on every brief with Bash and awk only; Python stays optional.
- Old evidence must not outrank current code: a remembered failure is a lead, never proof.

## Options

1. A database or JSONL store of lessons with confidence scores. Queryable, but a second memory
   beside the one users read and edit, and scores that nothing measures yet.
2. Failures as enforced conventions. No new category, but a one-off observation becomes a rule.
3. A separate Observed Failures (F) section in the same file: required fields, a verdict
   vocabulary, and evidence the helper re-opens whenever it serves the entry.

## Decision

Choose option 3. An F entry is served only with Failure, Scope, Origin, Evidence and Verdict; a
scope narrower than every run; a verdict that establishes it (OBSERVED, REPRODUCED, or a verifier's
CONFIRMED, REFUTED, MISCITED, REGRESSION, INCOMPLETE, SCOPE-CREEP); and cited files inside the
project that still show a verifier's verdict. Briefs label it "observed failure, not a rule".
`council memory propose` drafts entries from `claims.jsonl` and `repairs.jsonl`, never from a
summary; `accept|reject --user-said` files the user's answer with their words, and every edit is
validated with the serving parser before the file is replaced.

## Tradeoffs

The audit is mechanical: it proves a file still says REFUTED, as the verifier writes it, not that
the old failure applies to today's code. Evidence inside untracked run folders can disappear, which
drops the entry from briefs until it is re-anchored — safer than serving an unsupported claim, but
it can surprise. A whole-file citation is weak support. The helper cannot see the user's yes; the
recorded words make a skipped approval visible, not impossible. An independent review found eleven
ways around the first version of these rules (a looping line number, shared ids, spellings of an
every-run scope, text reassembling into fields); each is now a regression check.

## Alternatives rejected

No automatic promotion of lessons, no confidence arithmetic, no memory database, and no audit of
AP/EC/D evidence (their authority is the user's approval, and auditing them would break older
memories that cite prose).

## Revisit when

Benchmarks show whether served failures change findings; memories grow past the ~25 KB budget; or
teams need evidence that survives on other clones (copying cited evidence into a tracked store).
