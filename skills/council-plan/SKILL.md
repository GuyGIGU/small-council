---
name: council-plan
description: Plan a feature with the Small Council before any code is written — an interactive scoping conversation, then named domain seats advise in isolated context windows, and the Chair turns their advice into a sequenced, attributed, code-free plan built as vertical slices, each task saying what it touches and how to tell it's done. Use when the user wants to plan a feature, is about to start a non-trivial build, asks for a council plan, or invokes /council-plan. Propose it with its size and cost first.
---

# Council Plan (mode)

A mode on the council's engine. **Invoke `context-core` and run its stages.** At each stage, read the
stage's doctrine, then this file's `## At <Stage>` section.

**This is planning, not review.** No seat hunts for bugs. Each seat says:
- where the risk will live;
- how to structure the work correctly from the start;
- what the builder must get right the first time.

**Chair:** John Carmack — simplicity over cleverness, concrete over abstract, economic over
aesthetic, no flattery. At Judge the filter is: *needed for this feature at this scale, or premature?*

**Fit.** Plans suit work with a clear shape: a feature, an integration, a migration. For exploratory
work — algorithm tuning, a performance hunt, "which approach is best?" — run **council-research**
first and plan from its answer.

## At Convene — the discovery gate (in place of the generic go-ahead)

Planning needs a real conversation that pins the feature down well enough to brief every seat.
Nothing gets mapped, briefed or dispatched until this gate closes with an explicit go.

**Start from what exists.**
- If there's a spec — `specs/<feature>.md` from spec-writer, or one the user points to — read it
  first and ask only what it leaves open.
- Read `map.md` and do a light survey (Glob/Grep for entry points, existing patterns, schema shape),
  so every question is about the real code.

**Rules for the conversation:**
- **One question at a time.** A conversation, not a form.
- **Ground every question in what you saw.**
  - *Good:* "Your API routes are grouped by concern — auth, billing, users. Does this extend one of
    those or want its own module?" — *Bad:* "What architecture are you picturing?"
  - *Good:* "Records are keyed by `account_id` + `created_at`. Same grain, or a new table?" —
    *Bad:* "Who should have access?"
- **Reflect back** before moving on.
- **Don't propose solutions** — that's the council's job.
- **Ask what's already decided**, and never plan against it.

Cover, naturally:
- what it does for the user;
- who uses it, and the permission model;
- what data it touches: new or existing, and any external sources;
- what it connects to;
- what's **out of scope**;
- what the user already has opinions on.

Then present:

```
## Feature Scope Summary
**Feature:** <name>
**What it does:** <2–3 sentences — user-facing behaviour>
**Users & access:** <who uses it, permission model>
**Data:** <new models/fields, existing models touched, external sources>
**Integrations:** <modules, routes, components it connects to>
**Out of scope:** <what this plan will not cover>
**Already decided:** <choices the user has made — don't plan against these>
**Council:** <seats going and why, seats not going and why, estimated cost>
```

Ask: **"Ready to dispatch the council, or do you want to adjust the scope?"** Adjust and ask again
until they say go. Anything the user decided is a Decision they may want recorded in memory.

- Deliverable: `<home>/plans/<slug>.md`.
- Cap: 15 tasks.

## At Prepare

- There's usually no diff, so no change index.
- Refresh the map areas the feature touches.
- Find the **nearest existing feature** and trace it end to end in one line, using the map's flows
  plus up to 3 skeleton reads: "Nearest precedent: <feature> — <entry> → <module> → <store>". It goes
  in the brief's landscape.

## At Brief

The question for every seat: *what must the builder get right, through your lens, to build this
feature correctly the first time?*

Not a finding:
- re-opening an "Already decided" choice;
- generic best practice with no anchor in this feature;
- anything a settled memory entry covers.

## At Work — the per-item format

Index line: `<n> · <must|should|could> · <principle> · <path or area> · <title>`

```
### <n>. <title>
- Principle: <name + number from your reference doc>
- What to get right: 2–3 sentences — WHAT to build and WHY, specific to this feature in this code. No HOW, no code.
- Risk if skipped: 1 sentence, concrete
- Touches: <the areas or files it would change, from the map>
- Assumes: <the design choices it takes as given>
- Depends on: <other recommendations it must follow, or —>
```

## At Judge

- **Owner rules.** Keep the owner's item and cross-reference the rest:

  | Topic | Owner |
  |---|---|
  | Visual | UI |
  | Component architecture | Frontend |
  | Flow and screen states | UX |
  | Cross-module structure | Refactoring |
  | Async and runtime | Backend |
  | LLM specifics | LLM |
  | Security | Security |
  | Schema and migrations | Data |
  | Speed | Performance |
  | Testability | Tests |

- **Conflict pass.** Items whose *Assumes* lines contradict each other either get settled by the code
  or become rulings for the user.
- **Order the work as vertical slices.**
  - Task 1 is a walking skeleton: the thinnest end-to-end slice that exercises the riskiest
    assumption or integration.
  - Each later task adds one working slice.
  - Data design comes before the code that reads it; security informs all of it.
- **Apply the Carmack filter** to every recommendation. Cut anything speculative or anything that
  conflicts with memory.
- **Group into build tasks,** at most 15. Merge if you're over.
- **Every task gets:**
  - **Done when:** an observable check.
  - **Touches:** the files or areas it may change.

  Items that aren't tasks but matter during the build become **Risks & Watchpoints**.

## At Challenge

The verifier checks each task's assumptions against the real code:
- the modules, patterns and schemas it names exist;
- its Touches are real paths.

Send claims in the form: "task <n>: <assumption> — <path>".

## At Deliver — `<home>/plans/<slug>.md`

```
---
(the doctrine's frontmatter, kind: plan)
---
# Council Plan: <Feature>
**Scope:** <1–2 sentences> · **Context:** <2–3 sentences> · **Out of scope:** <…>
**Council:** <who ran · who wasn't called and why · who had no recommendations>

## Task Sequence
### 1. <Task title>
| | |
|---|---|
| **Domain** | <what it checks> (<Seat>) × Carmack — <principle> |
| **Ref** | `references/<file>.md` → Principle N |
| **Depends on** | — (or Task N) |
| **Touches** | <files or areas> |
| **Done when** | <observable check> |

<WHAT to build and WHY — at most 3 sentences. No HOW, no code.>

## Risks & Watchpoints
- **<Seat> — <principle>:** <when this bites and what to watch for>

## External Setup Required
| # | What | Why | Blocks task |

## Summary
| # | Task | Domain | Depends on |

## Verdict
<One direct paragraph: the most important architectural decision, the most critical domain,
where to start, and which seat is worth having on hand during the build.>
```

**Attribution is non-negotiable.** Every task has a Domain row and a Ref row. A combined task names
its primary domain and cross-references the rest.

In chat: the Summary table, the Verdict and the plan's path. Then, numbered:
- the rulings needed;
- memory proposals;
- the hand-off: *"Build it with council-implement?"*

## Notes

- **No code, ever** — not in tasks, risks or the verdict. Write "Add a unique index on
  (account_id, created_at)", not a model block.
- **A task longer than 3 sentences is too broad** — split it.
- **Say it plainly:** if a scope is risky, say so; if it's straightforward, say that too.
