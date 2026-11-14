# Architecture

How Small Council is put together: what each part owns, which way the dependencies run, where new code
goes, the one way each recurring job is done, and the names that never change. Read this before
changing anything. The settled decisions it rests on are in [`decisions.md`](decisions.md), cited by
id (`D12`). This page describes the code as it is, and marks each rule that is a target the cleanup
is moving toward, not yet true everywhere. The plan behind those targets is in §10.

## 1. System overview

Small Council is a Claude Code plugin. The main session acts as the **Chair**. It reads a mode's
skill, follows the stage doctrine, sends work to **seat** agents in their own context windows, and
records everything in a **run folder** inside the project's **council home** (`.council/`).

| Part | Where | What it is |
|---|---|---|
| Kernel | `skills/context-core/SKILL.md` | The laws, the stage index, the helper's essentials, file layout, limits, resume. Every mode invokes it. |
| Modes | `skills/council-*/SKILL.md` | One per job: init, review, plan, implement, research, postgame. Thin: `## At <Stage>` sections only where the mode differs. |
| Standalone skills | `skills/spec-writer/`, `skills/test-architect/` | Skills that use the council's agents and formats without being council modes. |
| Stage doctrine | `references/doctrine/NN-<stage>.md` | One file per stage, read by the Chair when it enters that stage. |
| References | `references/` | By who reads it: the seat docs, `guardrails.md` and `build-proof.md` at the root, `doctrine/`, `run/` (the run's contracts), `roster/`, `templates/`, `spec-writer/`, `test-architect/`. `references/README.md` is the map. |
| Agents | `agents/council-worker.md`, `agents/council-verifier.md` | The seat worker's and the blind verifier's contracts. |
| Helper | `bin/council` | The CLI for the mechanical steps: runs, state, seats, gates, the change index, checks, memory, the agent stop. Bash today (§10). |
| Scripts | `scripts/*.py` | Python for what bash does badly: status and the card, audit, history, tuning, impact, context packs, evidence, repair, memory, the pet, the Chair's tokens. Run through the helper. |
| Hooks | `hooks/*.sh`, `hooks/hooks.json` | Enforce what prose can't: SessionStart orientation and the session mark, the agent stop (PreToolUse on Agent, Task and Workflow), the Bash pipe guard, the seat-file check (SubagentStop), the turn-end nudges (Stop). |
| Mod | `hooks/council-view.tsx`, `hooks/council-scene.ts` | The council pane and the line above the prompt. It reads `scripts/status.py --json` and never writes a council file. |
| Evals | `evals/` | Machine checks: structural pins, helper and hook scenarios, per-script suites, judgment fixtures (`evals/suite/`), the benchmark harness. `evals/run_all.py` runs them all. |
| Docs | `docs/` | This page, the decisions index, ADRs and design notes (`design/`), validation records (`validation/`), roadmap status. |

## 2. Dependency direction

```
user ── Chair (main session)
          │ reads
          ├─ skills ──► doctrine ──► references (contracts, seat docs, templates)
          │ runs
          ├─ bin/council ──► scripts/*.py ──► run files (.council/)
          │ dispatches
          └─ agents (worker, verifier) ── read brief + references, write one seat/verify file
hooks ──► bin/council          mod ──► scripts/status.py
```

Rules:
- **Prose points down, never sideways.** A skill points at the doctrine and the references. A mode
  never restates the kernel, and an agent's dispatch message never restates the agent's contract
  (D3).
- **Mechanics live in the helper, not in prose** (D2). If a step can be done or checked by a
  script, the skill names the command and the helper does the step.
- **Hooks are thin.** A hook reads its input and asks the helper for the decision. A fault in a hook
  or in the helper lets the call through: a hook must never block work because of its own bug (D20).
- **Agents write only their own file.** A seat writes `seats/<slug>.md`, a verifier writes
  `verify-<n>.md`, and neither edits project code (D4).
- **Known cycle (debt).** `bin/council` runs the scripts, and one script (`pet.py`) runs `bin/council`
  back; others print `council …` commands for the reader to run. *Target:* both sides call one library,
  and nothing calls the CLI from inside the CLI's own code (§10, WS1).

## 3. Directory ownership

| Path | Owns | Never |
|---|---|---|
| `skills/` | How the Chair works, per mode | Logic a script could do; a project's own stack, seats or commands |
| `references/doctrine/` | What happens at each stage | Mode specifics (they go under the mode's `## At <Stage>`) |
| `references/*.md` (the root) | The 14 seat docs (principles), `guardrails.md`, `build-proof.md`. Their paths are frozen (§6) | Run-time state; a new contract (it goes in `run/`) |
| `references/run/` | The run's contracts, records and procedures, read by the Chair, the helper and the scripts | Seat principles; run-time state |
| `references/templates/` | The files `council init` writes into a project | Project-specific values |
| `references/roster/` | The seat catalogue | Seat principles (those are in the seat's doc) |
| `references/spec-writer/`, `references/test-architect/` | The two standalone skills' own templates, guides and formats | Anything a council mode reads |
| `agents/` | The worker and verifier contracts | Mode logic |
| `bin/council` | Every command, its arguments, output and exit codes | Long-running work; anything a hook must not wait on |
| `src/council/` | The Python library. `records/` reads and writes run files, one module per file (paths, locks, config, state, events, seats, plan, gates, ledger), with `home` (where the council lives), `runs` (the run listing), `sharing` (the sharing line), `owners` (who holds a lock), `writable` (whether a folder takes a new file) and `usage` (the per-seat usage rule and the agent stop's standing), `usage_gaps` (the seats that were agent runs with no token figure, read from it) and `audit_file` (audit.md and the audit's report text); `git.py`, `clock.py` | Printing, argument parsing, a command's own logic |
| `src/council/commands/` | The helper's commands ported from bash (D24), one module per area, behind `src/council/__main__.py`; `cli.py` reads the command line as `bin/council` does and holds the refusal | A run file's parser (that is `records/`) |
| `scripts/` | Python readers, renderers and analyses, over `src/council/records` | Their own copy of a run-file parser |
| `hooks/` | Enforcement at Claude Code events, the mod | Decisions: the helper makes them |
| `evals/` | Machine proof that the contracts hold | Production logic |
| `docs/` | Architecture, decisions, ADRs, validation | Rules the model must follow at run time (those are in skills, doctrine or references) |
| `types/` | The mod's TypeScript types | — |
| `.claude-plugin/` | The plugin and marketplace manifests | — |

## 4. The council home and the run folder

A project's council lives in `.council/` at its root. A linked worktree finds the main checkout's
home (`council_home`). Committed or ignored follows the project's sharing setting (D16).

| File | Written by | Read by |
|---|---|---|
| `council.config.md` | `council init` (template: `references/templates/`); the user's hand edits are theirs | the helper (`configured_*`), `status.py` and `tune.py` through `council.records.config`, `session-start.sh` |
| `conventions.md` (memory) | `council memory` on the user's words | the helper, `cockpit.py`, `status.py` |
| `map.md` | council-init's mapping seats | `session-start.sh`, briefs |
| `ledger.tsv` | `council run close` | `ledger.py`, `history.py`, `tune.py` |
| `asks/`, `plans/`, `reviews/`, `logs/`, `postgames/`, `research/`, `cards/` | each mode's Deliver | later runs (`council prior`) |
| `runs/<date-time>-<mode>/` | one run's working folder, below | |

Scripts read the files in these tables through `src/council/records`, never with a parser of their own.

Inside a run folder:

| File | Written by | Read by |
|---|---|---|
| `session-state.md` | `council run open`, `council state` | the helper (`field`), the scripts through `council.records.state`, the mod, `session-start.sh` |
| `run-plan.tsv` | the Chair, checked by `council run plan check` | the helper, `audit.py`, `cockpit.py`, `evidence.py`, `status.py`, `quick_validate.py` |
| `events.tsv` | the helper only, through `event_append` (contract: `references/run/event-stream.md`) | the helper, `audit.py`, `cockpit.py`, `history.py`, `repair.py` |
| `seats.tsv`, `usage.tsv` | `council seat` | the helper, `audit.py`, `cockpit.py`, `history.py`, `status.py` |
| `agent-starts.tsv` | the agent gate (`council cap check`) | the helper, `audit.py`, `status.py` |
| `ask.md` | the Chair (the user's words) | `council check`, `council ask save`, `status.py` |
| `brief.md`, `seats/`, `verify-<n>.md`, `synthesis.md` | the Chair and its agents | `council collect`, `council check`, `audit.py`, `evidence.py` |
| `gates/` | `council gate` | `council check`, `cockpit.py`, `evidence.py` |
| `check.md` | `council check` | the Chair (the receipt), the audit |
| `audit.md` | `council run close` (`audit.py --at-close --save`, through `records/audit_file`); a close again rewrites it | `council status` (the closing card), `council run status`, a later session |
| `repairs.jsonl` | `council gate` / `repair.py` | `repair.py`, `memory.py`, `cockpit.py`, `status.py` |
| `index.md`, `impact.tsv`, `contexts/` | `council index`, `impact.py`, `context.py` | seats, `context.py` |

## 5. Entry points

- **Skills** (what the user invokes): `council-init`, `council-review`, `council-plan`,
  `council-implement`, `council-research`, `council-postgame`, `spec-writer`, `test-architect`, and
  `context-core`, which only modes invoke.
- **Agents**: `small-council:council-worker`, `small-council:council-verifier`.
- **Helper commands** (`council help` gives exact syntax; `references/run/helper-commands.md` gives the
  purpose of each): `home`, `sharing`, `run open|close|status|resume|plan|events|audit|turn-end`,
  `state`, `seat`, `cap show|allow|check`, `route recommend`, `index`, `impact`, `context`,
  `evidence`, `repair`, `gate`, `gates`, `changed`, `collect`, `check`, `map`, `fingerprint`,
  `memory`, `prior`, `ask`, `ledger`, `tune`, `history`, `outcomes`, `tui`, `status`, `pet`,
  `correct`, `doctor`, `version`, `help`.
- **Hooks**: SessionStart → `session-start.sh`; PreToolUse Agent, Task, Workflow → `agent-gate.sh`;
  PreToolUse Bash → `bash-gate.sh`; Stop → `turn-end.sh`; SubagentStop worker and verifier →
  `seat-gate.sh`; the mod module → `council-view.tsx`.

## 6. Contracts: names a cleanup never renames

Renaming any of these is a separate decision, recorded in `decisions.md`, with a migration. It is
never part of a cleanup or refactor branch (D23).

- **Skill names, agent type names, the plugin name** (`small-council`) and the mod's slash command
  (`/council-view`).
- **Helper commands, their arguments, the words they take** (`phase=`, `deliverable=`, `decision=`,
  `type=`, `seat=` …) **and their exit codes**: 0 ok; 1 a check that found problems; 2 a refusal or
  usage error (a hook's refusal goes on stderr); 4 a gate run that checked nothing (NOTHING WAS
  CHECKED); 124 a gate stopped at its time limit (TIMED OUT); 97 a gate whose code root is
  unreachable. A gate otherwise returns its own command's exit code.
- **Output lines other code or the Chair reads**: lines starting `Small Council:` (hook refusals),
  `check:`, `audit:`, `NOTHING WAS CHECKED`, `TIMED OUT`, `UNWRITTEN <path>`, `Wrote <path> — …`.
- **The council home's file and folder names** (§4), the run folder's naming
  (`runs/<YYYY-MM-DD-HHMMSS>-<mode>`), and every TSV's columns and their order.
- **Event types, subjects and detail keys**, as `references/run/event-stream.md` lists them.
- **Seat doc paths**: the 14 seat docs, `guardrails.md` and `build-proof.md` stay at the root of
  `references/`, because project files carry their paths (a roster's doc column, a card's `source:`, a
  plan's `Ref:`, comments in the config). Moving one breaks every installed project.
- **Config keys** in `council.config.md` (`approve without asking`, `agent cap`, `context packs`,
  `seat models`, `models`, `build tier`, `checking`, `open items`, `pushes`, `sharing`, `notifications`,
  `estimate per worker`, `gate time limit`, the Gates table's columns).
- **JSON schemas**: `council.run-status/1`, `council.run-snapshot/2`, `council.history/4`,
  `council.tune/2`, `council.seat-advice/1`, `council.outcomes/1`.
- **Formats agents and checks parse**: the index line
  (`<n> · <severity> · <principle> · <path:line> · <title>`), `ref:` proof of reading, `quote:`,
  verdict words (CONFIRMED / REFUTED / UNCERTAIN / MISCITED; OK / INCOMPLETE / REGRESSION /
  SCOPE-CREEP / CANNOT VERIFY; MET / PARTLY MET / NOT MET / CAN'T TELL), memory entry ids (AP, EC,
  D, F), `Principle N` numbering in seat docs.
- **Environment variables**: `COUNCIL_ALLOW_NO_HOOKS`, `COUNCIL_ASCII`, `COUNCIL_BASE`,
  `COUNCIL_BOM`, `COUNCIL_INDEX_CAP`, `COUNCIL_INDEX_NAMECAP`, `COUNCIL_MEMORY_SIZE_LIMIT`,
  `COUNCIL_NEXT_AT_OPEN`, `COUNCIL_PET_LOG`, `COUNCIL_PLUGIN_ROOT`, `COUNCIL_RUN`, `COUNCIL_VERSION`.

When an internal name disagrees with a contract word, the internal name takes the contract word.

## 7. Where new code belongs

Before adding anything, answer these questions: which part owns it? Does something already own this
job (§8)? Will the next agent find it next to the code it relates to?

| I am adding… | Put it in | Also |
|---|---|---|
| A rule for how the Chair works at a stage | The stage's doctrine file, once | Each mode inherits it; never copy it into a mode |
| A rule only one mode needs | That mode's `## At <Stage>` section | Keep the skill under its size caps (D13) |
| A rule the model keeps breaking | The helper or a hook that enforces it | The prose keeps one pointer to the enforcement, not the whole rule |
| A seat's principle | The seat's reference doc at the root of `references/`, as `Principle N` | The catalogue row in `references/roster/expert-catalog.md` |
| A run contract (a file's shape, a verdict, an event) | Its `references/run/<contract>.md` | The reader and the writer change in the same branch |
| A new command or a check | Today: a `cmd_<name>` in `bin/council` and its dispatch line. *Target:* a Python module behind the same command (D24) | Help text, `references/run/helper-commands.md`, a scenario in `evals/run_cli.py` |
| A new analysis or view over run files | `scripts/<name>.py`, run through the helper, reading run files through `council.records` | Its own `evals/run_<name>.py` suite |
| A config setting | A `configured_<key>` reader in the helper, the template line and its comment in `references/templates/council.config.md` | A missing line has a stated default; an unknown word reads as the default and says so |
| An enforcement at a Claude Code event | A thin `hooks/<event>.sh` that asks the helper | `evals/run_hook.py`, including the fault path that must let the call through |
| A design decision | `docs/decisions.md` (an ADR in `docs/design/` when it weighs options) | A CHANGELOG line in the same branch |
| A test | `evals/run_cli.py`, `evals/run_hook.py` or the script's own suite; `evals/run_structural.py` only for document contracts | A scenario over a phrase pin wherever behaviour can be run (D25) |

## 8. How we do X here

One way per recurring job. Code that does one of these jobs another way gets folded into the one
way, never kept beside it. Rows marked **(debt)** have more than one way today. The cleanup (§10)
folds them, and new code uses the named way.

| Job | The one way | Notes |
|---|---|---|
| Find the council home | `council_home` (bash); in Python `council.records.home.council_home` | A worktree resolves to the main checkout's home. **(debt)** two copies until the bash is retired (S9): the hooks and the bash commands use the bash one |
| Find the run a command is for | `resolve_run`: `--run`, then `COUNCIL_RUN`, then this tree's one in-progress run, then the one this session drives on another tree. Two candidates at any step are a refusal naming `--run`; it never guesses (D6). In Python, `council.commands.resolve.run_folder` | **(debt)** two copies until S9: the bash commands use the bash one |
| Read a config setting | One `configured_<key>` function per key, with a stated default | **(debt)** 44 references to `council.config.md` in `bin/council`, 6 readers. Scripts read it through `council.records.config`, one function per key |
| Read a run's state field | `field <key> <file>`; in Python, `council.records.state` | Scripts no longer parse `session-state.md` themselves |
| Record an event | `event_append` under the run's event lock; nothing else writes `events.tsv` | `council.records.events.append` follows it step for step but has no caller yet |
| Write a shared TSV row | Under `event_lock`; never join a torn line | |
| Take a run file's lock | bash `event_lock`; Python `council.records.locks.held`. The owner file names the holder by the operating system's process id, checked by `owner_alive` (bash) and `council.records.owners.holder_alive` (Python), so either language waits for the other (D33) | `gates.lock` keeps bash's own process id until gate is ported (S6) |
| Refuse something | `die "<why — and the next command>"` (exit 2, stderr). From a hook: the helper prints `Small Council: …` on stdout with exit 2, and the hook moves it to stderr | Every refusal names what to do next (D19) |
| Take the user's go | `council state decision="<their words>"`, read back with `decisions_since` after the event it unlocks | Never inferred, never the Chair's words (D7) |
| Hand a path to awk | Through `ENVIRON`, never `-v` (Windows backslashes) | |
| Run Python from the helper | One candidate order, `PYTHON_CANDIDATES` (chosen without running anything). `python_command` hands a ported command to `src/council/__main__.py` with its words as typed: one Python start, no probe; the entry refuses an old Python itself (exit 85) and the launcher tries the next candidate (D34). Bash that stays and needs a ported check calls `python_run`, the same launch with the exit code handed back (Python never calls bash back, §2). `impact_python` probes the same candidates for a `scripts/` entry point | A ported command without Python refuses and says how to get it (D24, D19); a script the bash runs still degrades with a stated message. **(debt)** `impact_python`'s probe costs a Python start until the scripts are ported (S9) |
| Start a ported command | `council.commands.dispatch.COMMANDS` maps the command words to one module, imported on use. A new command adds a row there and its module in `src/council/commands/`; a stdlib module only some commands need is imported inside the function that uses it, never at the top of a module every command loads (D34) | `tests/py/test_launch.py` holds both |
| Read the command line | `main()` in `bin/council` for the bash commands; `council.commands.cli` for the ported ones, the same flags and refusals | **(debt)** two readers until S9 |
| Match the user's words | `fold` and `found` inside the quote check | **(debt)** two copies in `bin/council` (`cmd_check`, `postgame_next_tasks`) |
| Read a gate verdict | `gate_exit`, `gate_cmd`, `gate_proof` over `gates/<name>.json` | |
| Count an agent | `council seat` records it; the agent gate (`council cap check`, `src/council/commands/agent_gate.py`) counts starts; the ledger is written at close | One record per agent run, by id (`references/run/run-accounting.md`) |
| Read what a run's agents used | The per-seat rule: `council.records.usage` (`seat_list`, `usage_totals`, `standing`), read by `council cap`, the agent gate, the cockpit and the status card | **(debt)** bash keeps `seat_rows`, `run_usage`, `usage_words`, `usage_token_text`, `run_budget_value`, `agents_share`, `cap_standing`, `cap_starts`, `cap_extra`, `cap_allowed_until` and `run_agent_cap` for `run close`, `council seat`'s notes, `cap allow` and the ledger: two copies until S8b. `scripts/status.py` keeps its own `cap_standing`, `budget_value` and `run_agent_cap` until it moves onto `records.usage.standing` |
| Hold a build to its verifier rounds | `batch_check_refusal` (one checker per batch, D18) and `check_round_refusal` (no third check without a diagnosis or the user's go) | **(debt)** two copies until seat is ported: `council.commands.rounds` for the agent gate, the bash pair for `council seat … running` |
| Check a run plan | `council run plan check` (`src/council/commands/plan_check.py`). `council state` (each phase from Brief on), `council seat … queued/running`, `council context build` and `council doctor` reach the same check through bash's `plan_check` | A closed run's plan is judged by the settings of its day; Full needs a decision of the user's since the run opened (D7) |
| Prove a build task | `council gate before-<id>` / `after-<id>`, checked by `council check` (`references/build-proof.md`) | |
| Check a document's contract | A structural pin in `evals/run_structural.py` | Only for documents; behaviour is proved by running it (D25) |
| Hold a limit (a size, a count, a lint warning) | A number in `evals/ratchet.json`, measured by `evals/run_ratchet.py`; it may only go down, and `--update` keeps a gain | Never a hand-kept list of files or exceptions |

## 9. Naming

- **Bash**: `cmd_<command>_<sub>` for a command, `configured_<key>` for a config reader,
  `<noun>_<verb>` or a plain verb for a helper (`event_append`, `resolve_run`, `field`), all
  snake_case. Locals are declared with `local`.
- **Python**: snake_case modules and functions, CapWords classes, UPPER_CASE constants, `_private`.
  A function's name is a verb or the thing it returns.
- **Same word for the same thing everywhere**: run, seat, Chair, verifier, gate, proof, deliverable,
  ask (the user's request), decision (the user's words), ruling (the Chair's call inside its scope).
  Don't add a second word for any of them.
- **No filler names** (`_helper`, `_util`, `_data`, `do_`, `process_`) and no type tags
  (`list_seats`, `str_slug`).
- **Comments say why, in one line or two.** The story of the real run that taught a rule goes in
  `decisions.md` or the CHANGELOG, not in the code.

## 10. Known debt and the cleanup

Measured on 2026-11-13:
- `bin/council` is one 8,156-line bash file with 252 functions, 167 lines that call awk, and
  functions of up to 297 lines (`cmd_check`; `cmd_memory` and `memory_entries` are about 250).
- `session-state.md` is named on 89 code lines of `bin/council` and `run-plan.tsv` on 40. No script
  parses either any more: the scripts read run files through `src/council/records` (S1).
- Skills and agents sit near their size caps (council-implement is at 19,331 of 20,000 characters after WS6's
  first pass; it was 19,992).
- Many structural evals check that a phrase is present, not that behaviour holds. The full suite
  takes about 30 minutes on Windows and has no fast tier.

The cleanup's workstreams. [`design/cleanup-plan.md`](design/cleanup-plan.md) has the target layout
(`src/council/`, D32), the rules every session follows, and the sessions in order:

| WS | What |
|---|---|
| 0 | This page, `decisions.md`, the root `CLAUDE.md` |
| 1 | One Python library for config and run files; every script moves onto it; the copies go |
| 2 | `bin/council` split into Python modules, one area per branch, with commands, output and exit codes unchanged (the eval suite is the proof). *Started (S3):* `bin/council` hands ported commands to `src/council/__main__.py`; `home`, `sharing` and `run status` live in `src/council/commands/`, and bash and Python writers share run-file locks (D33). *S4:* `cap` and `cap check` (the agent gate) followed; `seat`, `correct` and `cap allow` wait on the ledger and redaction (S8) and the state writer (S8b). *S5:* `run plan check`, `run plan show` and `route recommend`; the bash that stays runs the same plan check through `python_run`. `state`, `run open`, `run close` and `run resume` stay bash until the areas they call are ported (the plan check, usage, the gates table, the ledger, the memory file, redaction: S4–S8) |
| 3 | File layout: `references/` by audience, evals into fast unit and scenario tiers |
| 4 | Quality gates as ratchets (ShellCheck, ruff, a type check on the library, size and complexity limits frozen at today's worst), and this page's rules as tests. *Started (S2):* `evals/run_ratchet.py` holds sizes, ShellCheck warnings, parsers, config readers and call-backs; `ruff.toml` runs on the whole tree. The type check is still to come |
| 5 | Slop pass: story comments out, a naming pass, dead code deleted, duplicates folded |
| 6 | One rule, one place: rules cited by id, doctrine loaded per surface (#67). *Started (P2):* 62 restated rules now live in their owner (§7) with a pointer left behind, a brief links only its own seats' cards and docs, and `evals/run_structural.py` checks that each folded rule's wording is in its owner only. Ten copies that disagreed were settled one way on the user's rulings, and a check keeps the stale wording out. A review run's method load fell from 59,387 to 56,970 bytes |
| 7 | Tests: a fast tier, behaviour over phrase pins, the Chair drill eval (#70) |
