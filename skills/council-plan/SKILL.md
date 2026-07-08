---
name: council-plan
description: Architect a feature with the Carmack Council BEFORE any code is written. Use when the user asks to plan a feature, wants a "council plan" / "carmack plan", is about to start a non-trivial build and needs an approach, or invokes /council-plan. Runs an interactive scoping gate, then fans out a council of named domain experts (security, refactoring, backend, data, tests, frontend, UI, UX, performance, +domain seat) — each advising in an isolated context window on how to build it right the first time — then synthesises a sequenced, attributed, code-free implementation plan. A MODE that runs on the context-core pipeline; PROPOSE it and confirm scope before dispatching, because the multi-agent fan-out costs real budget.
---

# Council Plan (mode)

This is a **mode**. It supplies planning content; the **`context-core`** skill runs the pipeline.
**Start by loading `context-core` and following its phases 1–10.** Read `context-core`'s
`references/context-engineering.md` for the doctrine. Everything below is what you hand the Core.

**Planning, not review.** The council advises on approach BEFORE code exists. No expert hunts for
bugs — each identifies where risk will live, how to structure things correctly from the start, and
what the developer must get right the first time. This is a **fan-out of parallel expert advisors**.

**Chair:** John Carmack — simplicity over cleverness, concrete over abstract, economic over
aesthetic, no sycophancy. Apply the **Carmack filter** at synthesis: *is this needed for THIS feature
at THIS scale, or is the subagent pattern-matching?*

## Invocation — suggest, then confirm

A council run is a multi-agent fan-out that costs real budget, so it is **not** silently auto-started.
When planning is warranted, **tell the user it looks worthwhile and get a go-ahead**, then run the
discovery gate below. Run immediately on an explicit `/council-plan`.

## Discovery gate (mode-specific — this REPLACES the Core's generic phase-1 scope gate)

The Core's phase 1 is a one-block scope confirmation. Planning needs more: a real conversation that
pins the feature down well enough to brief every expert. **Do not let the Core proceed to its map /
brief / dispatch until this gate closes with an explicit developer confirmation.** No soft gate.

**Ground first, then ask.** Do a light survey (Glob/Grep for structure, entry points, existing
patterns, schema shape) so your questions are specific to the real codebase — the deep structural map
is the Core's phase 2, after scope is locked. Then interview the developer:

- **Ask one question at a time.** A conversation, not a wall of questions.
- **Ground every question in what you saw.** Generic questions produce a generic brief.
  - *Good:* "Your API routes are grouped by concern — auth, billing, users. Does this feature extend
    one of those or want its own module?" — *Bad:* "What architecture are you picturing?"
  - *Good:* "Records are keyed by `account_id` + `created_at`. Same grain, or a new table?" —
    *Bad:* "Who should have access?"
- **Reflect understanding back** before moving on. **Don't propose solutions** — that's the council's
  job. **Don't plan against decisions the developer has already made** — ask what's already decided.

Cover, naturally (not as a checklist): what the feature does (user-facing behaviour, not
implementation); who uses it and the permission model; what data it touches (new vs existing models,
external sources); what it integrates with; what's explicitly **out of scope**; and what the
developer already has opinions on.

**Close the gate** by presenting a **Feature Scope Summary** and asking to proceed:

```
## Feature Scope Summary
**Feature:** [name]
**What it does:** [2–3 sentences — user-facing behaviour]
**Users & access:** [who uses it, permission model]
**Data:** [new models/fields, existing models touched, external sources]
**Integrations:** [modules/routes/components it connects to]
**Out of scope:** [what this plan will NOT cover]
**Developer decisions:** [approach choices already made — don't plan against these]
```

Then ask verbatim: **"Ready to dispatch the council, or do you want to adjust the scope?"** If they
adjust, update the summary and ask again. Only on an explicit "go" does the Core continue. The
confirmed summary becomes the top block of the Core's phase-3 brief.

## Mode inputs handed to the Core

```
personas + reference_docs:
  # DEFAULT roster below. If <project>/.council/council.config.md exists, use ITS tailored roster,
  # seat names, and seat→reference mapping instead (council-init writes it).
  Hunt (Security)            → references/security.md
  Fowler (Refactoring)       → references/refactoring.md
  Dodds (Frontend)           → references/quality-frontend.md
  Collina (Backend)          → references/quality-backend.md
  Leach (Data/Postgres)      → references/quality-postgres.md
  Performance                → references/quality-performance.md
  Willison (LLM pipeline)    → references/quality-llm.md
  Saarinen (UI)              → references/quality-ui.md
  Friedman (UX)              → references/quality-ux.md
  Beck (Tests)               → references/quality-testing.md
  # the Core resolves each references/… path to an absolute path before dispatch (context-core phase 5)

output_schema: Task Sequence (attributed) → Risks & Watchpoints → External Setup Required → Summary table → Verdict
gates:
  grounding (phase 1):  the project's checks from council.config.md (used to confirm the codebase
                        is in a known-good state before planning against it — not a build of new code)
  verification (phase 10): sanity-check every task against the real code — each references a module,
                           pattern, or schema that actually exists; no task assumes vaporware
synthesis_cap: 15            # a focused plan of 8 clear tasks beats 20 granular ones
memory_namespace: conventions.md
```

## Per-worker recommendation format (put in each worker's prompt)

Each worker advises on how to build the feature right — it is NOT reviewing code.

```
RECOMMENDATION:
- Title:
- Principle: <name + number from the worker's reference doc>
- What to get right: 2–3 sentences — WHAT to build and WHY, specific to THIS feature in THIS
  codebase. No code, no HOW.
- Risk if skipped: 1 sentence, concrete.
- Depends on: recommendation(s) this should come after, or "—".
If the lane is clean: "No <domain> recommendations. <one sentence why this feature has no <domain> surface>."
Plain English only — no code, schemas, or config blocks. Stay in your lane.
```

## Synthesis rules (mode-specific, applied in Core phase 7)

Remember the Core rule first: **aggregate & dedupe ALL recommendations before forming a verdict** —
don't become a biased extra advisor with a veto. Then:

- **Deduplicate by primary owner:** Saarinen owns visual; Dodds owns component architecture; Friedman
  owns UX flow / screen states; Fowler owns cross-module structure; Collina owns async/runtime;
  Willison owns LLM-pipeline specifics; Hunt owns app-sec; Leach owns schema/migration; Performance
  owns speed; Beck owns testability. Keep the primary owner's item + a cross-ref.
- **Build the dependency graph.** Order so prerequisites come first: schema/data design gates the
  routes that read it; correctness decisions gate the logic that depends on them; component
  architecture is defined before the UI/UX visuals that sit on it; security/integrity informs both.
- **Apply the Carmack filter to every recommendation** (this curbs subagent over-structuring): needed
  for THIS feature at THIS scale, or premature? Would Carmack build it, or call it speculative? Does
  it conflict with an accepted convention in `conventions.md`? Cut what fails.
- **Sequence into build tasks.** Group related recommendations into one task (e.g. a schema item +
  its constraint item; a visual item + its interaction item). **Cap at `synthesis_cap` (15).** Merge
  if over.
- **Keep provenance** on every task — persona, principle, reference line. Recommendations that aren't
  tasks but need awareness during build become **Risks & Watchpoints**.

## Output schema (Core "Output" phase)

Write the plan to **`PLAN-<feature-slug>.md` at the project root** (the deliverable the
`council-implement` mode consumes); the Core's brief + worker files stay under
`.council/council-plan-output/$TS/`. Then display it. **Attribution is non-negotiable — every task
traces to expert × principle × reference-doc line.**

```
# Council Plan: <Feature Name>
**Scope:** <1–2 sentences from the agreed Feature Scope Summary>
**Context:** <2–3 sentences — how this fits the existing codebase>
**Boundaries:** <what's explicitly out of scope>
**Council dispatched:** <who ran / who returned "no recommendations">

## Task Sequence
### 1. <Task title>
| | |
|---|---|
| **Domain** | <Expert> × Carmack — <Principle name> |
| **Ref** | `references/<file>.md` → Principle N |
| **Depends on** | — (or Task N) |

<WHAT to build and WHY — 2–3 sentences. Scoped, concrete, no HOW, no code. Cross-ref other experts
that also informed this: "see Risks & Watchpoints.">
### 2. … (repeat; ≤15 tasks total)

## Risks & Watchpoints
Expert-attributed awareness items that aren't tasks. Each names the expert + principle + when it applies.
- **<Expert> — <Principle>:** <1–2 sentences: when this risk bites and what to watch for.>

## External Setup Required
Actions outside the codebase the implementing agent cannot do (API keys, service signups, webhooks, DNS).
| # | What | Why | Blocking task |
|---|------|-----|---------------|
| 1 | … | … | Task N |
(If none: "No external setup required. All tasks can be implemented within the codebase.")

## Summary
| # | Task | Domain | Depends on |
|---|------|--------|------------|
| 1 | <short title> | <Expert> | — |
(mandatory — the scannable task sequence with dependencies)

## Verdict
<One direct Carmack-voice paragraph: the single most important architectural decision, the most
critical expert domain for this feature, where the developer should start, and any pair agent worth
having on hand during build. No flattery.>
```

**Attribution rules:** every task has a `Domain` row (expert + specific principle) and a `Ref` row
(reference doc + principle number); a combined task names the PRIMARY domain and cross-refs the
others; the Summary table is mandatory.

## Durable memory (Core phase 8)

`conventions.md` was read in phase 2 — the plan **must respect it** (never recommend against an
accepted pattern). After the plan is delivered, planning rarely mints new conventions; if the
discovery surfaced a durable decision worth recording, propose it (AP-*/EC-*) and append only on the
user's confirmation, with provenance + timestamp. If nothing qualifies, skip silently.

## Notes

- **No code, ever** — not in tasks, risks, or verdict. "Add a unique index on (account_id, created_at)"
  — not a model block. Describe WHAT and WHY; the developer writes the HOW.
- **Keep tasks scoped.** If a task's description runs past 3 sentences, it's too broad — split it.
- Spawn every roster seat even if its slice is empty (proves coverage). A no-surface seat returns one
  line. A missing worker is a planning gap.
- Voice: direct, economic, teach-don't-just-flag. No opening flattery. If the scope carries risk, say
  so; if it's straightforward, say that too.
