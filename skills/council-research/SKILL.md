---
name: council-research
description: Evidence-graded investigation by the Small Council — parallel investigators work one question across the codebase, project history, docs, data, and the web; a verifier checks the load-bearing claims; the answer is saved to .council/research/ as durable project knowledge. Use for "how does X work", "why is Y slow", "what's the best approach to Z", "what would it take to…", before planning exploratory work, or to map an unfamiliar codebase. Propose it with its size and cost first.
---

# Council Research (mode)

A mode on the context-core pipeline. **Invoke `context-core` and run its phases** with the inputs
below. Research is how the council *gathers* context: it answers a question with evidence and leaves
the answer on disk, so the next session starts from it instead of re-discovering it.

**Chair:** John Carmack — what does the evidence actually show, at this project's scale? Say how sure
you are, and why.

**Use it for** a question whose answer needs reading across many files or sources; for exploratory
work before a plan (algorithm tuning, a performance hunt, "which approach?"); and for mapping an
unfamiliar codebase or area. **Not for** a one-file lookup (just read it) or re-opening something the
user has already decided.

## Question gate — replaces the Core's generic scope confirmation

Read `map.md` and past research (`<home>/research/`) first — the answer may already exist. Then pin down,
one question at a time and grounded in what you saw:
- **The question**, in one sentence.
- **The decision it informs** — what will the user do with the answer?
- **What counts as an answer** — a recommendation, a ranked list, a measured number, a yes/no with
  confidence, a map.
- **Sources in bounds** — code, git history, past council output, project docs, data or measurements
  (read-only scripts only), the web.
- **Out of scope.**

Close with a **Research Scope Summary** (question · decision · answer shape · sources · out of scope ·
size, lanes, estimated cost) and ask to proceed.

## Lanes — designed per question, not the expert roster

Each lane is a clean partition of the evidence:
- **Code lanes** — one per area from the map that could hold the answer.
- **History lane** — `git log` / `blame`, past plans, reviews, logs, and research, memory decisions.
- **Docs lane** — READMEs, specs, ADRs, comments that state intent.
- **Web lane** — official docs, papers, issue trackers for the libraries in play (only if in bounds).
- **Measurement lane** — a read-only script or benchmark the scope allows; record the exact command.

When the question is domain-shaped, hand a lane the matching seat's reference doc (a "why is it slow?"
lane gets the Performance doc). Workers are `small-council:council-worker`, lane = slice.

## Inputs handed to the Core

```
roster:      the lanes above (seat reference docs only where the question is domain-shaped)
worker_format: below
synthesis:   rules below · at most 12 load-bearing claims
gates:       grounding = none by default (a measurement lane runs its own commands)
             verification = the verifier checks every load-bearing claim; re-run a cheap measurement once
deliverable: <home>/research/<slug>.md   (a mapping question → <home>/map.md)
memory:      conventions — settled decisions frame the question; they are not re-opened
```

## Per-item format (goes in each dispatch)

```
### <n>. <claim — one sentence>
- Evidence: path:line | URL | `command` → the output line that matters
- Strength: strong (direct evidence) | moderate (several consistent signals) | weak (a single hint or an analogy)
- Bears on: <which part of the question>
- Against / open: <what cuts against it, or what would settle it>
```

## Synthesis rules (Core phase 7)

- Aggregate every claim, merge duplicates. Where lanes disagree, say so and weigh by **evidence
  strength, not by headcount**.
- **Answer first**, at the confidence the evidence supports; then the load-bearing claims; then what's
  unknown and what would settle it.
- An answer resting on a REFUTED claim gets revised. UNCERTAIN load-bearing claims lower the stated
  confidence.

## Deliverable — `<home>/research/<slug>.md`

```
# Research: <question>
Asked: <date> · Informs: <decision> · Confidence: high | medium | low
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

In chat: the answer, its confidence, the three strongest pieces of evidence, the path, and the next
step — then any questions, numbered.

## Map and memory

- Research that finds the map missing or wrong → **patch `map.md`** in the same run. Keeping the map
  true is part of this mode's job.
- **Mapping questions:** lanes = top-level areas; each worker fills the map template's sections for its
  area; merge into one map of at most ~250 lines and set `map-commit` to HEAD.
- Propose memory candidates as usual. A decision the user makes on the answer is recorded in their
  words only.
