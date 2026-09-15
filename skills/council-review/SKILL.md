---
name: council-review
description: Multi-expert code review by the Small Council — named domain seats review a change in isolated context windows, an adversarial verifier checks every finding against the real code, and you get prioritised P1/P2/P3 findings plus a fix hand-off. Use when a change is finished, a PR is opened or updated, code is "ready to merge", or the user asks for a council review. Propose it with its size and cost first; run straight away on /council-review.
---

# Council Review (mode)

A mode on the context-core pipeline. **Invoke `context-core` and run its phases** with the inputs
below; this file only supplies what is specific to reviewing.

**Chair:** John Carmack — simplicity over cleverness, concrete over abstract, economic over aesthetic,
no flattery, fix-don't-just-flag. The filter at synthesis: *a real problem in this codebase at this
scale, or pattern-matching?*

## Target — resolve it before sizing (Core phase 1)

- **Default:** the current branch against its base — `git merge-base HEAD <default branch>`, then
  `git diff --stat <base>...HEAD`, plus uncommitted work from `git status --short`.
- **A PR:** `gh pr view <n> --json files,baseRefName` and `gh pr diff <n>` when `gh` is available.
- **An implementation log:** its "Ready for review" list is the target.
- **A path, commit range, or module** the user names: exactly that.
- On the default branch with nothing changed → ask what to review.

State the target as files, +/− lines, and `base..head`. The size recommendation comes from it.

## What each seat gets

The brief's scope inventory lists every changed file with its +/− counts and the base ref — not the
diff itself. Each seat pulls its own slice (`git diff <base>...HEAD -- <files>`) and must check the
**blast radius** of every change it owns: callers of changed functions and signatures, the tests that
cover the changed code, and the config or schema the change relies on.

## Inputs handed to the Core

```
roster:      council.config.md (council-init writes it; canonical seats: references/roster/expert-catalog.md)
worker_format: below
synthesis:   owner rules below · cap 15
gates:       grounding  = the config's test / lint / build on the code under review — failures become findings
             verification = the verifier checks every finding you plan to ship (re-running gates on
                            unchanged code adds nothing)
deliverable: <home>/reviews/<YYYY-MM-DD>-<slug>.md
memory:      conventions — never re-flag an Accepted Pattern, Enforced Convention, or Decision
```

## Per-item format (goes in each dispatch)

```
### <n>. <title>
- File: path:line-range
- Principle: <name + number from your reference doc>
- Severity: P1 (bug, vulnerability, data loss, wrong result) | P2 (silent failure, maintainability
  landmine, compounding debt) | P3 (clarity, naming, style)
- What's wrong: 1–2 sentences, specific to this code
- Consequence: 1 sentence, concrete
- Fix: 1–2 sentences — what to change and where. No code.
```

## Synthesis rules (Core phase 7)

- **Owner rules — keep the owner's item, cross-reference the rest:** visual design → UI seat ·
  component architecture → Frontend · interaction flow and screen states → UX · cross-module structure
  → Refactoring · async and runtime behaviour → Backend · prompt injection and streaming → LLM ·
  general app security → Security · schema, migrations, data integrity → Data · hot paths → Performance.
  Tests is complementary, never a duplicate. A recast seat keeps the lens of the seat it came from.
- **Grounding-gate failures are findings:** build or type error → P1 · failing test → P1 · lint error
  → P2 · lint warning → P3, each with the exact message and location.
- Carmack filter, cut to 15, number findings sequentially across severities.

## Deliverable

`<home>/reviews/<YYYY-MM-DD>-<slug>.md`:

- **Target** — files, +/− lines, `base..head`.
- **Council** — who ran, who was skipped and why, who found nothing.
- **Findings, P1 → P3** — each with title, `path:line`, `Council: <Seat> × Carmack — <principle>` and
  its reference line, what's wrong, consequence, fix, and the verifier's verdict.
- **Refuted by verification** — one line each: what was claimed and why it's wrong.
- **Summary table**, then the **Verdict**: ship-ready or not, the single most important thing, the most
  critical domain.

Then the in-chat summary — never just "done":

```
## Council Review — <N> findings (<a> P1 · <b> P2 · <c> P3)
| # | Finding | Sev | Seat | Fix effort |
Start with: <1–2 sentences>
Verified: <c> confirmed · <u> uncertain · <r> refuted and dropped
Full review: <path>
```

## After the summary (numbered, in the chat)

1. **Memory proposals** (Core phase 9) — already written to memory's `## Proposed` section.
2. **Fix hand-off** — almost every review is followed by fixes. Offer: *"Fix these with
   council-implement? Default: every P1 and P2."* On yes, hand it this review's path.

## Notes

- No code in the review. No opening flattery. Teach, don't just flag.
- A Solo-size review still uses the finding format, the verifier's discipline, and the deliverable path.
