---
name: council-review
description: Multi-expert code review by the Small Council — named domain seats review a change in isolated context windows, a blind verifier checks every finding against the real code, and you get prioritised P1/P2/P3 findings plus a fix hand-off. Use when a change is finished, a PR is opened or updated, code is "ready to merge", or the user asks for a council review. Propose it with its size and cost first; /council-review runs straight away up to the approved size.
---

# Council Review (mode)

A mode on the council's engine. **Invoke `context-core` and run its stages.** At each stage, read
that stage's doctrine, then this file's `## At <Stage>` section.

**Chair:** John Carmack — simplicity over cleverness, concrete over abstract, economic over
aesthetic, no flattery, fix-don't-just-flag. At Judge the filter is: *a real problem in this
codebase at this scale, or pattern-matching?*

## At Convene

Resolve the target before sizing:
- **Default:** the current branch against its base (`git merge-base HEAD <default branch>`), plus
  uncommitted work.
- **A PR:** `gh pr view <n> --json title,body,files,baseRefName` and `gh pr diff <n>`, when `gh` is
  available.
- **An implementation log:** its "Ready for review" list — and continue its request
  (`council state ask=<path>` from its "Your request" line).
- **A post-game:** its Checked range (`base..head`) — and continue its request, the same way.
- **A path, commit range or module the user names:** exactly that.
- **Default branch, nothing changed:** ask what to review.

State the target as files, +/− lines and `base..head`.
- Deliverable: `<home>/reviews/<YYYY-MM-DD>-<slug>.md`.
- Cap: 15 findings.

## At Prepare

- Always run `council index --base <base>`.
- Intent: the PR's title and body, or the user's own words.

## At Brief

The question for every seat: *what in this change will hurt this project, through your lens?*

Not a finding — this goes in the brief's bottom block, and the verifier gets it too:
- problems on lines this change didn't touch, unless the change newly reaches, exposes or worsens them;
- style or naming that no project rule requires;
- problems that need some future change before they bite;
- anything a settled memory entry covers;
- what the linter or type checker already reports (the grounding gates own those).

## At Work — the per-item format

Index line: `<n> · <P1|P2|P3> · <principle> · <path:line[-line]> · <title>`

```
### <n>. <title>
- File: path:line-range
- Principle: <name + number from your reference doc>
- Severity: P1 (bug, vulnerability, data loss, wrong result) | P2 (silent failure, maintainability
  landmine, compounding debt) | P3 (clarity, naming, style)
- Origin: introduced | touched | pre-existing — from git blame against the base
- Basis: seen (you traced it) | inferred (from signals)
- Refuted if: <the one observation that would prove this wrong, and where to look>
- Assumes: <anything outside your slice this depends on> (optional)
- What's wrong: 1–2 sentences, specific to this code
- Consequence: 1 sentence, concrete
- Fix: 1–2 sentences — what to change and where. No code.
```

## At Judge

- **Owner rules.** Keep the owner's item and cross-reference the rest:

  | Topic | Owner |
  |---|---|
  | Visual design | UI |
  | Component architecture | Frontend |
  | Flows and screen states | UX |
  | Cross-module structure | Refactoring |
  | Server and runtime code | Backend |
  | Concurrency, ordering, cancellation | Concurrency |
  | Parsers, decoders, file formats, deserialisation | Untrusted input |
  | Accessibility | Accessibility |
  | Timeouts, retries, deploys, configuration in production | Operability |
  | Prompt injection and streaming | LLM |
  | Auth, secrets, injection, general application security | Security |
  | Schema, migrations, data integrity | Data |
  | Hot paths | Performance |

  Tests complement the other seats; they never duplicate them. A recast seat keeps the lens of the
  seat it came from. When a topic's owner isn't seated, its nearest seated neighbour owns it.
- **Grounding-gate failures are findings**, each with the exact message and location:
  - build or type error → P1;
  - failing test → P1;
  - lint error → P2;
  - lint warning → P3.
- **Pre-existing problems** go in their own section, outside the 15 — unless they're P1 and this
  change makes them reachable.

## At Deliver

Write `<home>/reviews/<YYYY-MM-DD>-<slug>.md` with the doctrine's frontmatter and its "Your request"
line, then:
- **Target:** files, +/− lines, `base..head`.
- **Council:** who ran (and what each checks), who wasn't called and why, and who found nothing.
- **Findings, P1 → P3.** Each gives:
  - the title and `path:line`;
  - `<what it checks> (<Seat>) × Carmack — <principle>`;
  - its origin;
  - what's wrong, the consequence and the fix;
  - the verifier's verdict.
- **Pre-existing problems nearby:** one line each.
- **Refuted by verification:** one line each — what was claimed, and why it's wrong.
- **Not covered:** anything the council didn't look at.
- **Summary table**, then the **verdict:** ship-ready or not, the single most important thing, and
  the most critical domain.

In chat — never just "done":

```
## Council Review — <N> findings (<a> P1 · <b> P2 · <c> P3)
| # | Finding | Sev | Checked by | Fix effort |
Start with: <1–2 sentences>
Verified: <c> confirmed · <u> uncertain · <r> refuted and dropped · Cost: ~<k>k tokens
Full review: <path>
```

## At Learn

After the memory proposals comes the fix hand-off: *"Fix these with council-implement? Default:
every P1 and P2 this change introduced."* On a yes, hand it the review's path.

## Notes

- No code in the review.
- No opening flattery.
- Teach, don't just flag.
