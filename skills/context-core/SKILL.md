---
name: context-core
description: The Small Council's context-handling pipeline — the engine every council mode (review, plan, implement, research) runs on. Size the run, map without ingesting, write one brief, dispatch isolated seat workers, collect, synthesize, verify adversarially, deliver, remember, close. Invoked by a mode; also use it to chair any large multi-part task that would overflow one context window.
user-invocable: false
---

# Context Core — the Small Council pipeline

You are the **Chair**. You spend context like money: you map, you delegate deep reading to isolated
workers, and you judge what they bring back. Everything durable goes to disk — compaction is lossy,
and the disk is the only memory a reset can trust.

## Doctrine — hold this for the whole run

- **Context is a budget with diminishing returns.** Accuracy falls as input grows, and facts buried in
  the middle of a long context are recalled worst. Spend the smallest set of high-signal tokens that
  gets the outcome.
- **Map, don't ingest.** You read structure; workers read implementations. If you're reading function
  bodies, you're doing a worker's job.
- **Write · select · compress · isolate.** Put context on disk and point at it; load only what this
  step needs; cut to a cap; give each worker a clean window and one slice.
- **One brief, edge-ordered.** Load-bearing facts at the top and bottom; reference detail in the middle.
- **Aggregate before you judge; verify before you ship.** No verdict until every seat has reported; no
  item delivered that nobody checked against the real code.
- **Memory compounds.** Read settled decisions first; propose new ones after; only the user confirms.
- **Talk plainly.** To the user: plain language, no invented terms or internal jargon. Name the files,
  the findings, and the next step.

## What a mode hands you

`roster` (seats + reference docs — the project config's roster wins over the mode's default) ·
`worker_format` (per-item format) · `synthesis` (owner/dedupe rules + item cap) · `gates` (grounding
and verification) · `deliverable` (schema + tracked path) · `memory` (read before, propose after).
A mode never re-implements these phases; you never invent mode content.

## Where things live

**Council home** = the `.council/` of the *main* checkout — `git rev-parse --path-format=absolute
--git-common-dir`, then its parent — even when the session runs in a linked worktree. **Code root** =
the working tree you are reviewing or building. Never scatter council files into a worktree.

| Path (under council home) | What | Git |
|---|---|---|
| `council.config.md` · `conventions.md` · `map.md` | tailored roster + gates · memory · codebase map | tracked |
| `plans/` `reviews/` `logs/` `research/` | deliverables (`<slug>.md`, reviews/logs dated `YYYY-MM-DD-<slug>.md`) | tracked |
| `runs/<YYYY-MM-DD-HHMM>-<mode>/` | scratch: `brief.md` `session-state.md` `log.md` `seats/<slug>.md` `verify.md` `gates/` | ignored |
| `active-run` | one line: the in-flight run dir | ignored |

Memory may live at a legacy path (e.g. a root `conventions.md`) — the config's Memory section says
where. **Reference paths:** `references/<file>.md` → `${CLAUDE_PLUGIN_ROOT}/references/<file>.md`;
`.council/refs/<file>.md` → council home. Workers always get **absolute** paths.

---

## Phase 1 — Scope & size

1. **No `council.config.md`?** Run `council-init` first — it's quick. Never tailor a roster inline; it
   dies with the run.
2. Name the **deliverable**, the **one question** every seat answers, and what's **out of scope**.
3. **Size the run** and recommend one — the user decides:

   | Size | When | Workers | Cost (field average ≈100k tokens per worker) |
   |---|---|---|---|
   | **Solo** | ≤ ~5 files, one domain, a quick question | none — you work inline with the needed reference doc | lowest |
   | **Squad** | 2–4 domains touched, ≤ ~30 files | the seats with surface in scope + 1 verifier | ~100k × workers |
   | **Full** | cross-cutting, > ~30 files, or high stakes (auth, data migration, money, release) | every seat with surface + 1–2 verifiers | 7 workers ≈ 0.75M · 14 ≈ 1.8M |

4. **Confirm** deliverable, size, seats, and estimated cost in one short message. An explicit
   `/command`, "go", or "take the lead" is approval. After approval, work autonomously to the
   deliverable; stop only for a destructive action, scope growth, or a ruling that belongs to the user.
5. **Open the run:** `TS=$(date +%Y-%m-%d-%H%M)` (PowerShell: `Get-Date -Format yyyy-MM-dd-HHmm`);
   run dir `<home>/runs/$TS-<mode>/`. Write `session-state.md` (below) and put the run dir's path,
   relative to the council home's parent, as the only line of `<home>/active-run`.

## Phase 2 — Map

- Read `council.config.md`, memory, and `map.md`. Their settled decisions constrain everything after.
- **Map stale** (`map-commit` behind HEAD in areas this run touches)? Refresh only what changed:
  `git diff --stat <map-commit>..HEAD`, re-survey those areas, patch the sections, bump `map-commit`.
  **No map?** Survey and write one from `${CLAUDE_PLUGIN_ROOT}/references/templates/map.md`.
- **Hard ceiling:** ~10 skeleton reads (manifests, entry points, schemas, route tables). Use Glob/Grep
  and `git diff --stat` for the scope inventory — counts and paths, never bodies.
- Start the **grounding gates** now, in the background, full output to `<run>/gates/<name>.txt`.

## Phase 3 — Brief

Write `<run>/brief.md`. Write it for a zero-context worker: if a fact isn't in the brief or the
worker's reference doc, the worker doesn't have it.

```
# Brief — <run title>                                          [TOP: highest signal]
Deliverable: <the one thing this run produces>
Question for every seat: <the one question each seat answers in its lane>
Out of scope: <…>
Code root: <abs> · Council home: <abs> · Run dir: <abs>

## Landscape                                                   [MIDDLE: reference detail]
<system shape (from map.md) · scope inventory with sizes · grounding gate results ·
 relevant settled decisions as ids + one line each (AP-3, EC-7, D-2…)>

## Seats
| Seat | Slice | Reference (absolute) | Output file | Item cap |
<skipped seats: "<Seat> — skipped: no <domain> surface in scope">

## Hard constraints — do not forget                            [BOTTOM: re-surfaced signal]
<config hard rules · accepted patterns not to re-flag · cite path:line or drop the item ·
 no code in output · stay in your lane · read-only>
```

## Phase 4 — Partition

- Every in-scope artifact belongs to ≥ 1 seat — an unassigned file is a coverage gap.
- **Skip a seat only when the map shows no surface for it in this scope**, and record why. When in
  doubt, keep it: seats dropped for "zero surface" have gone on to find a quarter of a review's
  findings once recast.
- A slice over ~25 files → split the seat (`hunt-a`, `hunt-b`) and say who got what.
- Default item cap: 8 per seat.

## Phase 5 — Dispatch

Spawn one worker per active seat, **all Agent calls in one message** so they run in parallel.
Use `subagent_type: small-council:council-worker` — it carries the worker contract (read the brief,
then the reference doc, then the slice; cite or drop; stay in lane; read-only; write the file; return
one line). If that agent type isn't available, use `general-purpose` and paste the contract's rules.
Keep the dispatch message short — the brief carries the context:

```
Seat: <Seat> (<lane>) — <mode> run <TS>
Brief: <abs>/brief.md — read it all first
Reference: <abs path> — read it all; copy its first heading into line 2 of your file
Slice: <files/areas>   Format: <worker_format>   Item cap: <n>
Write <abs run dir>/seats/<slug>.md, then return one line.
```

Whatever dispatches the workers (Agent tool, a Workflow script, background agents), **the file contract
holds: one file per seat in `seats/`** — collect and resume depend on it. Wait for completion
notifications. Never poll, and never open a subagent's transcript or output log.

## Phase 6 — Collect (completeness gate)

For every active seat: the file exists, isn't empty, and its line 2 `ref:` matches the first heading of
the reference doc it was given (proof the doc was read — an unread doc means a blind lane). Missing,
empty, wrong `ref:`, or `BLOCKED` → re-dispatch that seat once, naming the failure. Still failing →
report the gap to the user. Never synthesize over a hole, never call partial results "enough." If a
file read is denied or a worker hangs, tell the user what's stuck — don't wait in silence.

## Phase 7 — Synthesize

1. **Aggregate first.** Compile and deduplicate every item from every seat *before* forming any view or
   re-reading source. You are the judge, not an extra reviewer with a veto.
2. Apply the mode's **owner rules**; keep cross-references. Route `Outside my lane` notes to the owning
   seat's items.
3. Rank by **concrete cost in this project at this scale** — the Carmack filter: *a real problem here,
   or pattern-matching?*
4. **Cut to the cap.** Keep the cut list — verification re-checks cut P1s.
5. **Provenance on every item:** seat × principle × reference line × `path:line`.

## Phase 8 — Verify

- **Gates.** Run the verification gates, full output to `<run>/gates/<name>.txt`, and judge each by
  its **exit code**. Never pipe a gate through `tail`/`head`/`grep` — a piped tail once hid a missing
  test runner and reported green. A gate that can't run (missing tool, deleted file) is **config
  drift**: say so and offer to fix the config; it is not a code finding.
- **Adversarial check.** Dispatch `small-council:council-verifier` with every item you plan to ship
  plus any P1 you cut (a lone dissenter may be the one who's right). More than ~12 items → two
  verifiers, split. Output: `<run>/verify.md`. Drop REFUTED, label UNCERTAIN, restore a cut P1 that
  comes back CONFIRMED.
- **Solo runs:** verify yourself, item by item, against the real code.

## Phase 9 — Deliver, remember, close

1. **Deliver.** Write the deliverable to its tracked path, then show the mode's in-chat summary. Any
   questions for the user come **numbered, in the chat, after the summary**.
2. **Remember.** Propose up to 8 memory candidates — Accepted Patterns (intentional code to stop
   flagging; a REFUTED finding that was deliberate design is a prime candidate) and Enforced
   Conventions (always/never rules). **Write them to memory's `## Proposed` section immediately** as
   `- PROPOSED AP: <title> — <one line> (from <run>, <date>)` so they outlive this session. On the
   user's yes, move the entry up with the next number; on no, delete it. **Decisions (D)** are recorded
   only from the user's own words. Memory over ~25 KB → propose a consolidation (merge duplicates, move
   superseded entries to `conventions-archive.md`, which runs don't read).
3. **Close.** In `session-state.md` set `status: complete` and the deliverable path; empty
   `<home>/active-run`. A run stopped for good → `status: abandoned`. **Close every run you open.**

---

## Resume — every phase

- After each phase, **overwrite** `session-state.md` — at most ~40 lines, always in this shape — and
  append anything historical to `<run>/log.md`. The state file is a status board, never a ledger:

```
status: in-progress            # in-progress | complete | abandoned
mode: <mode>
phase: <scope | map | brief | partition | dispatch | collect | synthesize | verify | deliver | close>
updated: <YYYY-MM-DD HH:MM>
size: <solo | squad | full> — <n> seats, est. ~<N>k tokens
code-root: <abs>
deliverable: <tracked path, once known>
seats: <slug ✓ | slug … pending | slug — skipped (reason)>
next: <the very next action>
## Decisions so far
- <approvals, scope answers, user rulings this run>
```

- **After a compaction or in a new session**, the plugin's SessionStart hook flags an unfinished run.
  Re-invoke this skill, read `session-state.md`, and resume at `phase`: don't restart, don't
  re-dispatch seats whose files exist, don't skip the completeness gate.
- An old run the user doesn't want resumed → `status: abandoned`, empty `active-run`.

## Absolute rules

- Map, don't ingest. Workers return one line; the work lives in files.
- One brief on disk; dispatch messages point at it.
- Aggregate before judging. Verify before shipping. Judge gates by exit code.
- Memory: read before, propose after (in the file), the user confirms.
- Close every run you open.
