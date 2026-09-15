---
name: council-research
description: Evidence-graded investigation by the Small Council — parallel lines of inquiry work one question across the codebase, project history, docs, data, and the web; a verifier checks the load-bearing claims; the answer is saved to .council/research/ as durable project knowledge. Use for "how does X work", "why is Y slow", "what's the best approach to Z", "what would it take to…", before planning exploratory work, or to map an unfamiliar codebase. Propose it with its size and cost first.
---

# Council Research (mode)

A mode on the council's engine. **Invoke `context-core` and run its stages.** At each stage, read the
stage's doctrine, then this file's `## At <Stage>` section. Research is how the council *gathers*
context: it answers a question with evidence and leaves the answer on disk, so the next session
starts from it instead of re-discovering it.

**Chair:** John Carmack. *What does the evidence actually show, at this project's scale?* Say how
sure you are, and why.

**Use it for:**
- a question whose answer needs reading across many files or sources;
- exploratory work before a plan — algorithm tuning, a performance hunt, "which approach?";
- mapping an unfamiliar codebase or area.

**Not for:** a one-file lookup (just read it), or re-opening something the user already decided.

## At Convene — the question gate (in place of the generic go-ahead)

**Look for an existing answer first:** read `map.md` and past research in `<home>/research/`. Then pin
down the following, one question at a time and grounded in what you saw:
- **The question**, in one sentence.
- **The decision it informs:** what will the user do with the answer?
- **What counts as an answer:** a recommendation, a ranked list, a measured number, a yes/no with
  confidence, or a map.
- **Sources in bounds:** code, git history, past council output, project docs, data or measurements
  (read-only scripts only), the web.
- **Out of scope.**

Close with a **Research Scope Summary**: question · decision · answer shape · sources · out of scope ·
the lines of inquiry and their cost. Then ask to proceed.
- Deliverable: `<home>/research/<slug>.md`, or `map.md` when the question is a mapping question.
- Cap: 12 load-bearing claims.

## At Prepare — scout first

If the answer is **one fact, one root cause, or a yes/no**, propose a scout: one worker (or Solo)
with a small budget. Escalate to several lines of inquiry only if the scout can't settle it.

## At Assign — lines of inquiry, not the roster

Each line of inquiry is one clean partition of the evidence:
- **Code lines:** one per area in the map that could hold the answer.
- **History:** `git log` / `blame`, past plans, reviews, logs and research, and memory decisions.
- **Docs:** READMEs, specs, ADRs, and comments that state intent.
- **Web:** official docs, papers, issue trackers for the libraries in play — only if in bounds.
- **Measurement:** a read-only script or benchmark the scope allows. Record the exact command.

For a **"why" question**, use 3–5 rival hypotheses instead. Each line owns one hypothesis, plus the
evidence that would confirm or kill it. Name them in the scope summary so the user can confirm them.

When the question is domain-shaped, give a line the matching seat's reference doc — for example, a
"why is it slow?" line gets the Performance doc.

## At Brief

The question for every line: its own slice of the research question.

Not a finding:
- a claim without evidence;
- restating the question;
- opinions about decisions already made.

## At Work — the per-item format

Index line: `<n> · <strong|moderate|weak> · <line of inquiry> · <path:line or URL> · <claim>`

```
### <n>. <claim — one sentence>
- Evidence: path:line | URL | `command` → the output line that matters
- Strength: strong (direct evidence) | moderate (several consistent signals) | weak (a single hint or an analogy)
- Bears on: <which part of the question>
- Against / open: <what cuts against it, or what would settle it>
- Conflict: <when sources disagree, both sides, cited> (optional)
```

## At Judge

- **Merge first.** Aggregate every claim and merge duplicates.
- **Disagreements:** where lines of inquiry disagree, say so, and weigh by **evidence strength, not
  by headcount.**
- **Answer first,** at the confidence the evidence supports. Then give the load-bearing claims, then
  what's unknown and what would settle it.

## At Challenge

- The verifier checks every load-bearing claim.
- **Answer rests on a REFUTED claim** → revise the answer.
- **An UNCERTAIN load-bearing claim** → lower the stated confidence.
- **Cheap measurements** → re-run once.

## At Deliver — `<home>/research/<slug>.md`

```
---
(the doctrine's frontmatter, kind: research)
---
# Research: <question>
Informs: <decision> · Confidence: high | medium | low
## Answer
<3–8 sentences, direct>
## Evidence
| # | Claim | Evidence | Strength | Verified |
## Unknowns — and how to settle them
## What this changes
<for plans, conventions, the map; the suggested next step, e.g. council-plan>
## Sources
<files, commits, URLs, exact commands>
```

In chat, give:
- the answer and its confidence;
- the three strongest pieces of evidence;
- the path and the next step;
- any questions, numbered.

## At Learn — the map and memory

- **Keep the map true.** If the research found the map missing something or wrong, patch `map.md` in
  the same run.
- **Mapping questions:** each line of inquiry covers one top-level area and fills the map template's
  sections for it. Merge into one map of at most ~250 lines, and set `map-commit` to HEAD.
- **Memory:** propose candidates as usual. A decision the user makes on the answer is recorded in
  their words only.
