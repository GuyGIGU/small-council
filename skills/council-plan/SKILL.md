---
name: council-plan
description: Plan a feature with the Small Council before any code is written — an interactive scoping conversation, then named domain seats advise in isolated context windows, and the Chair turns their advice into a sequenced, attributed, code-free plan built as vertical slices, each task saying what it touches and how to tell it's done. For a big or tough feature — or "debate it" — the seats first answer each other in a war room. Use when the user wants to plan a feature, is about to start a non-trivial build, asks for a council plan, or invokes /council-plan. Propose it with its size and cost first.
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

**Open the run and save the request first:** `council run open council-plan`, then write ask.md with
the user's words, before your first question — a compaction can't paraphrase what's already on disk.
Record the size later, with `council state size=…`.

**Start from what exists.**
- If there's a spec — `specs/<feature>.md` from spec-writer, or one the user points to — read it
  first and ask only what it leaves open.
- A post-game (`<home>/postgames/…`) is a spec too: what was built goes under Already decided; ask
  only what's left open, and continue its request (`council state ask=<path>`).
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
**Council:** <seats going and why, seats not going and why, estimated cost> · War room: <on — why, ~<k>k more tokens, no extra agents | off>
```

Ask: **"Ready to dispatch the council, or do you want to adjust the scope?"** Adjust and ask again
until they say go. Anything the user decided is a Decision they may want recorded in memory.

**Keep the user's scoping answers.** Each answer that adds, drops or rules out something goes under
ask.md's `## Later, in your words` as `- <date>: "<their words>"`, before your next question — a
post-game reads them.

**The war room.** For a big or tough feature — or when the user says "debate it" — the seats answer
each other before you judge. `${CLAUDE_PLUGIN_ROOT}/references/war-room.md` says when it's on and how
it runs; name it on the Council line with its cost.

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

When the war room is on, the brief's top block says `War room: on — end your file with ## Approach`.

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

## At Collect — the war room

**On:** after a clean `council collect`, read `${CLAUDE_PLUGIN_ROOT}/references/war-room.md` and run
round 2 — at most 6 neutral points in debate.md, the seats they name resumed, then one more
`council collect`. **Off:** nothing extra.

## At Judge

- **Owner rules.** Keep the owner's item and cross-reference the rest:

  | Topic | Owner |
  |---|---|
  | Visual | UI |
  | Component architecture | Frontend |
  | Flow and screen states | UX |
  | Cross-module structure | Refactoring |
  | Server and runtime code | Backend |
  | Concurrency, ordering, cancellation | Concurrency |
  | Parsers, decoders, file formats | Untrusted input |
  | Accessibility | Accessibility |
  | Timeouts, retries, deploys, production config | Operability |
  | LLM specifics | LLM |
  | Auth, secrets, injection | Security |
  | Schema and migrations | Data |
  | Speed | Performance |
  | Testability | Tests |

- **Conflict pass.** Items whose *Assumes* lines contradict each other either get settled by the code
  or become rulings for the user.
- **A real structural choice? Two stances.** When the conflict pass or the scope leaves two
  defensible shapes the code doesn't settle — one table or two, extend a module or add a new one —
  write both stances side by side: what each builds, what it costs, what it risks, which items each
  serves. Put it to the user as a ruling before grouping tasks. Only for a real fork; never as a
  default, and no extra agents.
- **After a war room,** every point ends one of four ways — agreed, settled by the code, moved without
  new evidence (treated as not moved), or a fork that becomes Two stances (war-room.md).
- **The request, covered.** Before grouping, every part of the request — ask.md, and the filed request
  it continues — maps to a task, to Already decided (built, per a post-game), or to Out of scope with
  the user's dated words that ruled it out. A part with none of these gets a task, or a question to
  the user.
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
  - **Constraints:** every hard rule, settled memory entry and "Already decided" choice that binds
    it, quoted word for word with its source — a builder can't honour a rule it never sees.

  Items that aren't tasks but matter during the build become **Risks & Watchpoints**.

## At Challenge

The verifier checks each task's assumptions against the real code:
- the modules, patterns and schemas it names exist;
- its Touches are real paths.

Send claims in the form "<n> · task <t>: <assumption> — <path>", where <n> is the synthesis number of
the recommendation the assumption comes from (`-` when none). The ledger matches verdicts to seats by
that number.

After a war room, the agreements a task rests on, and the riskiest assumptions two or more seats named,
go to the verifier too.

## At Deliver — `<home>/plans/<slug>.md`

File the request first — `council ask save` — then write:

```
---
(the doctrine's frontmatter, kind: plan)
---
# Council Plan: <Feature>
**Your request:** `.council/asks/<file>` — "<its first ~12 words>…"
**Scope:** <1–2 sentences> · **Context:** <2–3 sentences> · **Out of scope:** <item> — you, <date>: "<their words>" · …
**Council:** <who ran · who wasn't called and why · who had no recommendations>

## Task Sequence
### 1. <Task title>
| | |
|---|---|
| **Domain** | <what it checks> (<Seat>) × Carmack — <principle> |
| **Ref** | `references/<file>.md` → Principle N |
| **Depends on** | — (or Task N) |
| **Touches** | <files or areas> |
| **Constraints** | "<the rule, quoted>" — <config hard rule, memory id, or Already decided>; or — |
| **Done when** | <observable check> |

<WHAT to build and WHY — at most 3 sentences. No HOW, no code.>

## How the council decided        ← war room only: the table in war-room.md

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
