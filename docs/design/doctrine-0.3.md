# Small Council — stage doctrine and upgrade plan

*Design proposal · 2026-09-15 · targets v0.3–0.5 · status: accepted — 0.3 and 0.4 shipped, 0.5 next*

> **Ruled by the user, 2026-09-15:**
> 1. At most 10 agents per run, verifiers included.
> 2. A `/command` starts runs up to Squad size without asking; Full always asks.
> 3. Build order as recommended: 0.3 first, then 0.4, then 0.5.
> 4. Workers **keep loading the project's CLAUDE.md**; the brief still repeats every hard rule word for
>    word.
> 5. The helper is bash.
>
> **Changed while building 0.3:** Assign now comes *before* Brief, since the brief carries each
> seat's slice and budget. The stages are Convene · Prepare · Assign · Brief · Work · Collect · Judge
> · Challenge · Deliver · Learn.

Built from three sources:
- **A verified audit of this repo** through six lenses. 60 findings were raised; an adversarial check confirmed 47 and threw out 13.
- **22 peer projects and papers**, read from their real source. 148 of 150 checked mechanisms were confirmed. Three sources were never checked; they are marked *unverified* below.
- **Field data from ~50 real council runs.**

---

## 1. How many agents

The council is not a swarm and must not become one.

| | Original (Carmack-Council) | Today (0.2) | This doctrine |
|---|---|---|---|
| Small job | 10 — every seat, always | 0 (Solo) | 0 |
| Typical review | 10 | 3–5 | 3–5 |
| Largest run | 10 | 10 seats + 1–2 verifiers | **At most 10 agents in total, verifiers included**, unless you raise it |

Two research results set that ceiling.

**Agents read and judge in parallel; one hand writes code.**
- Parallel agents pay off on work that splits into independent reads: a review's lenses, a question's lines of inquiry.
- They cost on work that is a chain of dependent decisions, like an implementation.
- The scaling study (Kim et al. 2026) and Cognition's essay reach this conclusion from opposite directions. So seats review, advise and research in parallel, and one builder writes the code.

**More seats is not more coverage.** Overhead grows faster than coverage as agents are added. When coverage is thin, the fix is better slicing and one shared change index, not more agents.

---

## 2. The shape of the council

```
   You ─── rulings ───►  THE CHAIR (the main session)
                          one head · scope · judgment · your rulings · the final text · never deep-reads
                                        │
                   orders on disk  ─────┼─────  one line back, the work in files
                                        │
        ┌───────────────┬───────────────┼───────────────┬───────────────┐
        ▼               ▼               ▼               ▼               ▼
     SEATS — experts recruited for THIS project (council-worker, isolated, read-only)
     each one: a lens · a seat card · principles · surface markers · a severity rubric · a track record
                                        │
                                        ▼
     VERIFIER (council-verifier) — challenges claims and changes; blind to the author's reasoning

     SUPPORT SYSTEMS — mostly scripts, hooks and files, not agents
     recruitment · knowledge base · orders · logistics · ground truth · quality control ·
     continuity · economy · learning · measurement
```

Only **two agent types** are needed. Everything else in section 5 is a script, a hook, or a file.

---

## 3. The eleven laws

1. **One head.** The Chair owns scope, judgment, the user relationship and the final text. Experts own depth. No one else talks to the user.
2. **Parallel readers, one writer.** Seats read and judge side by side; one builder changes code.
3. **Gather once, share with everyone.** The Chair or a script computes, once, anything two seats would both need: the map, the change index, the relevant memory entries, earlier findings on these files. It goes in the brief.
4. **The disk is the memory; the Chair's context is scratch.** Every decision a later stage depends on is written to a file before its stage ends.
5. **Scripts do the mechanics; agents do the judgment.** If a script can do or check a step, a script does it: opening and closing a run, running a gate, counting seat files, checking citations. Models skip prose steps under load. Our field runs were left unclosed and a gate faked a green. Code Gauntlet's orchestrator acknowledged a mandatory step and then skipped it.
6. **Read a stage's doctrine as you enter it.** Rules read at the start of a long run have faded by its end.
7. **Evidence or it didn't happen.**
   - Every claim carries `path:line`.
   - Every "done" carries a gate's output file and its exit code.
   - A builder's explanation is a claim, never evidence.
8. **Aggregate, then judge; judge, then challenge.** The challenger never sees the author's reasoning.
9. **You rule; the council proposes.** Questions come last and numbered, and rulings are recorded in your own words.
10. **Every run is sized, budgeted, reported and closed:** an estimate before it starts, the actual cost after it ends, and a close every time.
11. **The council learns this project.** What it got wrong becomes memory. Each seat keeps a track record that shapes the next roster.

---

## 4. Stage doctrine

Each stage becomes one short doctrine file that the Chair reads when it enters the stage (`references/doctrine/<n>-<stage>.md`). Each mode adds a matching `## At <Stage>` section with its own specifics. The kernel skill (context-core) keeps only the laws, the stage index and the file layout, so it re-attaches whole after a compaction.

How today's 0.2 phases map onto the stages:

| 0.2 phase | Stage |
|---|---|
| (council-init) | 0 Summon |
| Scope & size | 1 Convene |
| Map | 2 Prepare |
| Brief | 3 Brief |
| Partition | 4 Assign |
| Dispatch | 5 Work |
| Collect | 6 Collect |
| Synthesize | 7 Judge |
| Verify | 8 Challenge |
| Deliver, remember, close | 9 Deliver · 10 Learn and close |

### Stage 0 — Summon (council-init, and refresh)

**Purpose:** recruit this project's council and give it what it needs to know.
**Who:** the Chair, plus a mapping squad of up to 4 workers for large repos.
**Produces:** in `.council/`:
- `council.config.md`: the roster (with slugs, lenses, surface markers and paths) and the gates (with probes and side effects);
- a seat card per seat;
- `map.md`;
- the memory file and `.gitignore`;
- the CLAUDE.md pointer.

**Rules**
- **Detect from an inventory, not a list of manifest files.** Count files by extension from `git ls-files`, list config files two levels deep, and see what CI runs. This catches firmware, Xcode projects and notebooks, which a manifest list misses.
- **Recast before you drop**, and drop only when there is nothing for the lens to look at. A thin lens is paired with a neighbour inside one worker rather than getting a worker of its own.
- **Surface markers per seat.** Each seat gets 2–6 globs or greps written in this repo's idioms (`migrations/**`, `APIRouter`, `*.tscn`). Assignment then becomes mechanical, and every skip has evidence behind it. *(Carmack-Council's marker table, pr-review-toolkit's change-triggered agents.)*
- **A seat card per seat, at most ~1.5k tokens.** It holds:
  - its numbered principles, one line each;
  - how each principle applies to this stack, translating the web-stack examples in the inherited docs;
  - the severity rubric for its domain;
  - the known hot spots for its lens.

  Workers read the card first and open the full doc only for principles they cite. *(Carmack-Council's stack-assumption inventory and per-domain rubrics.)*
- **Project-local seats.** A lens the catalog lacks gets a doc drafted from a seat template. Every principle cites repo evidence, and the doc stays `status: draft` until you accept it. *(SkillsBench's gate, unverified.)*
- **Gates carry more than a command.** Each records:
  - a probe: the exact dry-run command;
  - its requirements: tools, environment, credentials, hardware;
  - its side effects: none, writes the tree, network, cost, or hardware.

  A gate with side effects is never probed without asking.
- **Monorepos:** a lens may appear more than once, each copy covering different paths.
- **Record a `stack-fingerprint`** so Prepare can notice when the stack changes.

**Enforced by:** `council doctor`, which checks config paths, probes and the fingerprint; drill D1.
**Done when:** you have confirmed the roster and gates, the files are written, and `last-verified` is stamped.
**Over the original:** the original hard-coded Next.js/tRPC/Prisma markers and ten fixed seats. 0.2 tailors the roster and gates. This tailors the experts themselves, through cards, markers and rubrics, and notices when the stack drifts.

### Stage 1 — Convene (scope, shape, size, approval)

**Purpose:** decide whether to convene, whom to call, and at what cost.
**Who:** the Chair.
**Produces:** the run folder and its `session-state.md` (via `council run open`), and the approval message.

**Rules**
- **Resolve the target.** This is mode-specific: the diff from the merge-base, a plan, or a question.
- **Shape check before sizing.**
  - Can the work split into independent slices, or is it one chain?
  - How many surfaces does it touch?

  A chain means Solo or one builder; work that splits gets seats. *(Kim et al.)*
- **Size it:** Solo, Squad (2–4 seats), or Full (at most 7 seats plus verifiers, 10 agents in total).
- **The approval message shows:**
  - the deliverable;
  - the seats going, and the seats not going with the reason for each *(agentic-council)*;
  - an estimate based on this project's own run history, not a flat 100k per worker;
  - what you'll be asked at the end.
- **The approval threshold lives in the config**, e.g. `approve without asking: up to Squad`. A `/command` approves runs up to that size; a Full run always asks.
- **Test the write path first.** Before any fan-out, confirm that run files can be written. From a worktree, the council home lies outside the session's folder.
- **An open run already on this code root:** ask whether to resume it, close it, or run alongside it.

**Enforced by:** `council run open`, which creates the folder and state, registers the run, and refuses a duplicate.
**Done when:** the run is approved and open.
**Over the original:** the original always dispatched all ten seats without asking. 0.2 added sizing and a confirmation. This adds the shape check, per-project cost, visible skips and the threshold.

### Stage 2 — Prepare (gather once)

**Purpose:** gather every shared fact once, so that no seat has to.
**Who:** the Chair and scripts.
**Produces:**
- `<run>/index.md`, the change index;
- the grounding gate results;
- the memory entries in scope;
- earlier council findings on these paths.

**Rules**
- **The change index** (reviews and fixes). For each changed file it lists the hunks, the changed symbols, callers as `path:line`, the tests that cover it, and any schema or config it touches. It is built by one script in one pass, and every seat reads it instead of re-tracing blast radius on its own. This is the biggest cost cut available: slice reading was about 80k of the ~100k each worker spent.
- **Map:** refresh only the areas whose code moved, with a freshness stamp per area. Keep the map to what the code doesn't say itself: hot spots from history, vocabulary, non-obvious conventions. *(Controlled studies of repo context files are mixed: generic overviews cost steps without a clear gain. Evaluating AGENTS.md, unverified.)*
- **Memory:** read the one-line index of entries, then pull only the entries whose scope matches the paths and seats in play. *(ACE's scoped entries.)*
- **Prior knowledge:** grep the tracked reviews, logs and research for the in-scope paths, and list the hits as ids plus one line each. *(Compound Engineering, feature-dev.)*
- **Author's intent:** one line at the top of the brief, taken from the PR title and body, the plan task, or your own words. *(Anthropic's code-review plugin.)*
- **Grounding gates** run through `council gate` in the background and are judged by exit code.
- **Fingerprint:** if the stack fingerprint has moved, suggest a refresh.

**Enforced by:** `council index`, `council gate`, and `council map status`.
**Done when:** the index, the gate results and the memory selection are on disk.
**Over the original:** the original fed tsc, lint and test results into the brief, which is good, but every seat re-read the same code. 0.2 added the map. This adds the shared index, scoped memory and earlier findings.

### Stage 3 — Brief (orders on disk)

**Purpose:** one set of orders that each seat can act on with no other context.

**Rules**
- **Top:** the deliverable, the author's intent, and the run's one question.
- **Bottom:**
  - the hard rules, lifted from the config and CLAUDE.md;
  - the accepted patterns in scope;
  - the **"not a finding" list**, which seats and verifier share: lines this change didn't touch (unless it newly reaches them), style no rule requires, speculation about possible future changes. *(Anthropic's code-review plugin states it from both sides.)*
- **Middle:** the landscape, a pointer to the change index, earlier findings.
- **A task block per seat, about five lines:**
  - the objective (this seat's version of the question);
  - its key questions;
  - where to start (index entries and markers);
  - its budget and stop rule;
  - its output file.

  *(Anthropic's multi-agent research system.)*
- **Workers still load the project's CLAUDE.md** (your ruling), and the brief repeats every hard rule word for word. The worker contract tells them to ignore any instruction there to start a council mode.

**Done when:** the brief is written and the state is updated.
**Over the original:** one brief with one-line returns was the original's best idea, and it stays. This adds the per-seat task blocks, budgets, intent line and not-a-finding list.

### Stage 4 — Assign

**Purpose:** give each seat exactly its slice.

**Rules**
- **Slices come from surface markers** matched against the index or scope, mechanically. The Chair adjusts; it never guesses.
- **A seat with little surface is paired with a neighbour** in one worker (for example UI and UX together). It is neither dropped nor given its own agent. *(Anthropic research system.)*
- **A slice over ~25 files is split.**
- **The budget follows slice size:** about 15 tool calls for up to 5 files, 30 for up to 15, and 45 for up to 25. `maxTurns` is the hard ceiling.

**Done when:** every in-scope file has an owner and every seat has a budget.

### Stage 5 — Work (the seats) — the worker doctrine

**Purpose:** expert depth, in parallel, without crowding anyone else's context.
**Who:** one council-worker per active seat, all launched in one message. The rules live in the agent file and are not repeated in each dispatch.

**Rules**
- **Reading order:**
  1. the brief: its top, your block, its bottom;
  2. your seat card;
  3. the change-index entries for your slice;
  4. the code.

  Open the full reference doc only for the principles you cite.
- **The seat file is a live progress list.** Write its header first: seat, `ref:`, the question, a coverage checklist. Then update it as you go, so an interrupted worker still leaves usable work. *(Manus's recitation.)*
- **Every item carries:**
  - its title and `path:line`;
  - the principle;
  - a severity on the seat's own rubric;
  - its **origin**: introduced, worsened or pre-existing, from `git blame`;
  - its **basis**: seen or inferred;
  - **refuted if**: the one observation that would disprove it;
  - the fix, in one sentence.

  *(pr-review-toolkit and Code Gauntlet for origin; wshobson/agents for "refuted if".)*
- **An `## Index` block at the top**, one line per item, so the Chair reads the index rather than the prose.
- **Stay in your lane.**
  - Anything outside it goes under `## Outside my lane`.
  - Conflicting evidence becomes one item that shows both sides. *(Anthropic research system.)*
  - At most three `NEEDS RULING` questions for you. *(Spec Kit.)*
- **Keep to the budget and stop rule**, and say what you didn't cover.
- **Read-only, no delegation, one line back.**

**Enforced by:** a **SubagentStop hook** (`seat-gate`). A worker can't finish without a valid seat file: header, `ref:` line, index, item cap, size limit. The hook sends the worker back to fix it. *(Claude Code's SubagentStop hook, aimed at our agent type.)*
**Done when:** the file is valid and one line has come back.
**Over the original:** the original's one-line return with the work in a file stays. This adds seat cards, origin/basis/refuted-if, the live file, the index, budgets and the hook.

### Stage 6 — Collect

**Purpose:** prove every seat reported before anyone judges.
**Who:** a script first, then the Chair.

**Rules**
- **`council collect` prints one row per seat:** state, items, size, whether the `ref:` line matches, whether citations resolve, and tokens spent (taken from the completion notification).
- **Resume a failed seat before restarting it.** Message the same agent id (SendMessage) before re-dispatching from scratch.
- **In-scope files nobody opened** get one bounded extra pass, and only if they sit in a hot spot. *(code-modernization's "loop until dry", capped.)*
- **You can end early.** The Chair synthesizes what has arrived, marks the deliverable PARTIAL, and lists the missing seats.

**Done when:** every active seat is done or has been explicitly ruled out.

### Stage 7 — Judge (synthesize)

**Purpose:** the Chair's judgment, written down.

**Rules**
- **Build the raw ledger first:** one row per raw item, taken from the index blocks, before any merging. *(BMAD's triage, Compound Engineering.)*
- **Merge by owner and by root cause**, keeping every author.
- **Run a conflict pass.** List item pairs that contradict each other or rest on incompatible assumptions. Those that can't be settled from the code become rulings for you. *(Cognition: every action carries decisions nobody specified.)*
- **Rank by concrete cost here** (the Carmack filter), then cut to the cap and keep the cut list.
- **Write `<run>/synthesis.md`:** the kept items with provenance, the cut list with reasons, and the dedupe map. *(Compound Engineering's finish-input file.)*

**Done when:** synthesis.md is on disk.

### Stage 8 — Challenge (verify)

**Purpose:** catch what's wrong before you see it.

**Rules**
1. **Mechanical pre-check (`council check`).**
   - Every cited file and line exists.
   - Every quoted rule appears word for word where it is cited.
   - The claimed origin matches `git blame`.

   Items that fail are dropped or corrected before any agent runs. *(Code Gauntlet's citation check; Compound Engineering's quote gate.)*
2. **Blind verification.**
   - The verifier gets the claim and its location only: not the seat, principle, reasoning or fix. It must trace a live path through the code.
   - Every P1 and every protected subject gets its own verifier. Protected subjects are auth, data loss, injection, secrets, concurrency and public contracts.
   - Everything else goes out in batches of up to 8.

   *(Code Gauntlet's blind challenger; Anthropic's per-issue validators; Compound Engineering's protected subjects.)*
3. **Verdicts:**
   - CONFIRMED.
   - REFUTED.
   - UNCERTAIN.
   - MISCITED: the problem is real but at a different location, so the item is kept with the citation fixed. *(code-modernization.)*

   A protected subject is never dropped for being UNCERTAIN; it ships with that label.
4. **Gates run through `council gate`**, with exit codes recorded as JSON. A failure is read by grepping the saved output, never by reading the whole file.

**Done when:** every shipped item has a verdict and the gates are recorded.
**Over the original:** the original had no challenge step. 0.2 has one verifier reading everything. This makes it blind, one-per-P1 and pre-checked.

### Stage 9 — Deliver

**Rules**
- **Frontmatter:** the deliverable goes to its tracked path with title, areas, tags, date and status, so later runs can find it. *(Compound Engineering.)*
- **Plain words in chat:** what a seat checks comes first and the name second, e.g. "Data integrity (Leach)". No internal labels.
- **Actual cost next to the estimate.**
- **Then, numbered:** the rulings needed (from the conflict pass and NEEDS RULING), the memory proposals, and the next step (fix hand-off, build, or review).

### Stage 10 — Learn and close

**Rules**
- **Memory proposals are in plain words, with evidence and effect.** For example: "stop flagging X in these paths — it's deliberate (evidence: path:line, review <date>)". They are written to Proposed at once.
- **Admission rule:** a proposal must change agent behaviour if removed, and must not restate what the code already says. Check for an existing entry first, and count repeat sightings instead of adding duplicates. *(BMAD's admission rules; ACE.)*
- **A "no" goes to `## Rejected`** and is never proposed again.
- **The seat ledger** gets one row per seat per run: items raised, shipped, refuted, cut, and tokens spent. Refresh reads it to propose roster changes with the numbers shown, and Convene reads it for estimates.
- **Memory over its size limit is consolidated by listed operations** (merge this, retire that), never by a rewrite. *(ACE: whole-context rewrites collapse into uninformative summaries.)*
- **`council run close`** sets the status, stamps the actual cost, and removes the run from the open list.

**Done when:** the run is closed.

### The build loop (council-implement) — the one place that writes code

- **Baseline first:** record every gate before the first edit, so pre-existing failures are known. *(code-modernization.)*
- **Per task:**
  1. Load the governing card or doc.
  2. Capture **before-evidence**: a check that shows the problem or the missing behaviour.
  3. Make the minimal change.
  4. Run the gates.
  5. Capture **after-evidence**.
  6. The verifier judges from the evidence, never from the builder's account. *(skill-creator's grader, Spec Kit's proof rules, cc-sdd's fresh-evidence gate.)*
  7. Log it.
- **Two failed verifications** lead to a clean-context diagnosis before stopping: one fresh worker gets the task, both failures and the diff. *(cc-sdd.)*
- **In session-state:** retry counters and a short "tried and failed" list. *(wshobson/agents; Manus.)*
- **"Notes for later tasks"** go at the top of the log, where a resumed session reads them first. *(cc-sdd.)*
- **One commit per task** is offered in the single confirmation, so each task can be reverted.
- **The run ends with a converge pass:** one verifier checks every task's "Done when" against the final tree. *(Spec Kit.)*

### Plan and research specifics

**Plan**
- Tasks are ordered as vertical slices, with a walking skeleton first. *(Carmack-Council fork.)*
- Each task has a Touches row, listing the files or areas it may change, and a Constraints row with the constraints quoted word for word. *(cc-sdd; Spec Kit.)*
- An optional two-stance design step, used only when discovery finds a real structural choice. *(feature-dev.)*
- A conflict round runs before tasks are grouped.

**Research**
- A single-answer question gets a scout first. *(Kim et al.)*
- A "why" question gets rival-hypothesis lines of inquiry. *(wshobson/agents; agent-teams docs, unverified.)*
- Conflicting evidence is reported with both sides.
- The Chair writes the answer, and the citations stay attached. *(Anthropic research system.)*

---

## 5. Support systems

| System | Its job | Made of | Today | What changes |
|---|---|---|---|---|
| **Recruitment** | Build and maintain the roster; tailor each expert | council-init + catalog + seat cards + seat template | Roster and gates tailored | Cards, markers, rubrics, probes, path-scoped seats, fingerprint, 4 new lenses |
| **Knowledge base** | What the council knows about this project | map, memory index, prior findings, research, seat cards | Map + memory | Scoped memory, Rejected list, anchors, deliverable frontmatter, map of non-obvious facts only |
| **Orders** | Give each seat what it needs, nothing more | brief.md | One brief | Per-seat task blocks, budgets, intent, the not-a-finding list |
| **Logistics** | Open, track, collect, close runs | `council` CLI in the plugin's `bin/` (bash + git, like the hook) | Prose instructions | New: `run open/close/status`, `collect`, `gate`, `index`, `check`, `doctor` — one council-home resolver shared with the hook |
| **Ground truth** | Know what the code really does | gates with probes, exit codes, a baseline | Exit-code rule in prose | `council gate` writes output + JSON; a baseline before builds |
| **Quality control** | Keep wrong claims and bad fixes out | pre-check script + blind verifier + seat-gate hook | One verifier | Blind, per-P1, pre-checked, MISCITED, evidence-based change verdicts |
| **Continuity** | Survive compaction, new sessions, parallel work | SessionStart hook, state files | One active-run pointer | Several open runs, seat states with agent ids, resume by mode, a check that doesn't rely on bash alone |
| **Economy** | Spend where it pays | shape check, budgets, pairing, thresholds, ledger | Flat 100k estimate | Estimates from this project's history, actual cost shown, progress lines |
| **Learning** | Get better at this project | proposals, Rejected, seat ledger, consolidation | Proposals persisted | Evidence and effect on proposals, ledger-driven refresh, memory consolidated by operations |
| **Measurement** | Prove a change helped | evals | Load checks, string checks, hook tests | A behavioural suite with `claude plugin eval`, seeded fixtures scored for precision and recall, verifier calibration, results history |

---

## 6. Upgrade over the original

| Area | Carmack-Council (original) | Small Council 0.2 (today) | 0.3–0.5 (this plan) |
|---|---|---|---|
| Who's on the council | 10 fixed seats for Next.js/tRPC/Prisma, all dispatched every run | Tailored per repo; recast before drop; skips recorded | The experts themselves tailored: cards, markers, rubrics, path-scoped seats, 4 new lenses, a track record per seat |
| The head | Writes the brief, dispatches, merges | + sizing, confirmation, verification, memory, close | Reads each stage's doctrine on entry; mechanics in scripts; judgment written to disk |
| Context | One brief on disk, one-line returns (kept) | + map, memory, one council home, resume | + a shared change index, per-seat blocks and budgets, scoped memory, earlier findings, workers without CLAUDE.md |
| Quality | Completeness gate + tsc/lint/tests | + one verifier on shipped items | + citation pre-check, blind per-P1 verifier, protected subjects, evidence for changes, a seat-file hook |
| Memory | Conventions picked at the end | Proposals written at once; decisions in your words | + index and scopes, Rejected list, admission rule, consolidation by operations, seat ledger |
| Cost | Always ~10 agents, never reported | Solo/Squad/Full with a flat estimate | Shape check, pairing, a threshold, estimates from history, actual cost reported |
| Continuity | None | SessionStart hook, state file, one pointer | Several open runs, seat states with agent ids, resume by mode, resume a stuck worker |
| Fixing | Not covered | Fix mode + a verifier per task | + gate baseline, before/after evidence, clean-context diagnosis, converge pass, per-task commits |
| Proof it works | None | Load checks, 221 string checks, hook tests | Behavioural suite, seeded fixtures, verifier calibration, history per version |

---

## 7. Opinion

- **The foundation is right, and the research confirms it.** The best systems we studied converge on the core the original already had: orders on disk, isolated readers, one-line returns, and aggregating before judging. Those systems are Anthropic's research agent, Compound Engineering, Code Gauntlet and Superpowers. Keep that core.
- **The biggest weakness is not a missing feature: the method lives in prose the model has to remember.** Our field failures and Code Gauntlet's are the same failure. Ours: runs never closed, a faked green, proposals lost. Theirs: a mandatory step acknowledged, then skipped. The fix is structural: scripts and hooks for the mechanics, and stage doctrine read on entry.
- **The experts aren't yet experts in *your* project.** Each reads a generic 300-line doc written for a web stack and re-derives the same context every run. Three things turn a named persona into a project specialist: a seat card, a shared change index, and a track record.
- **We can't yet prove any of this works.** Until there is a behavioural eval suite, every change is a guess, this plan included. It's the part I'd least want to skip.
- **Where I'd push back on the research: don't chase numbers.** Confidence scores, loops that run until nothing new appears, and a referee for every item all multiply agents fast. Anthropic's own code-review plugin dropped its 0–100 confidence cut in favour of per-issue checks. The council's value is judgment per token, not coverage per dollar.
- **Risk:** 0.3 adds machinery, a CLI and a second hook. It has to stay small: bash and git only, every command tested, no daemon, no database.

---

## 8. What we will not copy

| Idea | Seen in | Why not |
|---|---|---|
| A 0–100 confidence score with a hard cut-off | code-review plugin (older version), pr-review-toolkit | Upstream replaced it with per-issue validation; a number invites false precision. We use basis (seen/inferred) plus the blind verifier. |
| Persona theatre: greetings, icons, menus, staying in character | BMAD | Costs tokens and adds nothing; the named expert is a doctrine device, not a role-play. |
| Agent teams for seat dispatch | Claude Code agent teams (experimental) | Interactive-only and experimental; also, never pass `name` to a council agent call or it becomes a teammate. |
| Cross-model peers, vector databases, embedding de-dup | Compound Engineering, wshobson/agents, ACE | Heavy dependencies for a markdown-and-bash plugin. |
| Injecting the full bootstrap into every session | Superpowers | Our hook is silent outside council repos and short inside them. |
| Loop-until-dry and a referee per item, everywhere | code-modernization | Agent counts explode (their own docs expect 10–40 agents); we allow one bounded pass, only in hot spots. |
| Mandatory feature-flag TDD for every behavioural task | cc-sdd | Too heavy as a default; before/after evidence gives the same proof. |
| 50–70 KB skill files full of edge cases | Code Gauntlet, Carmack-Council | Rules past the first ~5k tokens drop after compaction; logic belongs in scripts. |
| "Always at least three subagents" | Anthropic research system (web research) | Tuned for web search, where a subagent is cheap; code reading isn't. |

---

## 9. Implementation plan

### 0.3 — Discipline (highest leverage; mostly mechanical)

1. **`bin/council` CLI** (bash + git). Subcommands:
   - `run open`, `run close` and `run status`;
   - `gate`, which saves the output and writes JSON with the exit code;
   - `collect`, `check` (citations and quotes), `index` (the change index), `doctor`;
   - one council-home resolver, shared with the hook.
2. **The SubagentStop `seat-gate` hook**, for council-worker and council-verifier.
3. **A slim context-core kernel** plus `references/doctrine/` stage files.
   - Modes get restructured by `## At <Stage>`.
   - Resume re-invokes the mode, not just the core.
4. **Several open runs:** the hook scans `runs/*/session-state.md` instead of one pointer, and seat states carry agent ids.
5. **Worker contract v2:**
   - an index block, and origin/basis/refuted-if on every item;
   - the live seat file and a budget.
6. **Brief v2 and the challenge step:**
   - task blocks, the intent line and the not-a-finding list in the brief;
   - `synthesis.md`;
   - the blind per-P1 verifier.
7. **What you see:** the approval threshold, visible skips, progress lines, actual cost, plain labels, partial delivery.
8. **Evals:**
   - split run_structural into blocking structural checks and advisory phrase checks;
   - tests for the CLI and seat-gate hook.

### 0.4 — Tailored experts

1. **Seat docs restructured:** a principles core, an "Applying this seat to another stack" section, and the origin-stack examples moved to a section at the end. Performance's principles get renumbered to match the others.
2. **Init v2:** inventory detection, surface markers, seat cards, gate probes and side effects, path-scoped seats, the fingerprint, and a seat template for project-local docs.
3. **Four new stack-agnostic lenses:** accessibility, concurrency and runtime, untrusted input and bytes, operability.
4. **Memory v2:**
   - an index with scopes and anchors;
   - the Rejected list, the admission rule, consolidation by operations;
   - earlier findings in the brief and frontmatter on deliverables.
5. **The seat ledger**, plus refresh proposals backed by its numbers.

### 0.5 — Proof and build quality

1. **A `claude plugin eval` suite:**
   - sizing cases that stop at the proposal, so they're cheap;
   - triggering cases with near-miss queries;
   - seeded fixtures scored for precision and recall, with the answer key kept outside the fixture;
   - a verifier calibration case and a compaction-resume case;
   - saved results per version.
2. **Implement:** the baseline, before/after evidence, the clean-context diagnosis, the converge pass, notes for later tasks, per-task commits.
3. **Plan and research upgrades** (section 4).
4. **test-architect's fix mode** gets a verifier check.

### Later, optional

- A shipped Workflow dispatch script, used where the Workflow tool exists. It makes fan-out deterministic and resumable, and it must write the same seat files.
- Model tiers per spawn site.

**Each release is gated by:** validation, structural checks, the hook and CLI tests, and, from 0.5, the behavioural suite compared with the previous version.

---

## 10. Decisions for you

1. **Agent cap:** is at most 10 agents per run, verifiers included, right? Or lower?
2. **Approval threshold:** runs up to Squad start straight away on a `/command`, and Full always asks. Agreed?
3. **Order:** 0.3 (discipline) first, as recommended, or 0.4 (tailored experts) first?
4. **Workers without CLAUDE.md:** this is cheaper and cleaner, but it means the brief must carry every hard rule. Agreed?
5. **Helper CLI in bash:** it works wherever Claude Code's Bash tool works. Or would you prefer Python?

---

## Appendix A — Peers studied

| Peer | What it is | Best idea for us | Source |
|---|---|---|---|
| Anthropic multi-agent research system + context engineering | Engineering posts on Claude's Research feature | A per-subagent task block: objective, key questions, starting points, budget, stop rule | anthropic.com/engineering/multi-agent-research-system |
| Manus + Cognition | Practitioner essays | A live progress file that recites the goal; every action carries unspoken decisions, so run a conflict pass | manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus · cognition.com/blog/dont-build-multi-agents |
| Towards a Science of Scaling Agent Systems (Kim et al.) | Controlled study of multi-agent layouts | A shape check: fan out only on work that splits | arxiv.org/abs/2512.08296 |
| Agentic Context Engineering (ACE) | Paper + code on evolving playbooks | Consolidate memory by itemized operations, never by rewriting | arxiv.org/abs/2510.04618 |
| Evaluating AGENTS.md (ETH SRI) — *unverified* | Controlled study of repo context files | The map holds only what the code doesn't say; measure it | arxiv.org/abs/2602.11988 |
| SkillsBench — *unverified* | Paired with/without-skill benchmark | Measure lift, not just pass rate; compact core docs with examples on demand | arxiv.org/abs/2602.12670 |
| code-review plugin (Anthropic) | Multi-agent PR review command | Per-issue validation; a shared "not a finding" list; quote the rule a finding rests on | github.com/anthropics/claude-plugins-official/tree/main/plugins/code-review |
| pr-review-toolkit (Anthropic) | Six single-lens review agents | Choose specialists from what changed; tag findings as introduced vs pre-existing | …/plugins/pr-review-toolkit |
| feature-dev (Anthropic) | Phased feature workflow | Carry "read first" files into the build; ask clarifying questions after exploring | …/plugins/feature-dev |
| code-modernization (Anthropic) | Legacy modernization workflow | MISCITED verdict; baseline every gate before editing; "built" requires "the build ran" | …/plugins/code-modernization |
| skill-creator (Anthropic) | Eval-driven skill authoring | A grader that puts the burden of proof on the claim; cheap evals that stop at the proposal | github.com/anthropics/skills/tree/main/skills/skill-creator |
| Claude Code plugin evals + workflows (docs) | Platform capabilities | `claude plugin eval` with/without comparison; a SubagentStop hook to enforce the seat file; `omitClaudeMd` | code.claude.com/docs/en/plugin-evals |
| Claude Code agent teams (docs) — *unverified* | Experimental multi-session mode | Don't use it for dispatch; resume a worker by message | code.claude.com/docs/en/agent-teams |
| Superpowers | Skills methodology library | Scripts build review packages; reviewers can't be talked down; trigger-only descriptions | github.com/obra/superpowers |
| Compound Engineering (Every) | Plan → work → review → compound | Prior learnings found by frontmatter; protected subjects; the Chair finishes from a file on disk | github.com/EveryInc/compound-engineering-plugin |
| Code Gauntlet (Liatrio) | Adversarial multi-agent review | A blind challenger; a deterministic citation and origin check; mandatory steps moved into code | github.com/liatrio-labs/claude-code-gauntlet |
| Spec Kit (GitHub) | Spec-driven development kit | A converge pass after building; a cap on open questions; prompt text tested like code | github.com/github/spec-kit |
| BMAD Method | Agentic agile framework | A raw-finding ledger before dedupe; admission rules for what enters project context | github.com/bmad-code-org/BMAD-METHOD |
| cc-sdd | Kiro-style spec workflow | A clean-context diagnosis after two failures; notes for later tasks; a fresh-evidence gate | github.com/gotalab/cc-sdd |
| wshobson/agents | Large subagent marketplace | "Refuted if" on every finding; a drift doctor whose every finding has a fix line | github.com/wshobson/agents |
| agentic-council | Deliberation plugin | Show the seats not called, and why, in the approval | github.com/dtsong/agentic-council |
| Carmack-Council (upstream) | Our origin; unchanged since March 2026 | Per-domain severity rubrics; the stack-assumption inventory; walking-skeleton planning (a fork) | github.com/SamJHudson01/Carmack-Council |

## Appendix B — Where each confirmed audit finding lands

- **Instruction clarity:** IC-1 resume loads only the core → Continuity (resume by mode) · IC-2 no synthesis file, verifiers overwrite each other → Stages 7–8 · IC-4 map refresh → Stage 2 · IC-5 principle vs severity labels → 0.4 seat docs · IC-6 init's mapping squad undefined → Stage 0 · IC-7 worktree permissions → Stage 1 write check · IC-8 one active-run pointer → several open runs.
- **Evaluation:** EV-1 phrase checks → split structural · EV-2, EV-3, EV-9 → the behavioural suite, seeded fixtures, history · EV-4 → verifier calibration · EV-5, EV-8 → the seat ledger · EV-6 → the Rejected list · EV-10 → renumbered principles.
- **User experience:** UX-1 → the approval threshold · UX-2 → proposals with evidence and effect · UX-3 → partial delivery · UX-4 → progress and actual cost · UX-5 → several open runs · UX-7 → per-task commits · UX-8 → verifying test-architect's fixes · UX-10 → plain labels.
- **Adaptability:** SA-1 → seat docs and cards · SA-2 → gate probes and side effects · SA-3 → seat template · SA-4 → path-scoped seats · SA-5 → four new lenses · SA-6 → inventory detection · SA-9 → adaptation evals · SA-10 → the fingerprint.
- **Context economy:** CE-1 → index blocks and a size cap · CE-2 → the change index · CE-3 → budgets and estimates from history · CE-4 → seat cards · CE-5 → the memory index · CE-6 → synthesis.md · CE-7 → `omitClaudeMd` · CE-8 → reading gate output by grep · CE-9 → earlier findings in the brief.
- **Orchestration:** OR-1 → the write check · OR-2 → seat states and live files · OR-3 → synthesis.md plus a verdict-completeness check · OR-4 → several open runs · OR-5 → mode-aware resume that doesn't rely on bash · OR-9 → one home resolver.
- **Thrown out by the adversarial check (13):** IC-3, IC-9, IC-10, EV-7, UX-6, UX-9, SA-7, SA-8, CE-10, OR-6, OR-7, OR-8, OR-10.
