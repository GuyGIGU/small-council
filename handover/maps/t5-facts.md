<!-- Read-only facts map for T5, written 2026-11-16 against claude/t3-task-pack (before #116, #117 merged). Line numbers drift; check before relying on one. -->
# Map of what T5 ("a fresh builder per task") rests on

Read-only map of /home/user/wt-t3 (branch claude/t3-task-pack, HEAD b568ba9). No design. Paths are
repo-relative to /home/user/wt-t3. "chars" = Python len() of the text (what the checks count);
"bytes" = UTF-8. Sources read: docs/design/task-tree.md (sec. 3, 4, 6, "Where it lands", "Decided by the
user"), docs/architecture.md (3, 4, 6, 8), docs/decisions.md.

## 0. The settled text T5 builds on

### D4, whole (docs/decisions.md:20, table "Method")

| Id | Decision | Source | Held by | Supersedes |
| D4 | Parallel readers, one writer: agents read and write only their own seat or verify file, and only council-implement's Chair edits project code. | kernel law 2 | `seat-gate.sh`; agent contracts | |

**Last clause: "and only council-implement's Chair edits project code."** Task-tree sec. 6 (last
paragraph) and docs/design/cleanup-plan.md:201-203 both say T5's branch adds an entry that supersedes
that clause: "one builder at a time edits project code, a builder agent or, for a Solo build, the Chair."
Mechanics of supersede (decisions.md header): new row in the same table, old id in its **Supersedes**
cell, old row's status set to `superseded by Dn`; ids never reused. Next free id: D41 (D40 is the
highest; D39 superseded by D40; ids run D1..D40, D38/D39/D40 out of numeric order in the file).
Only on the user's word (CLAUDE.md). Note D4's first half ("agents read and write only their own seat
or verify file") also rubs: a builder writes project code AND `report-<n>.md`. The supersede must
rewrite the whole sentence, not just the clause. D4 "Held by" cites `seat-gate.sh` and agent
contracts only; no hook stops an agent writing project files today (hooks.json has PreToolUse only for
`Agent|Task|Workflow` and `Bash`, SubagentStop only for `council-(worker|verifier)`).
Kernel law 2 text (skills/context-core/SKILL.md:18): "**Parallel readers, one writer.** Seats read and
judge side by side; one builder changes code." It already says "one builder", so it needs no edit and
the structural pin on its title (evals/run_structural.py:124-128) stays green.

### Decisions T5 rubs against (quoted from docs/decisions.md)

- **D13** (line 34) "A skill stays under 20,000 characters and 500 lines ... a stage doctrine file under
  6,000 characters; the verifier contract under 8,000; a review run's method under 59,407 bytes."
  Held by evals/run_structural.py:238, 744-750, 153-156.
- **D18** (line 44) "Checking: `one per batch` (the default) gives a build one verifier, at converge; a
  second needs the user's go. `per task` verifies risky tasks one by one and batches the rest. A verifier
  judges the Done-when and nothing wider ..." A builder agent is NOT a verifier, so `rounds.batch_check`
  (which only looks at `verify-*` slugs) does not count it; but a fresh builder per FIX round after a
  verifier INCOMPLETE must not be confused with a re-check (`verify-<n>b`).
- **D23** (line 57) "Contract names are frozen: skill, agent and command names, arguments and exit codes,
  run-folder files and TSV columns, event types, config keys ... Renaming one is its own decision with a
  migration." Adding a new name is not renaming, but a new agent name, seat-slug prefix, run-folder file or
  config key becomes frozen the day it ships (see section 9).
- **D35** (line 45) Plan tasks carry Serves/Owner/Rests on; the pack reads them (no conflict).
- **D36** (line 46) "A builder's `NEEDS: <question>` is a correct outcome, recorded `done`, never
  `failed`; ... the Chair may run one probe or research seat a run inside the approved budget and asks the
  user before a second." A builder agent returning NEEDS is the first real caller of this; its seat must be
  recorded `done note="NEEDS: ..."` (repair-loop.md:77-78). Note "one probe or research seat a run" is a
  cap on probe seats, not on builders.
- **D37** (line 74) "... A verifier is never on a weaker model than the builder it checks ... in a build
  the Chair, which builds, counts as a builder." Already implemented both ways in
  src/council/commands/plan_models.py:48-62 (builders = selected seats whose role_of == "builder", plus
  the Chair in a council-implement run). With a builder agent the Chair clause becomes wrong (the Chair no
  longer builds): `verifiers()` line 53-54 adds `inherit` for the Chair whenever mode is BUILD. D37's text
  and references/run/models.md:22 and :34-35 ("A build's builder today is the Chair" / "In a build the Chair
  builds") would need the same supersede-or-amend care. T5's own text (sec. 6) lists this as the third
  reason for T5 ("a build's verifier may not be on a cheaper model than the session's").
- **D38** (line 47) "A build round's report is checked against its diff before the verifier sees either ...
  `council patch save` saves the round's diff (from the run's last saved round, else the commit it opened
  on, to the files on disk) ...". A fresh builder per task inherits this unchanged: rounds are by tree
  (`patches.Round.tree`), not by who wrote.
- **D39/D40** (lines 71-72): estimates per role incl. `builder=` already read (see 2).
- **D7** (line 23) "The user's go is their recorded words (`council state decision="..."`) ... never the
  Chair's words." Used by sec. 6's "until the user's ruling is on record" refusal.
- **D19** (line 53) "Every refusal says what to do next." Every new refusal below must name the command.
- **D20** (line 54) hooks never block on their own fault, never write stdout. Binds any new hook wiring
  for the builder's stop.
- **D24** (line 58) New logic in Python; hooks stay thin bash. **D25** (line 59) behaviour proved by running a
  scenario (evals/run_cli.py or run_hook.py), phrase pins only for document contracts.
- **D12/D17** (lines 28, 43) proof contract (before/after pair, tiers); revert check (part 5) must not
  redefine "what counts as proof" (D17: "The tier sets how much proof, never what counts as proof").
- **D3/D14** prose points down; a mode is thin. Relevant to moving the loop to a reference.

## 1. The builder's contract

### What exists
- `agents/` holds exactly two files: `agents/council-worker.md` (106 lines, 6,623 chars) and
  `agents/council-verifier.md` (134 lines, 7,996 chars). **There is no `council-builder.md` or similar.**
- Frontmatter of the worker (agents/council-worker.md:1-7): `name: council-worker`, `description`, `tools: Read,
  Grep, Glob, Bash, Write, WebFetch, WebSearch` (no Edit), `maxTurns: 60`, `color: blue`. Verifier: same tools,
  `color: red`. scripts/quick_validate.py:160-182 validates every agents/*.md: name == file stem, kebab-case,
  description required, keys limited to PLUGIN_AGENT_KEYS (line 44; `hooks`, `mcpServers`, `permissionMode`
  rejected). A new agent file is discovered by the loader with no manifest edit.
- Worker contract (what it says): a seat of one lens in a clean window; reads brief (3 parts), its reference,
  writes its `seats/<slug>.md` header first, works a slice, items with `path:line` + Evidence state; "**Read-only on
  the project.** Your output file is the only thing you write" (line 90-92); never installs/commits/pushes/
  changes config; "No delegation. Don't spawn subagents or invoke council skills" (93-95); `BLOCKED: <reason>` stop
  (96-98); 60 turns at most (99-102); returns exactly one line `Wrote <output path> — <N> items (...)` (104-106);
  "A hook checks your file when you stop." It has a war-room section (86-... ) a builder does not need.
- Verifier contract: see section 7.
- **How a worker is dispatched today**: references/doctrine/05-work.md:5-35. One message, all Agent calls,
  `subagent_type: small-council:council-worker`; per-invocation `model` parameter from the plan's
  `seat/<slug>/model` row ("a builder, review or verifier seat under `- models:`", 05-work.md:11-12, so the
  doctrine already names a builder seat); never pass `name`; the short dispatch block
  `Seat: <slug> — ... / Brief: <abs>/brief.md / Reference / Doc / Format / Write <abs run>/seats/<slug>.md`;
  then `council seat <slug> running agent=<id>` and on notification `council seat <slug> done tokens=<n>
  tools=<n>` (05-work.md:29-40). **A build never reads 05-work.md**: structural comment at
  evals/run_structural.py:146-147 ("Solo, build and post-game runs never read 05-work.md"), and council-implement
  replaces stages 3-7 with its loop. A build's dispatch of the verifier is spelled in the implement skill itself
  (SKILL.md:127-139) and the diagnosis worker in references/run/repair-loop.md:123-135 (a council-worker with
  `ref: none`, dispatch message is its whole brief, writes `seats/diagnose-<n>.md`, run-plan role `diagnosis`).
  So the nearest precedent for "a worker-type agent in a build" is the diagnosis worker, and it is read-only.
- **The standing builder rules already exist as a reference written for a builder seat**:
  references/run/builder-rules.md (31 lines, 2,234 chars): "The rules every build task carries, whoever builds
  it: the Chair, or a builder seat." Rules 1-11 incl. 10 "**Start no agent.** One hand writes code: a builder
  dispatches no agent and invokes no council skill", 11 "End with the report head, or a `NEEDS:` line.", 2 "No
  commit, branch or stash ... The Chair commits a finished task when the user allowed commits (council-implement,
  step 8)", 1 "Work in the code root only". Linked from every pack (src/council/commands/context.py:19,
  :178-179), never copied.
- **The report contract also already says "or a builder seat"**: references/run/builder-report.md:37 "The
  builder is the Chair today, or a builder seat."; head (lines 41-51), "When the builder stops instead" (59-66:
  returns one line `NEEDS: <question>` or `NEEDS: fix <file:line> · does: <...> · should: <...> · seen: <...>`
  and writes no round), checks table (73-79), saved files (86-94: `T<n>-<r>.patch` "which `git apply -R`
  reverses", `T<n>-<r>.json`, `T<n>.md`). 63 lines, 4,262 chars.
- Frozen names a builder would use already shipped: `report-<n>.md` (architecture sec. 4 row: "the builder,
  at each round of task n"), `patches/`, `NEEDS:` line formats, `- models: builder=` and `- estimates: builder=`
  (sec. 2 below).

### What a builder contract would still need (facts only)
- An agent file with edit tools (task-tree sec. 6: "a new agent file with the edit tools a worker does not
  have"): `Edit`/`Write` of project files; `Bash` for gates; a turn limit. Nothing exists for it.
- The agent type string `small-council:council-builder` appears nowhere: agent_gate.KINDS
  (src/council/commands/agent_gate.py:28) maps only the two existing types; hooks/agent-gate.sh:62
  hard-codes `ty != "small-council:council-worker" && ty != "small-council:council-verifier"` and the file
  regex at line 67 (`seats/...md` for worker, `verify-...md` for verifier); hooks/seat-gate.sh:46-50 and
  hooks/hooks.json SubagentStop matcher `^small-council:council-(worker|verifier)$` cover two kinds. A new agent
  type is touched in all five places (section 2).
- Size/limit for a new agent file: none pinned. evals/run_structural.py:749-750 pins `worker` and `verifier`
  only at 8,000 chars; a new file has no cap unless one is added.

## 2. The build seat and its refusals

### Owners today
- `council seat <slug> <state>`: src/council/commands/seat.py (200 lines, 11,131 bytes; longest fn `main`
  37 lines, ratchet evals/ratchet.json). States `queued|running|done|failed|blocked|skipped` (seat.py:17). Slug
  regex `[A-Za-z0-9._-]*` (:18). Fields `agent= tokens= agents= tools= note=` (:15, :110-111). `ROLES` set at
  :19-20 already contains `"builder"` (rejected as an `agent=` value: "is a role, not an agent id").
- What `running`/`queued` refuse today (`_may_record`, seat.py:138-160): `plan.require(run, "start seat <slug>")`
  (:154); the run plan must mark the seat `selected` (:155-157); then `rounds.batch_check(run, slug, home)` or
  `rounds.check_round(run, slug)` (:158). Both in src/council/commands/rounds.py (147 lines) look only at slugs
  starting `verify-` (`_building`, rounds.py:45-51, and only when the run's mode is council-implement). **No
  refusal exists for a `build-<n>`, `task-<n>` or any other builder slug**: no "one build seat at a time", no
  "task depends on a NEEDS: fix task". `done` refuses a seat with no file only for a verifier
  (`verify-*` -> `verify-<n>.md`, re-checks `verify-<n>[a-z].md`) or a seat listed in brief.md
  (`out:`) (src/council/records/seat_write.py:28-40, `missing_file`; seat.py:140-144). A builder not in
  brief.md returns '' there, so **`council seat build-3 done` is accepted with no report file today**.
- seats.tsv columns (frozen, architecture sec. 6 "every TSV's columns"; src/council/records/seat_write.py:11):
  `slug  state  agent  tokens  updated  note  agents  reported`. usage.tsv: `at seat agent kind runs tokens`.
  agent-starts.tsv: `at tool session`. States are only the six above. A NEEDS return is a `note=` cell on a
  `done` seat (repair-loop.md:76-78; read back by tree.py `_needs`, below).
- Events: `seat.updated` (seat.py:197-199) carries `tokens=;agent_runs=;reported=`. Event types are a frozen
  contract (references/run/event-stream.md).
- Slug-prefix knowledge scattered in readers: records/usage.py:105 and records/ledger.py:131
  `startswith(("verify-", "diagnose-"))` (those two prefixes are the "verifier" bucket in totals; every other
  slug is a "worker", so a builder's tokens land under `workers` in `usage_totals`); views/status_names.py:34
  names prefixes `verify-` -> Verifier, `diagnose-` -> Diagnosis, `task-` -> Task (a `build-` prefix would
  read as plain "Build 3" via the generic words fallback); records/seat_write.py:30. ledger.record
  (ledger.py:121-140) writes one ledger row per non-verifier executed seat and counts raised items from
  `seat_files.out_path(run, slug)` (the seat's file under `seats/`): a builder seat with no `seats/<slug>.md`
  gets 0 raised. references/run/run-accounting.md:11 already lists `task-4` as an example seat slug.
- **Slug mismatch to settle**: task-tree sec. 6 names the seat `build-<n>`. `tasks.number` (src/council/records/
  tasks.py:54-57, regex `(?:[Tt](?:ask-?)?)?([0-9]+)`) matches only `3`, `T3`, `task-3`. tree.py `_needs`
  (src/council/commands/tree.py:92-105) attributes a seat's `NEEDS:` note to a task through `tasks.number(slug)`,
  so a `build-3` seat's NEEDS note would be listed under "NEEDS: from seats whose slug names no task of the plan"
  (tree.py:49-51), not on T3's line. Either the slug is `task-<n>` or `tasks.number`/tree learn `build-`.
- Agent gate: src/council/commands/agent_gate.py (290 lines, longest fn `dispatch_refusal` 38):
  - `KINDS` line 28: the two agent types. `check()` (64-98) runs `gate_writable.refusal(KINDS.get(type), ...)`,
    `hunting(...)`, `dispatch_refusal(...)` (219-256), `workflow_refusal(...)`, then `stops(...)` (the agent
    cap/ceiling stop, with `count_start` writing `agent-starts.tsv`).
  - `dispatch_refusal` (219-256): a Small Council agent (kind in KINDS) goes out only for an open run and a seat
    that run's plan selects (`seat_runs`/`plan.selected`, :196-212; `_unplanned` :275-290); then
    `rounds.batch_check or rounds.check_round` for the picked seat (:254-256). For `kind is None` it returns
    None, so **an agent of any other type is not gated at all except by the cap**.
  - `gate_writable.refusal` (src/council/commands/gate_writable.py:10-25): refuses while the council home or the
    named run folder is not writable from this session; applies to `kind` not None.
  - Hook layer: hooks/agent-gate.sh (152 lines) reads the call and runs `council cap check`; type allow-list at :62.
    hooks/seat-gate.sh (226 lines, SubagentStop): "A council agent may not finish without the file its contract
    requires" - blocks once (exit 2) when the reply names no `Wrote <path>.md` or the file is missing/malformed;
    second stop always passes (`stop_hook_active`); `BLOCKED:` replies pass; lines 46-50 choose kind
    worker|verifier from `agent_type`, other types `exit 0`. **"The seat gate covers the builder as it covers a
    worker: no report file, no stop" (sec. 6) is therefore NOT true of a new type until seat-gate.sh and the
    hooks.json matcher add it**, and the gate's reply pattern is `Wrote <path>.md`, while a builder returns a
    `done`/`NEEDS:` line (builder-report.md:59-66) and its file is `<run>/report-<n>.md` at the run root.
    D20 holds: the hook must let through anything it cannot read.
- Run plan (src/council/commands/plan_check.py 357 lines; contract references/run/run-plan.md): seat rows
  `seat/<slug>/disposition|role|context|tool-calls|model|purpose`, `role` in `chair|worker|verifier|diagnosis`.
  Size rule: Solo selects no delegated agents, Squad >= 1, Full >= 4 (run-plan.md "Exactly one Chair ...").
  A builder-agent build is therefore at least Squad; sec. 6's "A build of one small task: the Chair still, when
  the size proposal says Solo" matches this. Models: plan_models.role_of (plan_models.py:19-27) already maps a
  build's `role=worker` (purpose not mapping/survey) to model role `builder`; `verifiers()` (48-62) already compares
  each selected verifier with each selected builder seat's model. Config: `- models: builder=, review=, verifier=`
  (records/models.py ROLES, line 19; template references/templates/council.config.md:17,43) and
  `- estimates: ... builder=450k ...` (records/estimates.py: ROLES line 15, `WORKERS = {"implement": "builder"}`
  line 16; `mode_roles("council-implement") == ("builder","converge")`; template :50; docs adaptive-routing.md
  :106-110). So **model/estimate plumbing for a build's builder agents exists and is tested** (tests/py/
  test_plan_models.py, test_models.py, test_estimates.py; evals run_cli groups `models`).
- `council gate --seat <slug>` already exists (src/council/commands/gate.py:42-52, `_top` :90-99; default seat
  `chair`, gate.py:76): "the seat running this gate in its own tree (a builder in its worktree)". It records
  `"seat"` and `"tree"` in a configured gate's verdict. It is for the held parallel-builder case (#63) but a
  builder seat can pass it today. build-proof.md:59-62 already allows `before-<id>` with "a builder's name,
  such as `before-b7-flip`" (PROOF_ID, gate.py:112-114).
- Rounds: src/council/commands/rounds.py - `check_round` (third check of a task needs a `diagnose-` seat or the
  user's go; `verify-<n>` only), `batch_check` (D18 one verifier per batch), `third_fix_round` (:91-108; by files,
  asked by `patch save`), `decisions_since(run, since)` (:39-42, the user's-go reader, reusable for "until the
  user's ruling is on record"), `local_minute`. No builder-seat rule.

### What sec. 6 asks "in code" and the state of each
1. `council seat build-<n> running` refused while another build seat is running: **not built** (only the
   `_may_record` hook point, seat.py:153-160, and `rounds` exist to plug it into; `seats.rows(run)` gives the
   other seats' states).
2. ... and for a task that depends on a task stopped by `NEEDS: fix` until the ruling is on record: **not built**.
   Pieces that exist: `tasks.depends(cell)` (records/tasks.py:78), `tasks.read`, `task_slice.plan/cut`
   (commands/task_slice.py), seat `note` `NEEDS: fix` on a `done` seat (read by tree.py:92-105), and
   `rounds.decisions_since`. "Rests on the same code" (skill SKILL.md:297-300, "stop ... every task that depends
   on it or rests on the same code") has no machine reader; only `Depends on` does.
3. "When a build seat starts, a tree that differs from the last saved round is named, file by file": **not built**.
   Pieces: each saved round keeps `tree` (records/patches.py Round.tree; patch.py:56 `tree = git.files_tree(top)`
   and :71-74), `patches.rounds(run)[-1].tree` is the last saved round's tree, `git.files_tree(top)`
   (src/council/git.py:50) computes the tree now (every file on disk, ignored and `.council/` out), and `patch.py`
   `_start` (:92-103) already picks "last saved round, else `start-head`'s tree". `diff.files` (src/council/diff.py)
   parses a diff into files. Nothing prints the difference yet; the nearest print is `patch save`.
4. Seat gate covers builder: not built (see above).
5. Contract file + loop reference: not built (sections 1, 4).

## 3. The tree check

- `council tree`: src/council/commands/tree.py (105 lines, longest fn `lines` 20), tests via evals/run_cli.py group
  `requests` block `requests_task_tree`. Pure print, exit 0; `cli.takes_flags(args, "tree")`, `cli.no_words`.
  Reads, only through `records/` and `task_slice`:
  - `task_slice.plan(run, "tree")` -> the `input=` plan's text (refuses with no `input=` or an unreadable plan,
    task_slice.py:56-68, message names `council state input=<plan>`); `tasks.read(content)` -> Task(number, title,
    line, rows) with rows `serves`, `owner`, `rests on`, `depends on`, `touches`, `done when`, `constraints`;
  - ask.md's `## In your words` via `request.ask_words` (tree.py:55-62);
  - `gates.results(run)` (records/gates.py:42-63: name, exit, seconds, when, command, note, proof, void) for
    `before-<n>`/`after-<n>` pass|fail (tree.py:75-77, :67);
  - `patches.rounds(run)` count per task (tree.py:38-40);
  - the build log's Converge table via `converge.read(run, deliverable)` (tree.py:80-89) for met/partly/not met/
    blocked;
  - `seats.rows(run)` notes starting `NEEDS:` mapped through `tasks.number(slug)` (tree.py:92-105).
  Line shape (tree.py:69-72): `T<n> <title> · rests on <k> facts · proof: before-<n> pass, after-<n> pass ·
  rounds: <r> · verdict: <v> [· NEEDS: ...]`. Groups by Serves quote.
- A check on it could refuse (all derivable from the same readers, none exists): a task with a saved round but no
  seat/gate; a `NEEDS: fix` seat with a dependent task whose proof/round exists (via `tasks.depends`); a tree on
  disk that differs from `patches.rounds(run)[-1].tree` (needs `git.files_tree`, which `tree.py` does not call
  today; `tree.py` imports no git). `council check` (src/council/commands/check.py, 234 lines) is the existing
  "check that finds problems" command (exit 1) and already has a build-only branch `Check.proofs()` (:176-184);
  `council tree` has no exit-1 path and is documented as "printed, never checks" (architecture sec. 8 row "Print
  the task tree").
- Sec. 6 wording: "The helper already keeps the tree at the end of each saved round." True: `Round.tree` in every
  `patches/T<n>-<r>.json`. Gaps: round 1 has no earlier round (base = `start-head`'s tree, patch.py:96-103, and
  `--base` override); a seat that edits between a saved round and the next builder start is exactly what the
  diff would name; gates that write non-ignored files also change the tree (gate_run.py `_tree` :136-145 notes
  "the files changed while it ran"), so a tree-differs check will see those as false "outside a round" edits.
- Commits: the tree is files on disk, not HEAD, so a per-task commit (skill step 8) does not change it.

## 4. The implement skill's loop

skills/council-implement/SKILL.md: **304 lines, 19,878 chars (20,062 bytes)**. Limits 20,000 chars / 500 lines
(evals/run_structural.py:744-745): 122 chars of headroom, 196 lines. So T5 cannot add text here without moving
text out first (task-tree sec. 6: "the skill ... is at its size cap").

Line map (measured; chars include newline):
| Lines | Section | chars |
| 1-33 | frontmatter, intro (line 8 "One builder, one task at a time, in this window. Parallel agents read; one hand writes code."), line 14-15 "You dispatch only verifiers ... and at most one diagnosis worker per stuck task.", Carmack, hard rules | - |
| 22-33 | Three kinds of input (plan / review fix mode / post-game) | - |
| 34-59 | At Convene (read, order, safety net, approval, open run, rulings) | - |
| 61-89 | At Prepare, the baseline (line 86-89: "Before changing code, make sure the run plan names the inline Chair and expected verifiers ... `council state phase=build`") | 2,034 (61-90) |
| **91-158** | **The build loop - for each task (8 numbered steps)** | **4,940** (68 lines) |
| 160-197 | The log template (`## Task <n>` block, Shortcuts, Converge, Post-game line) | - |
| 199-216 | At Challenge - converge | - |
| 218-291 | At Deliver - the receipt (seven lines at 220-231), open items, freeze, fetch, post-game offer | 3,899 (218-269) |
| 293-304 | Edge cases (line 297-300 `NEEDS: fix` rule) | - |

Loop steps (SKILL.md line : chars): 1 orders `council context build task-<n>` (93-96) + 2 before-evidence
(97-101) + 3 plan the change (102) + 4 implement (103-107) = 1,101; 5 gates (108-121) = 1,188 (incl. repair
loop and "third failed execution blocks the task"); 6 report + `council patch save <n>` + after-evidence
(122-126) = 397; 7 adversarial check, verifier dispatch and verdict handling (127-150) = 1,659; 8 log and
state, commit (151-158) = 560.

Which steps are the *builder's* under sec. 6's table ("Before gate, the change, the gates, the report,
`council patch save`, after gate"): steps 2-6 (lines 97-126, ~2,700 chars) plus the first half of 1. What
stays with the Chair: step 1's "add only judgement", step 7 (verifier dispatch and verdicts), step 8 (log,
state, commit), and the Edge-cases stop. So the movable block is lines ~97-126 and the builder-side halves of
step 1/5; moving 2-6 would free about 2,700 chars and ~30 lines.

Where it could move: references/run/ (architecture sec. 3: "The run's contracts, records and procedures, read
by the Chair, the helper and the scripts"). Existing neighbours there and their sizes (chars/lines):
repair-loop.md 9,929/135 (already holds "One task, one gate, at most three failed attempts", The log, Unknowns,
Fix rounds, The diagnosis worker); builder-report.md 4,250/63; builder-rules.md 2,234/31; run-plan.md 8,752/120;
helper-commands.md 15,992/48 (no cap pinned for run/*.md; only code is ratcheted). A new
`references/run/builder-loop.md` (name free) is the natural home; D3/architecture sec. 6 says a new run
contract goes in `references/run/` with "the reader and the writer in the same branch". CONTRIBUTING.md is
the place that says how.

Phrase pins in evals/run_structural.py that read text INSIDE lines 91-158 and would break (or need re-homing
to the new reference) if that text moves (D25 says these are document contracts only): 
- :138-141 words "Before-evidence", "After-evidence", "clean-context diagnosis", "converge", "council gate --all",
  "small-council:council-verifier", "diagnose-<n>.md", "verify-<n>b.md" (line 404-408 list);
- :178-190 repair pins: `"council repair record"`, `"repair-loop.md"`, `"do not attempt steps 6–7 as a fix path"`,
  `"only if the task is not blocked"`, `"commit only a task whose mandatory gates pass"` (those three are in steps
  5, 6, 8);
- :482-491 `"risk class"` after `Dispatch \`small-council:council-verifier\` with:`, `"per task only"` (step 7),
  `"light tier"`;
- :511-512 `` "`council context build task-<n>`" `` and `` "resume from `council tree`" `` in the skill (steps 1 and 8);
- :497-500 `"carry on with the tasks that do not rest on it"` (Edge cases, stays), plus the NEEDS: fix phrases (Edge cases).
Also evals/run_phrases.py:48 ("Not proved:") reads the receipt (Deliver, unchanged).

Where the loop is read elsewhere: kernel/context-core never copies it; the skill's line 9-11 says "run: stages 1-2
with this file's sections; the build loop below, in place of stages 3-7; then stages 8-10." The verifier's
brief shape is in step 7 (127-136). architecture sec. 8 and run-accounting.md list `verify-<n>`, `diagnose-<n>`.

## 5. A revert check (undo the fix in a scratch copy, rerun the test, expect it to fail)

**Nothing does this today.** What exists, all by *recorded runs*, never by re-running with the change removed:
- `council gate before-<n> -- '<cmd>'` / `after-<n>`: src/council/commands/gate.py (247 lines); runs the command
  in the code root (`_top` :90-99), saves `gates/<name>.txt` and `.json` (src/council/commands/gate_run.py:101-134;
  fields in section 6). `--proof change|preserve` (gate.py:102-114) and `--invalid "<why>"` (:178-198) mark a
  before-check whose red proves nothing. `execute(top, base, command, out, limit)` (gate_exec.py:56) takes the
  directory to run in, so a command can run in any folder.
- `council check` build branch: src/council/commands/check.py `Check.proofs()` (:176-184) -> check_proofs.proofs
  (src/council/commands/check_proofs.py, 159 lines) -> `status(before, after, number)` (:69-94): verdict `ok`
  (change: before exit != 0, after exit 0, same command), `preserved`, `BEFORE-PASSED` (change proof whose
  before-gate exited 0), `AFTER-FAILED`, `DIFFERENT-COMMAND`, `DIFFERENT-PROOF`, `INVALID-PROOF`,
  `BEFORE-FAILED`, `MISSING-OUTPUT`, `NOTHING-RAN` (`_ran_nothing` :59-66), `NO-BEFORE`, `NO-AFTER`,
  `NO-PROOF-YET` (`void()` :40-52: invalid, timed out, exit 127, missing Python module). Then
  `proof_reach.test_path(top, command)` names the saved test (note "test saved: <path>" / "couldn't confirm a
  saved test"; src/council/commands/proof_reach.py) and `run_folder_only` notes a proof that ran only
  `.council/runs/` scripts (:111-114 of check_proofs). Table written to `<run>/check.md`; closing line
  `check: N of M fix(es) proved ...` (:142-159).
- references/build-proof.md (175 lines, 11,774 chars; no size cap on it): "Choose the mode" (change vs preserve),
  "Record the pair" (41-68), "Tiers" (77-94; light = pair only for risky tasks), "Checking" (96-142), "Read the
  result" (144-175) - and states the limit itself: "The helper compares recorded modes, commands, exits and
  outputs; it cannot tell whether a red change check failed for the intended reason, a test exercises the path,
  or assertions were weakened. The independent verifier must inspect those facts" (171-173). That gap is
  exactly what a revert check would close mechanically.
- The saved round: `patches/T<n>-<r>.patch` is the round's diff and "`git apply -R` reverses" it
  (builder-report.md:86-87); `T<n>-<r>.json` keeps `files`, `tree`, `base`; `git.files_tree` and `git.run/output`
  (src/council/git.py:14-34) are the git primitives; `diff.files` splits a diff by file. `patch.py` already pulls
  `git diff --binary ... start tree -- :(top) :(top,exclude).council`.
- Where a revert step would plug in (facts): (a) as a new row kind in `check_proofs._one` (:97-121) after a
  proof reads `ok`, since `Tally`/`Row`/`summary` and check.md's rows are built there; (b) as a flag or step of
  `council patch save` (it holds the diff and tree at the moment the builder's round arrives), whose frozen
  checks list is `patch_checks`/`_problems` (patch.py:106-129); (c) as a command of its own in
  `dispatch.COMMANDS` (architecture sec. 7: "A new command ... a module in src/council/commands/ and its row in
  `dispatch.COMMANDS`; help text, references/run/helper-commands.md, a scenario in evals/run_cli.py").
  The command to rerun is `verdicts.command(after)` (records/verdicts.py:33-35); the scratch copy needs source
  files only (what `files_tree` names); tests that need an untracked/ignored build dir would not be in the tree.
  `bench.py` has its own `copy_project`/`unittest_run` (evals/bench.py:250, :258) but that is evals code, not
  production.
- Exit-code contract (architecture sec. 6): 0 ok; 1 a check found problems; 2 refusal/usage; 4 nothing checked;
  124 timed out; 97 code root unreachable. A revert check's "expected to fail" result must map onto these
  without a new code (D23) - a green rerun after revert is a "check found problems" (1) in `council check`.

## 6. Receipt lines ("Checked by machine", "Not proved") and gate records

**Who writes receipts today: the Chair, in prose.** No helper command, no src/ code writes any receipt line
(`grep -rni receipt src` hits only src/council/records/closing.py:39, a sentence in a close warning).
- Definition: skills/council-implement/SKILL.md:218-247 ("At Deliver - the receipt", the seven lines in a fenced
  block at 223-231: `Built:`, `Works?:`, `Checked by machine:`, `Shortcuts I took:`, `Not proved:`, `Left open:`,
  `Cost:`). `Checked by machine:` is "<the gates' verdict line, baseline -> now> | <the helper's own NOTHING WAS
  CHECKED line, quoted> [· <the standing red-baseline clause>]" (226); `Not proved: <what nobody actually checked>
  | nothing` (228); the baseline clause (SKILL.md:81-84). Doctrine: references/doctrine/09-deliver.md:26-33
  ("A mode that changed code carries one line, as written: `Checked by machine:` followed by the gates' verdict
  line ... or ... NOTHING WAS CHECKED line quoted"). Config template mentions "one line each in the receipt"
  for fix-now items (references/templates/council.config.md:37). build-proof.md:90-92 says `check.md` "so the
  receipt carries it". Pins: evals/run_structural.py:141-143, :409-412; evals/run_phrases.py:48.
- Where the helper text the Chair copies comes from: `gate --all`'s summary line `gates: N ran — ...`
  (src/council/commands/gate_set.py:201-205) and the `NOTHING WAS CHECKED` lines (gate_set.py:49,52,178-184;
  doctor_gates.py); `council check`'s closing `check:` line (check.py:206-234, `Check.verdict`) and `check.md`
  (architecture sec. 4: "`check.md` | `council check` | the Chair (the receipt), the audit"). The Chair composes
  the line; nothing stops it writing "checked by machine" for work no gate ran.
- `council check`/`council run close` do not emit receipt text. `references/run/helper-commands.md` has no
  receipt command.
- **gates/<name>.json fields** (one line of JSON, written at src/council/commands/gate_run.py:125-127; read by
  records/gates.py `results` and records/verdicts.py): `gate`, `command`, `exit`, `seconds`, `when`, `limit`;
  optional `note` (e.g. `TIMED OUT after Ns (...)`, `cmd opened its prompt and ran nothing`, `exit 0, but its
  output says no test ran`, `exit 0, but it printed nothing`), `timed_out: true`, `proof` (`change`|`preserve`,
  gate_run.py:119-120), `tree` and `seat` (configured gates only, `_tree` :136-145; `tree` is dropped when files
  changed while the gate ran), and `invalid` (set by `--invalid`, gate.py:178-198, which also copies to
  `gates/invalid/` and emits `gate.invalidated`). Baselines: `gates/baseline/<name>.{json,txt}` (gate_run.py:
  159-169 `keep_baseline`). Output: `gates/<name>.txt`. Event: `gate.finished` per run.
  `records/gates.results` returns `name, exit, seconds, when, command[:200], note, proof, void`. Readers:
  `verdicts.green(path, command)` (reuse of a green on the same tree), `check_proofs`, `tree.py _proofs`,
  `council evidence`.
- What it would take to have the *helper* write a receipt line from these records is not present; the inputs
  (exit codes, tree, seat, note, proof, void reason, `check.md` rows, `patches/` records with `signs`/`outside`)
  all exist as files.

## 7. The verifier: "exists, not a stub, wired in"

**Neither the verifier contract nor build-proof.md asks this today.** `grep -i 'stub|wired|wiring|dead code|
placeholder'` over agents/, build-proof.md, builder-report.md, builder-rules.md and the implement/postgame
skills finds nothing. What they ask:
- agents/council-verifier.md (134 lines, **7,996 chars; limit 8,000 -> 4 chars of room**; 8,068 bytes, which
  is why the check counts chars; pinned at evals/run_structural.py:749-750). Change verdicts (lines 58-75):
  `OK` "backed by evidence you can check, and name both parts: a gate's saved output in `gates/` with exit 0; a
  check that actually runs the changed path: a test, a command, or a query" (68-70); `INCOMPLETE` "part of the
  ask isn't done" (71); `REGRESSION`, `SCOPE-CREEP`, `CANNOT VERIFY` "no test runs the path, or the gate never
  ran" (74-75). Line 60 "The builder's account is a claim, never evidence"; 62-66 "Judge the Done-when,
  nothing wider ... `## Noticed`"; 77-82 "For build tasks, read build-proof.md and check its mode, pair and coverage
  contract ... On every round, also ask its Checking questions: does it contradict a recorded decision (a D or
  EC entry) or add a second way beside the map's One way per job table? Does any added line exist only to make
  up for other code in this repo? Name that code. On a fix: does it hide the symptom, not remove the cause?".
- The nearest "live path" wording is the post-game check (verifier lines 84-98): `MET` "a live path from an
  entry point to code that does what the quoted words say. Cite the chain, and add `tested: <file>` or `tested:
  no`" (90-91) and for claims (verifying a claim, 40-44, 55-56) "trace a live path ... state reachability:
  *current* or *latent*". These are for council-postgame and claims, not for a build task's change.
- references/build-proof.md: "Prove it through the entry point that ships" (25-30; at least one proof runs "the
  command a person would run"; `council check` notes run-folder-only proofs); "Read the result" (144-175): "it
  traces the named invariants through the changed path, inspects test assertion changes and reads the actual
  before-failure"; "Missing proof earns CANNOT VERIFY; code that establishes an unmet Done-when earns
  INCOMPLETE" (175). Checking (96-142): "Judges the Done-when and nothing wider ... never hunts past it".
  A brief that sends the verifier hunting ("however narrow", "any route") is refused by the agent gate
  (`hunting`, agent_gate.py:101-115). So an "exists/not a stub/wired in" question is a new verifier question
  and has two homes: the verifier file (4 chars free) or build-proof.md Checking (no cap pinned) with a pointer;
  the verifier file already says "read build-proof.md ... ask its Checking questions" (77-82), so the pattern is:
  add the question to build-proof.md, Checking, and have the verifier line reference it (the same way "Making up
  for other code" was added in T3: build-proof.md:135-142 and verifier 79-82).
- The verifier's phrase pins to keep green: evals/run_structural.py:513-517 ("On every round", "make up for other
  code in this repo? Name that code."), :543-546 ("Judge the Done-when, nothing wider", "## Noticed", "however
  narrow"), :547-560 verdict words.
- A verifier on a weaker model than the builder: D37, section 2.

## 8. The benchmark, run both ways

- Files: evals/bench.py (752 lines, 41,267 bytes), evals/bench/README.md (123 lines), evals/bench/cases.json
  (schema `council.bench-cases/2`, 3 cases: `bench-refund-sign`, `bench-slug-contract`, `bench-admin-delete`),
  evals/bench/*.hidden (encoded traps/hidden checks), live cases evals/suite/bench-*/{case.yaml,prompt.md,
  scaffold.sh,graders/}. Registered in evals/run_all.py:57 as "Benchmark harness self-test (no model calls)"
  (`python evals/bench.py self-test`, ~18 s estimate at run_all.py:241); also docs/roadmap-status.md:36 ("10
  Benchmark harness | 0.13 (never run) | `bench.py self-test` | No | The paid comparison"); CHANGELOG ("Running it
  costs money, and it has not been run"); evals/README.md sec. 9 (:331-342).
- How it runs: `bench.py` itself calls **no model**. The runs are produced by `claude plugin eval . --tag
  benchmark --scaffold --keep-temp --runs 1 --model <m> --max-cost-usd 30 --allow-tools Bash Write Edit
  --no-publish --json evals/suite/results/bench.json` (README bench :69-72), "Run where live evals run (WSL2,
  macOS or Linux)". Then `python evals/bench.py score --case <c> --arm with|without --repo <kept project>
  --trace <trace.jsonl> --run <id>` per run (appended to a results.jsonl), then `python evals/bench.py compare
  results.jsonl [--json] [--min-pairs 10]`. Subcommands (bench.py:700-720): score, compare, self-test, show,
  pack, unpack. The README says "The kept folders' layout is not documented. The first pilot has to establish
  where each run's project and trace land, and only then should the scoring loop be scripted" (i.e. no
  automated driver).
- Can it compare two configurations? **Only two fixed arms: `with` vs `without` the plugin.** `score --arm`
  `choices=("with","without")` (bench.py:705); `compare` hard-codes `("with","without")` at :492, :497, :500;
  `summarise` and the verdict text say "Small Council met more/fewer tasks" (:508-512); `RUN_SCHEMA =
  "council.bench-run/1"`. To compare "Chair builds" vs "builder agent builds" both arms would be `with`-plugin
  runs, so a new arm label or a configuration tag on the record is needed (not present); today the two
  configurations would collide on the `(case, arm, run)` uniqueness key (:485-490). The `--ablation` flag is
  `claude plugin eval`'s (README: "default `--ablation with-without`"; evals/README.md:259, 279, 287 `--ablation
  none`), not bench.py's. How T5 would switch the build between the Chair and a builder agent for a bench run is
  not defined (no config key or flag for it today; see section 9).
- What it measures (bench.py:391-444 `score`, :342-379 `trace_facts`, :459-476 `summarise`): per run `met`
  (hidden checks pass + original suite + no frozen/protected change + a test where required), `scope`
  (changed/outside_scope/frozen/protected), `tests.assertions_removed`, `tests.test_added`, `report` claims
  (`claims_done`, `claims_blocked`, `asked_for_input`, **`false_completion`**, regex phrase matches), `cost`
  (usd, input/output/cache tokens, turns, duration, **`agents`** = count of Agent/Task tool_use blocks, `skills`).
  `compare`: tasks met, false completion, outside scope, frozen/protected, assertions removed, asked for input,
  median usd/tokens/turns/agents, usd per met, sign test on paired outcomes; below 10 pairs "a pilot, not a
  result". **No per-role token breakdown** (task-tree sec. 6 wants "tokens by role"): `trace_facts` reads only the
  trace's final `result.usage` totals and counts agent tool_uses (rows with `parent_tool_use_id` are skipped for
  text only). Per-role tokens would come from the run's own `seats.tsv`/`usage.tsv` (records/usage.py `workers` vs
  `verifiers` totals), which the bench does not read.
- Cost (evals/bench/README.md:76-87, 99-100): a council build "about $3-6 on Opus (the repair drill cost $5.69)";
  one run per arm per case = 6 sessions, "$12-25", `--max-cost-usd 30` stops before a further case; a result
  needs >= 10 paired runs: "for example, 4 runs per arm per case, about $50-90". Doubling for a
  builder-agent arm vs a Chair arm is the same order (two plugin arms). Model calls: every `claude plugin eval`
  session is real model calls; `self-test` and `score`/`compare` are free (no model).
- Small N and scope: 3 small Python cases; "Three small Python tasks are not a population" (README :114-115).
  Task-tree sec. 6 "How we would know": "The benchmark has never been run for a result; this is the first question
  it should answer."
- Other behavioural drills: evals/behavioral-drills.md; judgment fixtures evals/suite/build-judgment,
  build-repair-drill, verifier-build-proof, build-contract-conflict (T4's planted drill cases, #70, "part of S10").

## 9. Contract names (architecture sec. 6) T5 would add or touch

Frozen categories in architecture.md:133-170 and what each T5 part touches. "Add" = a new name that is frozen
from the day it ships; "touch" = an existing frozen name whose text/behaviour changes.
- **Agent type names**: ADD `council-builder` (or chosen name; file `agents/council-builder.md`, `name:` must
  equal the stem, quick_validate.py:173) and its dispatch type string `small-council:<name>`. Touch the
  allow-lists: hooks/agent-gate.sh:62 and :67, hooks/seat-gate.sh:46-50, hooks/hooks.json SubagentStop matcher,
  src/council/commands/agent_gate.py:28 (`KINDS`), gate_writable (takes `kind`), hooks/agent-gate.sh Workflow
  string at :104 and :125 (verifier only). evals/run_hook.py (agent gate and seat gate scenarios) must gain
  cases (D20 fault path included).
- **Helper commands, arguments, words, exit codes**: touch `council seat` (new refusals for the build seat; same
  usage and exit 2, seat.py `USAGE` :15 unchanged); possibly touch `council tree` (a check or `--check`), add or
  touch a revert check (new command or a flag: any new command needs `dispatch.COMMANDS`, `help.py` help text,
  references/run/helper-commands.md, structural pin "every `council ...` command a text mentions exists"),
  possibly touch `council patch save` (a tree-differs notice, a revert step), `council context build` (the
  task's own history for a fix round, today excluded: context.py:187-199 `earlier` skips `one.task ==
  found.task.number`; `patches/T<n>.md` is linked from the fix-round brief per builder-report.md:93-94).
  A helper-written receipt would be a new command or output. Exit codes: none to add; 0/1/2/4/124/97 only.
- **Output lines other code reads**: `Small Council:` hook refusals (new seat-gate/agent-gate text),
  `check:`, `NOTHING WAS CHECKED`, `TIMED OUT`, `UNWRITTEN <path>`, `Wrote <path> — ...`. A builder's return
  line (`done`/`NEEDS: ...`) is not in this list yet and `seat-gate.sh` greps `Wrote <path>.md`. The receipt
  line words `Checked by machine:` and `Not proved:` are pinned by structural checks.
- **Run-folder files and TSV columns**: `report-<n>.md` (already in sec. 4), `patches/` (T<n>-<r>.patch, .json,
  T<n>.md) already exist; seats.tsv columns frozen (no new column is needed to hold NEEDS: the `note` cell
  carries it); a builder seat could not carry its model or role without a run-plan row (`seat/<slug>/model|role`
  already exist). No new file is required by the design, but a revert check's scratch results or a receipt
  file would be a new run-folder file (frozen on shipping).
- **Event types/subjects/detail keys**: `seat.updated` and `gate.finished` already cover a builder seat and its
  gates; a new event for "tree differs"/"revert check" would extend references/run/event-stream.md (and
  `council run events check`).
- **Seat slug conventions** (not listed in sec. 6 but read by code): `verify-`, `diagnose-` (usage.py:105,
  ledger.py:131, status_names.py:34, seat_write.py:30), `task-<n>`/`T<n>`/`<n>` (tasks.number); the build seat's
  slug choice (`build-<n>` in task-tree sec. 6 vs `task-<n>` in run-accounting.md:11 and tree.py) becomes frozen.
- **Config keys** (sec. 6): `models` (builder= already there), `estimates` (builder= already there), `checking`,
  `build tier`, `open items`, `pushes`. No key exists to choose "Chair builds" vs "builder agent builds"; sec. 6
  says it follows the size proposal (Solo = Chair). If T5 adds a switch (e.g. for the bench), it is a new config
  key (reader in `council.records.config`, template line, default stated; architecture sec. 7).
- **Skill names**: none change (`council-implement` text only). **Verdict words**: none (sec. 6: "It adds no
  agents and no verdict words" is stated for the whole tree design in "What this does not do" - note: that
  line says "adds no agents"; T5 adds one agent file, a tension the plan should state).
- **Formats agents/checks parse**: the report head (`Cause/Owner/Removed/Assumed/Redesign`), `NEEDS:` /
  `NEEDS: fix <file:line> · does: · should: · seen:` (pinned at evals/run_structural.py:497-500, needs_fix at
  :494), the index line, verdict words.
- **Seat doc paths / references**: `references/build-proof.md` (frozen path) edits keep its path; a new
  `references/run/<name>.md` is new (not frozen yet). `references/run/builder-rules.md` and `builder-report.md`
  paths shipped in T3/T2 and are cited by packs.
- **Environment variables**: none needed.
- Decision entries: D4 (supersede), D37/references/run/models.md ("the Chair counts as a builder"), possibly
  D18's "Held by" row if builder rounds join `rounds.py`. Docs to update in the same branch: docs/architecture.md
  (sec. 3 `agents/` row "The worker and verifier contracts"; sec. 4 `report-<n>.md` row; sec. 8 rows "Hold a build to
  its verifier rounds", "Count an agent", "Print the task tree"), CHANGELOG `## [Unreleased]`, task-tree.md
  sec. 6, references/run/helper-commands.md rows for seat/tree/patch/context.

## 10. Size ledger (chars / lines vs limits) for every file T5 text could change

| File | chars | lines | Limit | Room |
| skills/council-implement/SKILL.md | 19,878 | 304 | 20,000 / 500 | 122 chars; 196 lines |
| skills/context-core/SKILL.md | 10,434 | 158 | 20,000 / 500; kernel <= 14,000 and <= 11,000 (run_structural.py:747-748) | 566 chars under the 11,000 check |
| agents/council-verifier.md | 7,996 (8,068 bytes) | 134 | 8,000 chars | 4 chars |
| agents/council-worker.md | 6,623 (6,667 bytes) | 106 | 8,000 chars (pinned, :749-750) | 1,377 |
| agents/council-builder.md (new) | - | - | none pinned today | - |
| references/build-proof.md | 11,774 (11,796 b) | 175 | none pinned | - |
| references/run/builder-rules.md | 2,234 | 31 | none | - |
| references/run/builder-report.md | 4,250 | 63 | none | - |
| references/run/repair-loop.md | 9,929 | 135 | none | - |
| references/run/models.md | 3,268 | 63 | none | - |
| references/run/run-plan.md | 8,752 | 120 | none | - |
| references/run/helper-commands.md | 15,992 | 48 | none | - |
| references/run/run-accounting.md | 14,971 | 206 | none | - |
| references/doctrine/05-work.md | 3,660 | 64 | 6,000 | 2,340 |
| references/doctrine/09-deliver.md | 2,658 | 49 | 6,000 | 3,342 |
| references/doctrine/01-convene.md | 5,994 | 85 | 6,000 | 6 chars (read in a review run) |
| references/doctrine/08-challenge.md | 5,672 | 80 | 6,000 | 328 |
| references/doctrine/10-learn.md | 5,215 | 69 | 6,000 | 785 |
| other doctrine 02,03,04,06,07 | 3,263 / 3,779 / 3,822 / 2,299 / 2,222 | 50/53/71/36/48 | 6,000 | > 2,000 each |

**Review method load** (the sum the check measures, evals/run_structural.py:153-156 = context-core SKILL.md +
council-review SKILL.md + the ten doctrine files, bytes, `load < 59407`): **55,266 bytes now**, 4,141 bytes
of headroom. Only context-core and the doctrine files (and the review skill) enter it, so edits to
council-implement, agents/ and references/run/ do not move it; an edit to context-core, 05-work.md,
09-deliver.md, 01-convene.md etc. does. Python size limits for new/edited modules (CLAUDE.md, ratchet): a new
file <= 500 lines / 60-line functions; src/council/* may grow to those; `bin/council`, hooks and scripts/ are
frozen at their ratchet numbers (hooks/seat-gate.sh 226 lines, longest fn 21; hooks/agent-gate.sh 152, 0 fn).
Current Python sizes (lines): seat.py 200, agent_gate.py 290, rounds.py 147, tree.py 105, context.py 199,
patch.py 142, patch_checks.py 164, task_slice.py 68, check.py 234, check_proofs.py 159, gate.py 247,
gate_run.py 180, seat_write.py 100, seats.py 122, plan_models.py 86, plan_check.py 357.

## 11. Further facts the plan may want

- Task-tree sec. 6 text already decided: Solo stays with the Chair ("Decided by the user" item 6, 2026-11-15);
  "One part is still a proposal: a fix round gets a fresh builder, not the same agent continued. T5 measures both
  ways before it is settled" - i.e. a measurement is part of T5 (bench, sec. 8), and the planned pack for a fix
  round plus `patches/T<n>.md`.
- Sec. 6 table rows: orders (pack + Chair's where-to-start), builder returns one line `done | NEEDS: <q> |
  NEEDS: fix ... | blocked at the third failed gate`, Chair reads that line and `council patch show <n>`,
  fix round = fresh builder with pack + history, verifier unchanged "may be on any model that is not below the
  builder's".
- "Where it lands" row (task-tree.md:252-260): `| T5 | A fresh builder per task (section 6): the builder's
  contract, the build seat and its refusals, the tree check, the implement skill's loop moved to a reference,
  the entry that supersedes D4's last clause | T3 (it needs the pack) | ~1-1.5M |`. T4 (planted drill cases)
  "After S10 (#70)", "part of S10". The sec. 6 "How we would know": scenarios for each refusal, planted cases
  of T4, then the bench both ways: "tokens by role, hidden checks passed, false completion claims".
- Cost estimates: "the total tokens of a build will probably not fall"; "the estimate of a build is measured
  again from the ledger before the default changes (D39)" - but D39 was superseded by D40 (2026-11-15: `council
  tune`, `history`, `outcomes` cut; estimates edited by hand). The sec. 6 sentence cites a superseded id and a
  cut command; `council ledger` still exists (records/ledger.py; `council ledger advice`).
- Sec. 3's `Owner:` check ("a changed file outside the slice is flagged") and the builder's `Owner:` head line
  are produced by `patch save` regardless of who builds.
- Verifier dispatch brief for a build (SKILL.md:127-136) passes patch + history + gates by path; unchanged.
- Chair edit ban in prose only: nothing makes the Chair refuse to edit once a builder agent exists; sec. 6's
  tree-differs notice is the planned detector ("how a Chair that 'just fixes it' shows, with no new hook on every
  edit").
- Tests that exist for the parts T5 touches: tests/py/{test_patch,test_context,test_seats,test_cap,
  test_plan_models,test_models,test_estimates,test_gates,test_gate_reuse}.py; evals/run_cli.py groups
  `lifecycle` (runs_dispatch_record, runs_one_checker_per_batch, runs_third_check_needs_diagnosis), `gates`
  (gates_patch_rounds), `requests` (requests_task_pack, requests_task_tree), `models`; evals/run_hook.py (agent
  gate, seat gate, `--group main`). Run only the groups touched plus `run_all.py --fast` (CLAUDE.md).
