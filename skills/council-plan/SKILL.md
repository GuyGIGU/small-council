---
name: council-plan
description: Plan a feature with the Small Council before any code is written — an interactive scoping conversation, then named domain seats advise in isolated context windows, and the Chair turns their advice into a sequenced, attributed, code-free plan whose tasks each say how to tell they're done. Use when the user wants to plan a feature, is about to start a non-trivial build, asks for a council plan, or invokes /council-plan. Propose it with its size and cost first.
---

# Council Plan (mode)

A mode on the context-core pipeline. **Invoke `context-core` and run its phases** with the inputs
below; this file supplies what is specific to planning.

**Planning, not review.** No seat hunts for bugs. Each seat says where the risk will live, how to
structure the work correctly from the start, and what the builder must get right the first time.

**Chair:** John Carmack — simplicity over cleverness, concrete over abstract, economic over aesthetic,
no flattery. The filter at synthesis: *needed for this feature at this scale, or premature?*

**Fit.** Plans suit work with a clear shape — a feature, an integration, a migration. For exploratory
work (algorithm tuning, a performance hunt, "which approach is best?") run **council-research** first
and plan from its answer.

## Discovery gate — replaces the Core's generic scope confirmation

The Core's phase 1 is a one-block confirmation. Planning needs a real conversation that pins the
feature down well enough to brief every seat. The Core does not map, brief, or dispatch until this
gate closes with an explicit go.

**Start from what exists.** If there's a spec (`specs/<feature>.md` from spec-writer, or one the user
points to), read it first and ask only what it leaves open. Read `map.md` and do a light survey
(Glob/Grep for entry points, existing patterns, schema shape) so every question is about the real code.

- **One question at a time.** A conversation, not a form.
- **Ground every question in what you saw.**
  - *Good:* "Your API routes are grouped by concern — auth, billing, users. Does this extend one of
    those or want its own module?" — *Bad:* "What architecture are you picturing?"
  - *Good:* "Records are keyed by `account_id` + `created_at`. Same grain, or a new table?" —
    *Bad:* "Who should have access?"
- **Reflect back** before moving on. **Don't propose solutions** — that's the council's job. **Ask what
  is already decided** and never plan against it.

Cover, naturally: what it does for the user; who uses it and the permission model; what data it
touches (new vs existing, external sources); what it connects to; what's **out of scope**; and what the
user already has opinions on. Then present:

```
## Feature Scope Summary
**Feature:** <name>
**What it does:** <2–3 sentences — user-facing behaviour>
**Users & access:** <who uses it, permission model>
**Data:** <new models/fields, existing models touched, external sources>
**Integrations:** <modules, routes, components it connects to>
**Out of scope:** <what this plan will not cover>
**Already decided:** <choices the user has made — don't plan against these>
**Council:** <size, seats, estimated cost>
```

Ask: **"Ready to dispatch the council, or do you want to adjust the scope?"** Adjust and ask again until
they say go. The confirmed summary becomes the top block of the brief; anything the user decided is a
Decision they may want recorded in memory.

## Inputs handed to the Core

```
roster:      council.config.md (canonical seats: references/roster/expert-catalog.md)
worker_format: below
synthesis:   owner rules + dependency order below · cap 15 tasks
gates:       grounding  = the config's checks, to confirm the code is in a known-good state before planning on it
             verification = the verifier checks every task's assumptions against the real code — each
                            names a module, pattern, or schema that exists; no task assumes vaporware
deliverable: <home>/plans/<slug>.md
memory:      conventions — the plan never recommends against an Accepted Pattern, Convention, or Decision
```

## Per-item format (goes in each dispatch)

```
### <n>. <title>
- Principle: <name + number from your reference doc>
- What to get right: 2–3 sentences — WHAT to build and WHY, specific to this feature in this code. No HOW, no code.
- Risk if skipped: 1 sentence, concrete
- Depends on: <other recommendations this must follow, or —>
```

## Synthesis rules (Core phase 7)

- **Owner rules:** visual → UI · component architecture → Frontend · flow and screen states → UX ·
  cross-module structure → Refactoring · async and runtime → Backend · LLM specifics → LLM · security →
  Security · schema and migrations → Data · speed → Performance · testability → Tests. Keep the owner's
  item plus a cross-reference.
- **Dependency order:** data design before the routes that read it; correctness decisions before the
  logic built on them; component architecture before the visuals on top; security informs all of it.
- **Carmack filter on every recommendation:** needed now, or speculative? Conflicts with memory? Cut
  what fails.
- **Group into build tasks** (a schema item with its constraint item; a visual item with its
  interaction item). At most 15 — merge if over. Items that aren't tasks but matter during the build
  become **Risks & Watchpoints**.
- **Every task gets a "Done when"** — an observable check (a test that passes, a behaviour a user can
  see, a query that returns the right thing). council-implement's verifier judges the task against it.

## Deliverable — `<home>/plans/<slug>.md`

```
# Council Plan: <Feature>
**Scope:** <1–2 sentences from the Feature Scope Summary>
**Context:** <2–3 sentences — how this fits the existing code>
**Out of scope:** <…>
**Council:** <who ran · who was skipped and why · who had no recommendations>

## Task Sequence
### 1. <Task title>
| | |
|---|---|
| **Domain** | <Seat> × Carmack — <principle> |
| **Ref** | `references/<file>.md` → Principle N |
| **Depends on** | — (or Task N) |
| **Done when** | <observable check> |

<WHAT to build and WHY — at most 3 sentences, no HOW, no code. Cross-reference other seats that shaped it.>

## Risks & Watchpoints
- **<Seat> — <principle>:** <when this bites and what to watch for>

## External Setup Required
| # | What | Why | Blocks task |
(or: "None — every task can be done inside the codebase.")

## Summary
| # | Task | Domain | Depends on |

## Verdict
<One direct paragraph: the most important architectural decision, the most critical domain, where to
start, and which seat is worth having on hand during the build.>
```

**Attribution is non-negotiable:** every task has a Domain row (seat + principle) and a Ref row
(document + principle number); a combined task names its primary domain and cross-references the rest.

In chat: the Summary table, the Verdict, the plan path — then, numbered: memory proposals (if the
discovery produced decisions worth keeping) and the hand-off: *"Build it with council-implement?"*

## Notes

- **No code, ever** — not in tasks, risks, or verdict. "Add a unique index on (account_id,
  created_at)", not a model block.
- A task whose description runs past 3 sentences is too broad — split it.
- Say plainly when a scope is risky, and just as plainly when it's straightforward.
