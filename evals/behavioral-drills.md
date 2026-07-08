# Behavioral drills (run in Claude Code)

Run each once by hand before shipping a change to the skills. Record pass/fail + a note.

## D1 — Roster fit (`council-init`)
**Setup:** in any project with no `.council/council.config.md` (or a scratch copy). Pick one whose
stack is NOT the Carmack default — e.g. a Python service, a Go CLI, a Rails app.
**Run:** `council-init`.
**Pass if:** it detects the project's real stack + surfaces and proposes a roster that **drops** seats
with no surface (no frontend → no Dodds/Saarinen/Friedman) and **recasts** others to fit (non-Node
backend → a generic backend seat; non-Postgres store → a data-integrity seat; a numeric engine → a
numerical seat reusing `quality-llm.md`), keeping Carmack as chair and Fowler/Beck always; and it
detects the project's REAL gate commands instead of assuming `tsc`/`vitest`/`cypress`.
**Fail if:** it hard-codes the Carmack-default (Next.js) roster or the default gates instead of
detecting them.

## D2 — Triggering (`council-review` / `using-council`)
**Pass if:** the review mode engages when the user says "review this" / finishes a change / opens a
PR, WITHOUT an explicit slash command; and does NOT fire during unrelated conversation.
**Fail if:** it never auto-fires, or it fires on idle chatter.

## D3 — Bug caught (fixture)
**Setup:** point a review at `fixtures/` (see `fixtures/README.md`), which contains a seeded
off-by-one / null-deref style bug.
**Pass if:** the bug appears as a P1 (or P2) finding, attributed to the correct expert, with a
concrete fix and NO code snippet.
**Fail if:** the bug is missed, or the run emits code in the review.

## D4 — Memory respected (fixture)
**Setup:** `fixtures/conventions.md` contains an accepted pattern (AP-1) covering an intentional
choice in the fixture.
**Pass if:** the review does NOT re-flag AP-1 (proves read-before + the compound effect).
**Fail if:** it flags the accepted pattern as a finding.

## Context-hygiene spot checks (any real run)
- The Chair never deep-read every file (check it used Glob/Grep + a bounded set).
- Each worker returned ~one line to the parent; full findings live in `.council/review-output/$TS/*.md`.
- A `context-brief.md` exists and is edge-ordered (decision at top, constraints at bottom).
- After any compaction, the run resumed from `session-state.md` rather than restarting.
