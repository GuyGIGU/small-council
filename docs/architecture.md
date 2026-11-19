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
| Kernel | `skills/context-core/SKILL.md` | The laws, the stage index, the helper's essentials, file layout, limits, resume. No mode invokes it since D67; it stays for a post-game run opened on 2.0.0 or earlier. |
| Modes | `skills/council-*/SKILL.md` | One per job: init, review, plan, implement, research, postgame, health, and `council`, the whole loop. Each page is its whole method: the commands in order and the rules they need, with no kernel or doctrine (D47, D56, D60, D65, D67). |
| Standalone skills | `skills/spec-writer/`, `skills/test-architect/` | Skills that use the council's agents and formats without being council modes. |
| Stage doctrine | `references/doctrine/NN-<stage>.md` | One file per stage, read by the Chair when it enters that stage (never in a review, D47). |
| References | `references/` | By who reads it: the seat docs, `guardrails.md` and `build-proof.md` at the root, `doctrine/`, `run/` (the run's contracts), `roster/`, `templates/`, `spec-writer/`, `test-architect/`. `references/README.md` is the map. |
| Agents | `agents/council-worker.md`, `agents/council-verifier.md`, `agents/council-builder.md` | The seat worker's, the blind verifier's and the builder's contracts. The builder builds one task of a build in a clean window (D42). |
| Helper | `bin/council`, `src/council/` | The CLI for the mechanical steps: runs, state, seats, gates, the change index, checks, memory, the agent stop. `bin/council` only starts Python; every command is in `src/council/commands/` (§10). |
| Scripts | `scripts/quick_validate.py`, `scripts/build_release.py`, `scripts/publish_release.py` | The repo's own validator; the builder of the release tree, the files a user installs, and its publisher (D45). The tools (audit, evidence, repair, memory, the Chair's tokens) are modules in `src/council/commands/`, the views (status and the card, over the run's snapshot) in `src/council/views/`, run through the helper. |
| Hooks | `hooks/*.sh`, `hooks/hooks.json` | Enforce what prose can't: SessionStart orientation and the session mark, the agent stop (PreToolUse on Agent, Task and Workflow), the Bash pipe guard and push freeze, the seat-file check and the builder's stop check (SubagentStop), the turn-end nudges (Stop). |
| Mod | `hooks/council-view.tsx`, `hooks/council-scene.ts` | The council pane and the line above the prompt. It reads `python src/council/commands/script.py status … --json` and never writes a council file. |
| Evals | `evals/` | Machine checks: structural pins, helper and hook scenarios, per-script suites, judgment fixtures (`evals/suite/`), the benchmark harness, the release tree's standing alone (`run_release.py`). `evals/run_all.py` runs them all. |
| Docs | `docs/` | This page, the decisions index, ADRs and design notes (`design/`), validation records (`validation/`), roadmap status. |

## 2. Dependency direction

```
user ── Chair (main session)
          │ reads
          ├─ skills ──► doctrine ──► references (contracts, seat docs, templates)
          │ runs
          ├─ bin/council ──► src/council ──► run files (.council/)
          │                    └─ src/council/views, the views (in the same process)
          │ dispatches
          ├─ agents (worker, verifier) ── read brief + references, write one seat/verify file
          └─ agent (builder), one at a time ── runs council context build, writes one task's code + report-<n>.md
hooks ──► bin/council          mod ──► commands/script.py status
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
- **One builder at a time edits project code** (D42): a builder agent on seat `task-<n>`, which
  writes the code of its one task and `report-<n>.md`, or the Chair itself in a Solo build. Outside a
  Solo build the Chair edits no project code.
- **Nothing calls the CLI back.** The mod reads the status as its own process through
  `commands/script.py`; the views print `council …` commands for the reader to run, and none runs
  `bin/council` (§10, WS1).

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
| `agents/` | The worker, verifier and builder contracts | Mode logic; the builder's steps, proof and stops (its one page, `references/run/builder-rules.md`, D56) |
| `bin/council` | Finding a Python and starting `src/council/__main__.py` with the words as typed; the one refusal when there is none (D24) | A command's own logic; anything but the launch |
| `src/council/` | The Python library. `records/` reads and writes run files, one module per file (paths, locks, config, state, events, seats, plan, gates, ledger), with `home` (where the council lives, and the plugin's own folder: `plugin_root`), `runs` (the run listing), `sharing` (the sharing line), `pushes` (the push freeze line), `owners` (who holds a lock), `writable` (whether a folder takes a new file) and `usage` (the per-seat usage rule and the agent stop's standing), `usage_gaps` (the seats that were agent runs with no token figure, read from it), `audit_file` (audit.md and the audit's report text), `request` (the user's words from ask.md and the filed request, and the quote match), `tasks` (a plan deliverable's tasks and their rows, and the task word: 3, T3, task-3), `map_file` (map.md's one-way-per-job table, its stamp, the top-level areas changed since a commit, and its one writer), `converge` (the build log's Converge table), `report_head` (a build round's report and its head), `patches` (a build's saved rounds), `stages` (the stage table: rank, next step, required and skipped stages), `state_write` (the one writer of session-state.md), `closing` (what a close checks and says: undelivered runs, the usage words, the warnings), `synthesis_counts` (each seat's kept, cut and refuted items for the ledger), `seat_write` (seats.tsv's rows and the usage trail), `repairs` (the repair trail and the user's go past it), `hook_marks` (which hooks ran in a session), `book` (the project's book: where its four pages are, from the config's `## Book`, and the one writer of a known-problems line), `restore` (a run's restore point, `restore.md`, D57), `memory` (the memory file, what is wrong with how it reads, and its one writer) with `memory_entries` (its entries, and the section each sits under), `memory_anchors` (what each **Anchor:** names) and `memory_audit` (each observed failure's support), `scope` (how a scope or an areas: list matches), `earlier` (earlier council work on some paths), `anon` (a run's words made anonymous for `council run export --anon`: paths as placeholders, free words as stand-ins of the same shape), `redact` (secret-looking strings out of the user's words), `ignores` (the home's .gitignore) and `bytewise` (text as the C-locale awk read it); `git.py`, `clock.py`, `diff.py` (a unified diff's files and lines) | Printing, argument parsing, a command's own logic |
| `src/council/commands/` | Every helper command (D24), one module per area, behind `src/council/__main__.py`: `dispatch.py` maps the words to a module, `cli.py` reads the command line and holds the refusal, `help.py` the help text and the version. The tools live here as modules of their own: `audit` (with `audit_checks`, the run's records, `audit_steps`, the Chair's steps in the transcript, and `audit_calls`, how the helper was called), `chair_usage`, `evidence` (the claim index: `build`, its one writer, for `evidence build|check`, `memory propose claim` and a complete close), `memory_draft` and `repair_trail`. `script.py` runs a tool's `main(words)` in process, says its faults as the tool's own process did, and is the one way in by path for a caller outside the helper (the mod, the evals: `python src/council/commands/script.py <tool> <words>`; the seat-gate hook goes through `bin/council` with `COUNCIL_SCRIPT=script`, so it starts the Python the launcher picks); `script_cmds.py` runs the commands that hand over to a tool or a view; `session_start.py` is the SessionStart hook's body (`council run session-start`); `book.py` is `council book` and `book note|waive`, and the book's lines a review's brief and a task's orders carry; `restore.py` is `council restore point|show`, a run's restore point and the commands that go back to it, printed and never run (D57); `init.py` is `council init detect|scaffold`, setup's mechanical part, with `init_checks.py` (the candidate checks a project's manifests and scripts show), `init_seats.py` (the catalog's seats and the surface markers a file list shows) and `init_write.py` (the setup files filled from `references/templates/`, the Gates rows from the setup run's probes); `context.py` prints a build task's orders and `tree.py` the task tree, with `task_slice.py` (a task's plan and slice, and the refusal when the run has no readable plan, shared with `patch`); `build_seat.py` holds the build seat's rules (the slug `task-<n>`, one at a time, no start past a standing `NEEDS: fix` stop, the report a finished seat owes, the files changed outside a saved round) for `council seat` and the agent gate, and the one reader of a task's stop, which `council tree` asks too, and `builder_stop.py` is the tool that judges a builder's stop for the seat gate; `patch_apply.py` takes a saved round off a folder's files or puts it back on (`council patch apply|revert`), `revert_check.py` is `council check`'s revert check, and `receipt.py` writes the receipt's two machine lines; `run_export.py` copies what the audit reads of a run, anonymised, with `run_export_log.py` the session transcript's part | A run file's parser (that is `records/`) |
| `src/council/views/` | The views over `src/council/records`: `status`, a module with a `main(words)` named in `script.TOOLS` (the plain reading, with `status_card` the card and widget, `status_usage` the usage and the stop, `status_closing` the close, `status_names` the seat names, `words` the shared wording), and `snapshot` (the run's records read once, for the status and its parts) | Their own copy of a run-file parser |
| `scripts/` | `quick_validate.py`, the repo's own validator; `build_release.py`, the release tree's one builder, and `publish_release.py`, its one publisher (D45) | Council logic; anything the installed plugin runs (scripts/ never ships) |
| `hooks/` | Enforcement at Claude Code events, the mod; `session-mark.sh`, the one bash writer of the session mark, sourced by the bash and seat gates | Decisions: the helper makes them |
| `evals/` | Machine proof that the contracts hold | Production logic |
| `docs/` | Architecture, decisions, ADRs, validation | Rules the model must follow at run time (those are in skills, doctrine or references) |
| `types/` | The mod's TypeScript types | — |
| `.claude-plugin/` | The plugin and marketplace manifests; main's marketplace entry names the `release` branch (D45) | — |

## 4. The council home and the run folder

A project's council lives in `.council/` at its root. A linked worktree finds the main checkout's
home (`council_home`). Committed or ignored follows the project's sharing setting (D16).

| File | Written by | Read by |
|---|---|---|
| `council.config.md` | `council init` (template: `references/templates/`); the user's hand edits are theirs | the helper (`configured_*`) and `council status` through `council.records.config`, `session-start.sh` |
| `conventions.md` (memory) | `council memory` on the user's words | the helper, `council status` |
| `design.md`, `stack.md`, `known-problems.md` (the book, when the project keeps no such file of its own: the config's `## Book` names each page) | council-init on the user's yes (the design and stack pages); `council book note` and `book waive` (known problems) | every agent (the design and stack pages, through the review's brief and a task's orders: `council book`); a review (known problems) |
| `map.md` | council-init's mapping seats; `council map touch` (the `## Changes <date>` lines) | the SessionStart banner, `council map status`, the plan check, `council context build`, `council run close`, briefs |
| `ledger.tsv` | `council run close` | `council ledger` |
| `asks/`, `plans/`, `reviews/`, `logs/`, `postgames/`, `research/` | each mode's Deliver | later runs (`council prior`) |
| `cards/<slug>.md` | the Chair at Brief, the first time a run selects the seat, by the rules in `references/templates/seat-card.md`; a council-init refresh rewrites a stale one | briefs (`- ref:`), `council collect` (the seat's `ref:` line), `council doctor` |
| `runs/<date-time>-<mode>/` | one run's working folder, below | |

Scripts read the files in these tables through `src/council/records`, never with a parser of their own.

Inside a run folder:

| File | Written by | Read by |
|---|---|---|
| `session-state.md` | `council run open`, `council state` | the helper (`field`), the scripts through `council.records.state`, the mod, `session-start.sh` |
| `run-plan.tsv` | the Chair, checked by `council run plan check`; a review's and a build's are written by `council run open` from their templates and changed by the Chair only where their comments say | the helper, `council run audit`, `council evidence`, `council status`, `quick_validate.py` |
| `events.tsv` | the helper only, through `event_append` (contract: `references/run/event-stream.md`) | the helper, `council run audit`, `council repair` |
| `seats.tsv`, `usage.tsv` | `council seat`; the agent gate records a build seat `running` as its builder goes out (`seat.taken`) | the helper, `council run audit`, `council status` |
| `agent-starts.tsv` | the agent gate (`council cap check`) | the helper, `council run audit`, `council status` |
| `ask.md` | the Chair (the user's words) | `council check`, `council ask save`, `council status` |
| `brief.md`, `seats/`, `verify-<n>.md`, `synthesis.md` | the Chair and its agents; a review's brief, and a build's for its reader and runner (the review's template with `build-brief.md`'s blocks, D56), a health pass's for its reader (with `health-brief.md`'s block, D65), and a post-game's for its pair (with `postgame-brief.md`'s block, D67), are written by `council run open`, and the Chair fills only their `<…>` lines | `council collect`, `council check`, `council run audit`, `council evidence` |
| `gates/` | `council gate`; `council check` writes `gates/reverted/after-<n>-with-change.txt` and `after-<n>.txt`, its revert check's two outputs, which no gate reader reads | `council check`, `council evidence` |
| `check.md` | `council check`; in a build it ends with the receipt's `Checked by machine:`, `Not proved:` and `Your decisions:` lines | the Chair (the receipt, those three lines copied word for word), the audit |
| `audit.md` | `council run close` (the audit with `--at-close --save`, through `records/audit_file`); a close again rewrites it | `council status` (the closing card), `council run status`, a later session |
| `repairs.jsonl` | `council gate` / `council repair` (`repair_trail`) | `council repair`, `council memory propose`, `council status` |
| `restore.md` | `council restore point`, once, before a build changes the project (the commit it names is kept by `refs/council/restore/<run>`) | `council restore show` |
| `report-<n>.md` | the builder (a builder agent on seat `task-<n>`, or the Chair in a Solo build), at each round of task n (its head: `references/run/builder-rules.md`, The report; `builder-report.md` the checks of it) | `council patch save`, the seat gate (`builder_stop`), `council seat task-<n> done` |
| `patches/` | `council patch save` (`T<n>-<r>.patch`, `.json`, and the task's history `T<n>.md`); `council patch hold` (`T<n>-held.patch`, removed by `council patch apply <n> --held`) | the verifier, a fix round's builder (its orders link `T<n>.md`), `council patch show`, `council patch apply|revert`, `council check`'s revert check, the seat gate (`builder_stop`) |
| `index.md` | `council index` | seats |

## 5. Entry points

- **Skills** (what the user invokes): `council`, `council-init`, `council-review`, `council-plan`,
  `council-implement`, `council-research`, `council-postgame`, `council-health`, `spec-writer`,
  `test-architect`, and `context-core`, which no mode invokes (council-review, council-implement,
  council-plan, council-research, council-health and council-postgame are each their own page: D47, D56,
  D60, D65, D67; `council`, the whole loop, has no run of its own and follows the plan and build pages: D64).
- **Agents**: `small-council:council-worker`, `small-council:council-verifier`,
  `small-council:council-builder`.
- **Helper commands** (`council help` gives exact syntax; `references/run/helper-commands.md` gives the
  purpose of each): `home`, `sharing`, `init detect|scaffold`, `pushes`,
  `run open|close|status|resume|plan|events|audit|export|turn-end`, `state`, `seat`,
  `cap`, `cap allow|check`, `index`,
  `evidence build|check`, `repair`, `gate`, `gates`, `book`, `restore point|show`, `changed`, `collect`, `check`, `patch save|show|apply|revert`, `context build`, `tree`, `map status|touch`, `fingerprint`,
  `memory`, `prior`, `ask`, `ledger`, `status`,
  `correct`, `doctor`, `version`, `help`.
- **Hooks**: SessionStart → `session-start.sh`; PreToolUse Agent, Task, Workflow → `agent-gate.sh`;
  PreToolUse Bash and PowerShell → `bash-gate.sh`; Stop → `turn-end.sh`; SubagentStop worker, verifier and builder →
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
  `check:`, `audit:`, `NOTHING WAS CHECKED`, `TIMED OUT`, `UNWRITTEN <path>`, `Wrote <path> — …`; on a
  build, `council check`'s three receipt lines, `Checked by machine: …`, `Not proved: …` and
  `Your decisions: …`, which the Chair copies word for word.
- **The council home's file and folder names** (§4), the run folder's naming
  (`runs/<YYYY-MM-DD-HHMMSS>-<mode>`), and every TSV's columns and their order.
- **Event types, subjects and detail keys**, as `references/run/event-stream.md` lists them.
- **Seat doc paths**: the 14 seat docs, `guardrails.md` and `build-proof.md` stay at the root of
  `references/`, because project files carry their paths (a roster's doc column, a card's `source:`, a
  plan's `Ref:`, comments in the config). Moving one breaks every installed project.
- **Config keys** in `council.config.md` (`approve without asking`, `agent cap`,
  `seat models`, `models`, `build tier`, `checking`, `open items`, `pushes`, `sharing`, `notifications`,
  `estimate per worker`, `estimates`, `gate time limit`, `memory budget`, the Gates table's columns, and the `## Book` lines: `design`, `stack`, `decisions`, `known problems`).
- **JSON schemas**: `council.run-status/1` (`council.seat-advice/1` went with `ledger advice`, D44).
- **Formats agents and checks parse**: the index line
  (`<n> · <severity> · <principle> · <path:line> · <title>`), map.md's `## Changes <YYYY-MM-DD>` lines
  (`- <area>: <line>`), `ref:` proof of reading, `quote:`,
  verdict words (CONFIRMED / REFUTED / UNCERTAIN / MISCITED; OK / INCOMPLETE / REGRESSION /
  SCOPE-CREEP / CANNOT VERIFY; MET / PARTLY MET / NOT MET / CAN'T TELL), memory entry ids (AP, EC,
  D, F), `Principle N` numbering in seat docs; `council check`'s proof word `REVERT-PASSED`.
- **The build seat** (D42): the agent `small-council:council-builder`; the seat slug `task-<n>`
  (`task-` and digits, a build seat only in a council-implement run; role `worker` in the run plan);
  the file word `report-<n>` the agent gate reads from its dispatch; the dispatch block's lines
  (`Seat: task-<n>`, `Run: <run folder>`, `Start: …`, `Write <run folder>/report-<n>.md`); its
  one-line returns (`Wrote <run folder>/report-<n>.md — task <n>, round <r> saved`, `NEEDS: <question>`,
  `NEEDS: fix <file:line> · does: … · should: … · seen: …`, `BLOCKED: <reason>`); the tool word
  `builder_stop`; the path `references/run/builder-rules.md`, the builder's one page, which the
  builder's contract, its orders and council-implement name (D56), and `references/run/builder-loop.md`,
  kept on disk though no build reads it since.
- **Saved rounds on and off the files**: `council patch apply|revert <task> [--round <r>]`, the flag
  `--round`, and `gates/reverted/` in the run folder; `council patch hold <task>`, `council patch apply <task>
  --held` and `patches/T<n>-held.patch`.
- **Environment variables**: `COUNCIL_ALLOW_NO_HOOKS`, `COUNCIL_ALLOW_PUSH`, `COUNCIL_ARG_CONV_EXCL`,
  `COUNCIL_BASE`, `COUNCIL_BASH` (the bash running `bin/council`, for the commands that
  print or start it), `COUNCIL_INDEX_CAP`, `COUNCIL_INDEX_NAMECAP`, `COUNCIL_PLUGIN_ROOT`,
  `COUNCIL_RAN`, `COUNCIL_RUN`, `COUNCIL_SCRIPT` (`script`: `bin/council` runs a tool through
  `commands/script.py`, for the seat gate). Named values: `COUNCIL_MEMORY_SIZE_LIMIT` (`records/memory.py`, the default of `- memory budget:`),
  `COUNCIL_NEXT_AT_OPEN` (`records/state_write.py`), `COUNCIL_VERSION` (`commands/help.py`).
- **Hook-only commands**: `council run turn-end` (the Stop hook) and `council run session-start` (the
  SessionStart hook: the session's orientation on stdout, nothing else, exit 0).

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
| A new command or a check | A module in `src/council/commands/` and its row in `dispatch.COMMANDS` (D24) | Help text, `references/run/helper-commands.md`, a scenario in `evals/run_cli.py` |
| A new analysis or view over run files | A module in `src/council/commands/` (a tool) or `src/council/views/` (a view) with a `main(words)`, named in `script.TOOLS` and run through the helper, reading run files through `council.records` | Its own `evals/run_<name>.py` suite |
| A config setting | A reader in `council.records.config`, the template line and its comment in `references/templates/council.config.md` | A missing line has a stated default; an unknown word reads as the default and says so |
| An enforcement at a Claude Code event | A thin `hooks/<event>.sh` that asks the helper | `evals/run_hook.py`, including the fault path that must let the call through |
| A design decision | `docs/decisions.md` (an ADR in `docs/design/` when it weighs options) | A CHANGELOG line in the same branch |
| A test | `evals/run_cli.py`, `evals/run_hook.py` or the script's own suite; `evals/run_structural.py` only for document contracts | A scenario over a phrase pin wherever behaviour can be run (D25) |

## 8. How we do X here

One way per recurring job. Code that does one of these jobs another way gets folded into the one
way, never kept beside it. Rows marked **(debt)** have more than one way today. The cleanup (§10)
folds them, and new code uses the named way.

| Job | The one way | Notes |
|---|---|---|
| Find the council home | `council.records.home.council_home`; with none, the next step for every mode is `home.NO_SETUP` (run status, doctor; run open words it per mode) | A worktree resolves to the main checkout's home |
| Find the run a command is for | `council.commands.resolve.run_folder`: `--run`, then `COUNCIL_RUN`, then this tree's one in-progress run, then the one this session drives on another tree. Two candidates at any step are a refusal naming `--run`; it never guesses (D6). This tree's run, when another session drives it, is found only for a command that reads (`READS`); one that writes is refused, naming `run resume --run` for the user to decide | |
| Read a config setting | `council.records.config`, one function per key, with a stated default, each reading its `- key: value` line through `config.pref` (the key in any capitals, a `# note` or `(note)` after the value off, the value compared lower-cased); a value it can't read is said once on stderr (`config.unread`) and listed by `council doctor` (`config.problems`, against `config.SETTINGS`) | `records/sharing.py` and `records/pushes.py` read their line through `config.pref`, and the push freeze holds on a value it can't read; a heading the helper looks for matches through `cells.heading` (any capitals, a trailing `(…)`); `hard_rules` reads the `## Hard rules` section word for word |
| Tell whether a run is on this tree | `council.records.runs.here`: its code-root is this tree, blank or '-', for the run listing, `resolve`, `cap`, the agent gate and the SessionStart banner | |
| List the runs | `council.records.runs.listing`: each state's header as `state.header` reads it (exact keys); a run is open when its header's status is in-progress or paused | |
| Read a run's state field | `council.records.state` (`field`, `header`) over `text`, the one guarded read: a link, a file outside the run or one over 4 MB reads as ''. `unread` says why it left a state out, with the next step (D19), for `council state`, `run resume` and the events-schema stamp `council.records.events` reads through `text` | |
| Find a run's filed request | `council.records.request.filed`: the file the state's `ask:` (or ask.md's `continues:`) names, and only inside the project's `.council/asks`, for `council check` and the status's closing card | |
| Record an event | `council.records.events.append` under the run's event lock; nothing else writes `events.tsv` | A False return is no failure: a run with no stream, or a once-only event already there |
| Write a shared TSV row | Under the run's lock (`council.records.locks`); never join a torn line. `council.records.paths.append_row` writes one row so: the head first in a new or empty file, never joined to a torn last line (the agent gate's starts, `cap allow`, the repair allowances); `seat_write.add` does the same for seats.tsv, usage.tsv and tools.tsv under `seats.tsv.lock`, taking it unless its process holds it; the home's `ledger.tsv` is rewritten under `ledger.tsv.lock` | **(debt)** the event stream's own writer appends without that guard |
| Swap a file in | `council.records.paths.swap_in` (and `atomic_write`, which writes the temporary file beside it first): `os.replace` as `mv` did, tried again for about a second while Windows refuses because another process has the file open | State, events repair, a gate's `--invalid` mark, the memory file, seats, the ledger and every `atomic_write` caller |
| Take a run file's lock | `council.records.locks` (`acquire`, `release`); a command holds it for a block with `council.commands.event_note.locked`, which refuses with the holder and the site's own sentence. The owner file names the holder by the operating system's process id, checked by `council.records.owners.holder_alive` (D33) | No hook takes a lock |
| Refuse something | `raise cli.Refusal("<why — and the next command>")`: `council: <why>` on stderr, exit 2. From a hook: the helper prints `Small Council: …` on stdout with exit 2, and the hook moves it to stderr | Every refusal names what to do next (D19) |
| Take the user's go | `council state decision="<their words>"` (with `task=<n>`, one task's alone), read back with `council.commands.rounds.decisions_since` after the event it unlocks (with a task, the whole run's and that task's own, for its stop, third check and third fix round; with none, the whole run's only); an entry's minute, task and words through `council.records.state.decision`, a task's share (the whole run's and its own) through `decisions_for`, for `context build`, the receipt's `Your decisions:` line and the warning about a brief that leaves one out (`council.commands.collect.unbriefed`, given by `council state phase=work` before dispatch and by `council collect` after) | Never inferred, never the Chair's words (D7). The one store of the user's decisions: no second file of rulings |
| Hand a path to awk | Through `ENVIRON`, never `-v` (Windows backslashes) | Only the hooks keep awk |
| Run Python from the helper | `bin/council` alone: one candidate order chosen without running anything (`python3 python`; `python python3` under Git Bash, MSYS2 and Cygwin), started with `-E -s` and the words as typed. Exit 85 (the entry's own refusal of a Python older than 3.8), 126, 127 or 49 tries the next candidate unless the command itself ran (`COUNCIL_RAN`); with none left it refuses, naming the command (D24, D34). A tool or a view runs in the command's own process through `council.commands.script` (`run`, `captured`, `load`, each a module of the package); `COUNCIL_SCRIPT=script` starts `commands/script.py` instead, the seat gate's one way to a tool | With no Python every command refuses, `help`, `-h` and a bare `council` among them; the SessionStart hook then prints one line in a project with a council home (Python 3.8+ needed, checks off until installed) and nothing elsewhere |
| Start a ported command | `council.commands.dispatch.COMMANDS` maps the command words to one module, imported on use. A new command adds a row there and its module in `src/council/commands/`; a stdlib module only some commands need is imported inside the function that uses it, never at the top of a module every command loads (D34) | `tests/py/test_launch.py` holds both |
| Read the command line | `council.commands.cli` (`parse`, `takes_flags`, `no_words`, `Refusal`); each command's module holds its own word counts and `--run` refusals | |
| Match the user's words | `council.records.request` (`fold`, `found`, `verdict`): `council check`'s quotes and next tasks (`council.records.quotes`), and the plan check's Serves rule | |
| Read a gate verdict | `council.records.verdicts` (`number`, `text`, `command`, `holds`, `green`) over `gates/<name>.json`, for `council gate`, `gate --all`'s reuse of a green on the same tree, and `council check` | |
| Name the files a gate ran on | `council.git.files_tree`: `git add -A` into a copy of the index, then `git write-tree`; every file on disk, ignored ones, `.council/` and Python's bytecode (`__pycache__/`, `*.pyc`, `*.pyo`: `git.CACHES`) left out. A build round's diff and the files a seat names as changed outside a round are taken from it too. A gate's verdict keeps `council.git.disk_tree` as `"tree"` (`council.commands.gate_run`): the same files, each as its bytes on disk (no line-end conversion or `.gitattributes` rule), from an index of the council's own in the worktree's git folder (`council-disk.index`), so only a file whose stat changed is read again; `''` (the gate runs) for a submodule with changes, git older than 2.40 or a rule in `.git/info/attributes` | Two trees are compared with `council.git.between` after the `--`: the council home and `git.CACHES` left out on both sides, so a round saved before `CACHES` lists no bytecode as deleted (patch save, the files outside a round, `unchanged_under`) |
| Take a green instead of running a gate | `council.commands.gate_reuse.taken`: the gate's last green with the config's command, on the very tree on disk now (#68), or, for a row with a `Covers` cell, on a tree whose files under those paths are the same (`council.git.unchanged_under`, #47) when every one of them matches a file (`council.git.unmatched`, which `council doctor` asks too); `not_rerun` words the second. Asked by `gate --all` (`gate_set._reused`) and the receipt (`receipt.py`) | A tree git can't read is never taken: the gate runs |
| Read the Gates table | `council.records.gate_table` (`gates`, `gates_listed`: one `Gate` per row, the header found by the column names (`named`), the optional `Covers` cell as `covers`), for `council gate`, `gate --all`, `council gates`, `council doctor` and `run close`'s warnings; `init_write.fill_unprobed` places a row's cells by `named` | |
| Say what a gate command's text gives away | `council.records.gate_notes` (`notes`, `backslash`, `winswitch`): a pipe, a fallback, a captured runner, a dropped backslash, a Windows switch, for `council gate` and `council doctor` | |
| Read a plan row | `council.records.plan.keyed` over `council.records.cells.tab_rows` (lines from `cells.lines_of`: split at newlines only, each line's trailing CRs cut): the value is the fourth cell, trimmed of spaces and tabs only and never lower-cased, the keys exact, the first row of a key wins; `plan.budget`, `plan.selected`, `stages.required` and `seat_rows` read it | `council run plan check` judges every row itself (`plan_check.py`) |
| Read a number | `council.records.cells.optional_number`: plain ASCII digits, 1 to 12 of them, ends trimmed; `cells.leading` is that number or 0. Anything else is not a number | |
| Tell whether a path is absolute | `council.records.home.absolute`: rooted (`/` or `\`) or with a drive (`C:`), on every OS, for any path that arrives as text (a state file, the config, a user, git); a caller that opens it goes through `home.native` first | `records/memory.py`'s `absolute` keeps its own meaning: a leading `/` is the repo's root |
| Read the roster | `council.records.config.roster_table`, the one reader of the config's Roster table, for `council doctor`, `council memory select` and the status's seat names | |
| Split a Markdown table row | `council.records.cells.table_cells`: at each pipe outside a code span, an escaped pipe kept as text (`raw`: as written, for a row rewritten in place); the Roster and the map's one-way table read through it | **(debt)** `gate_table.table_cells` (the Gates table), `converge.table` and `evidence.cells_of` keep their own splitters |
| Budget an agent | The Chair, from the config's `- estimates:` line (each role's figure), else `- estimate per worker:`, within doctrine's size limits, recorded in `run-plan.tsv` and judged by `council run plan check` | No command computes the figure since `route recommend` went (D44); `council doctor` names a figure it can't read (`config.SETTINGS`, `config.ESTIMATE_ROLES`) |
| Say which hooks ran | `council.records.hook_marks` (`put`, `ran`, `seen`): a hook leaves `<session id>.<hook>` (and the bare `<session id>`) under `small-council/sessions/` in the user's cache; `council doctor hooks` and the SessionStart banner read them. A hook that has not fired yet is not seen, not broken | Two writers, one per language: `hooks/session-mark.sh` for the bash and seat gates (no Python start on a gate's path), `hook_marks.put` for `council run session-start`, `run turn-end` and `cap check`. Only `put` prunes marks 30 days old |
| Read the memory file | `council.records.memory` (`locate`, `rows`, `served`, `would_serve`, `oversized`, `size_note`, `placed`, `proposals`, `replace`, `COUNCIL_MEMORY_SIZE_LIMIT`) and `memory_entries` (`rows`, `pending`, `section`), for `council memory`, `council doctor`, `run open`, the SessionStart hook and the views. `council status` finds the file with `memory.locate`, says its size through `memory.size_note` against `config.memory_budget` (as run open, a complete close and `council doctor` do) and counts its proposals with `memory.proposals`, as the SessionStart banner does | |
| Read a run's event stream | `council.records.events` (`ready`, `check`, `show`, `repair`), for `council run events` and `council doctor` | |
| Read the ledger | `council.records.ledger.raw_rows`, for `council ledger` | The typed reader went with `ledger advice` (D44) |
| Build the claim index | `council.commands.evidence.build`, the one writer of `claims.jsonl`: for `evidence build`, `evidence check` (which builds it, then checks it), `memory propose claim` and a complete `run close` (through `script.captured`). The Chair never runs one evidence command to make another work (D44) | `council status` and `council run audit` only read it; the audit names `evidence check` for one missing or out of date |
| Read a gate's saved output | `council.commands.gate_output` (`zero_tests`, `failure_ids`, `missing_module`, `never_ran`) | |
| Read a seat file and its citations | `council.records.seat_files` (`brief_seats`, `items`, `shape`, `verify_problems`, `ref_title`, and `blocked`, the one reader of a `BLOCKED:` line, in a seat file's head or a builder's reply), `council.records.citations` (`parse`, `rows`, `ranges`, `line_verdict`) and `council.records.seat_rows`, for `council collect` and `council check` (the run files they name, `brief.md` to `index.md`, in `council.records.run_files`); a citation's status and origin in `council.commands.cite_check` and `cite_origin` | `hooks/seat-gate.sh` keeps its own copy of the item-section rule (no Python start on the gate's path) |
| Redact the user's words | `council.records.redact` (`redact`, bytes in and bytes out, with the count; `said`, a flattened one-line copy), for `council check`'s quotes, `council ask save`, `council memory`'s drafts and answers, `council state`'s decisions, `cap allow` and `repair allow` | |
| Run a gate | `council gate` (`council.commands.gate_exec.execute`): `bash -c` in a process group of its own, a watchdog process stopping the whole tree at its limit; on Windows through `/proc/<pid>/winpid`, a group TERM, then `taskkill /T` | A project's command starts through `council.commands.shell`: the bash on PATH, the caller's `MSYS2_ARG_CONV_EXCL` back (`COUNCIL_ARG_CONV_EXCL`), and on Windows a command line written the way Git Bash's runtime splits it (`argv_for`) |
| Record a build's repair attempt | `council gate` (`council.commands.gate_repair`) and `council repair` run `council.commands.repair_trail` through `council.commands.script` (`run`, `captured`), in their own process; `council.records.repairs` owns `repair-allowances.tsv` | — |
| Write the map | `council.records.map_file.touch` through `paths.atomic_write`, for `council map touch`: lines under a dated `## Changes`, each ending `(at <commit>)`, the stamp moved only when every stale area is covered. How far the map is behind HEAD, by top-level area, is `map_file.stale` (its stamp, whether that commit is in the history, the commits since and the files changed since by area, an area touched later counted from its touch), the one reader for `council map status`, `council map touch`, `council doctor`, the close's `map-touched` warning (with `disk`, uncommitted changes counted) and the SessionStart banner; a map-commit HEAD doesn't have (`aside`) is from another line of history. The areas changed since a commit are `map_file.areas` over `map_file.changed` | The one-way table and the other sections are never rewritten |
| List memory merges and retirements | `council memory tidy` (`commands/memory_tidy.py`): numbered operations, nothing written; the user's yes applies each through `memory.replace` | Rules now enforced by a hook are not looked for: nothing reads what the hooks enforce |
| Write a run's state | `council.records.state_write.change`: `council state`, and `run open`, `resume`, `close` and `turn-end` through it (`raw_lines` and `council.records.paths.atomic_write(keep_mode=True)` for a header rewrite of its own); `clear_waiting` is a thin caller, and `council index` and `council ask save` set their fields through `change` too | |
| Count an agent | `council seat` records it; the agent gate (`council cap check`, `src/council/commands/agent_gate.py`) counts starts; the ledger is written at close | One record per agent run, by id (`references/run/run-accounting.md`) |
| Measure a run's method load | `council.records.stages.method_files` and `method_bytes`: context-core's skill, the mode's own and the doctrine of each stage it enters (all ten when none are named), or a one-page mode's own page alone (a review's, D47; a build's, D56; a plan's and research's, D60; a health pass's, D65; a post-game's, D67), or `/council`'s page and the two it follows (`stages.FOLLOWS`, D64), each file's bytes with CRLF read as LF. `evals/run_structural.py` holds a review's and a build's under 16,000 bytes with it, a plan's under 12,500, research's and a health pass's under 10,500, a post-game's under 14,000, and the whole loop's under 36,000; `run close` records the run's figure, over `stages.required`, as `method_bytes=` on `run.chair_usage` | No second list of what the Chair loads |
| Point a seat at its reference | The roster's Reference cell (`council.config.md`, `## Roster`), the one place a surface maps to its doc: a brief block's `- ref:` is the seat's card, else that doc (doctrine `04-brief.md`, Cards first); `council collect` checks the seat's `ref:` line against what its block names | Never the whole set of seat docs. Not for a review: its reader and runner have `ref: none`, and their role text in the brief is their lens (D48) |
| Read what a run's agents used | The per-seat rule: `council.records.usage` (`seat_list`, `usage_totals`, `usage_words`, `reported_runs`, `agents_share`, `standing`), read by `council cap`, the agent gate, `council seat`'s notes, `run close`, the ledger and the status card | — |
| Hold a build to its verifier rounds | `council.commands.rounds`: one checker per batch, and no third check without a diagnosis or the user's go, for the agent gate and `council seat … running`. Since D56 a build starts a verifier only for a protected subject's finding | |
| Hold a build to its fix rounds | `council.commands.rounds.third_fix_round`, asked by `council patch save`: no third fix round in the same files without a redesign and the user's go (D38) | Beside the verifier-round rules, in the same module |
| Save a build round and check its report | `council patch save` (`src/council/commands/patch.py`): the head through `council.records.report_head`, the diff from `council.git.files_tree`'s tree, the checks in `patch_checks.py`, the rounds in `council.records.patches`; what a round is diffed from with no `--base` is `patch.since`, which `context build` names too | The round's diff is taken between two trees, never from the index or HEAD |
| Read a task word | `council.records.tasks.number`: 3, T3 or task-3, the whole word | For `council patch`, `council context build`, and `council tree`'s match of a Converge row and a seat slug |
| Find a build task's slice | `council.commands.task_slice` (`plan_of`, `of`, `cut`, and `paths_in`, the one reader of a cell's paths: a backticked span whole, the rest split at commas): where a build's tasks come from (`<run>/tasks.md` when the Chair wrote one, else `input=`: a plan's Task Sequence or a post-game's Next tasks), the task's Owner and Touches and the map row its Owner names; `plan` refuses with no `input=`, an unreadable plan, or one that lists no tasks (`missing` for the build seat) | For `patch save`, `context build`, `tree`, the build seat and the receipt |
| List a round's workaround signs | `council.commands.patch_checks.SIGNS`: one `(kind, pattern)` per sign, matched by `signs()` on added lines of code only (documents skipped), for `council patch save` | Questions for the verifier, never verdicts |
| Build a task's orders | `council context build task-<n>` (`src/council/commands/context.py`): printed, never written; `CEILING` 8,000 bytes; whole parts dropped from the end and named under Left out. The builder runs it itself, as its first command; a fix round's orders link the task's own history, `patches/T<n>.md` | Reads only through `records/`; doctrine is linked by path, never copied; the Chair's dispatch never pastes the orders (D3) |
| Build one round of a task | `references/run/builder-rules.md`, the builder's one page (D56), followed by the builder agent (`agents/council-builder.md`) or by the Chair in a Solo build | council-implement keeps the Chair's part: the dispatch, the checks after the task, the log, the state, the commit |
| Hold a build to one builder | `council.commands.build_seat` (`SEAT`, `start_refusal`, `dispatch_refusal`, `missing_report`, `outside_round`), asked by `council seat task-<n> queued|running|done` and by the agent gate for a council-builder: one build seat at a time (taken from its `queued`, not only while `running`; the agent gate lets a builder out only while its seat is queued, and records it `running` as it goes, under the seat lock, so a second builder for the same seat is refused until the Chair records the first one's line, or `failed` and `queued` again for a dispatch that started no agent: `council.commands.seat.taken`), no start of a task that is or depends on a standing `NEEDS: fix` stop, a finished seat owes its `report-<n>.md`, and `council seat` names each file changed outside a saved round (D42) | The one home of the `task-<n>` pattern: `evals/bench.py` reads it from here. `Depends on` is followed at every level, and is the stop's one list |
| Read a task's stop | `council.commands.build_seat.stop_of`: a seat's `NEEDS:` note is `resolved` once the task's own `after-<n>` gate passed after the stop (by the event stream's order), `released` once a decision of the user's is on record from the stop's minute on, else it `stands`; `resolved_tasks` gives `council tree` its `was stopped:` | The stop's moment is the seat's first finish (done, failed, blocked or skipped) after its last start, never the row's `updated` cell. The one `NEEDS:` reader (`needs`, `fix_at`) is in `records/seat_write.py`, where the note itself ends when the seat has run again and is recorded `done` with no note. With no event stream nothing is refused |
| Judge an agent's stop | `hooks/seat-gate.sh` (SubagentStop): a worker's and a verifier's in bash; a builder's through `council.commands.builder_stop` (`COUNCIL_SCRIPT=script bin/council builder_stop`, exit 1 and one line to send it back once) | A BLOCKED reply is read only by `seat_files.blocked`: for a worker and a verifier the hook asks `builder_stop blocked` the same way (exit 1: no BLOCKED reply); no Python, or a fault, lets the stop through (D20) |
| Take a saved round off the files, or put it back | `council.commands.patch_apply` (`undo`, `redo`: `git apply`, all or nothing, the files named when it won't go), for `council patch apply|revert`, `patch hold` and `apply --held`, and the revert check | No record changes; `git apply` is called nowhere else |
| Write the receipt's machine lines | `council.commands.receipt.lines`, printed by `council check` on a build and filed in `check.md`: `Checked by machine:` from the gate records, `Not proved:` from the proofs, the gates and the revert checks, `Your decisions:` from the run's state | The Chair copies them; it may add to `Not proved:`, never cut |
| Find the plugin's own files | `council.records.home.plugin_root`: `CLAUDE_PLUGIN_ROOT` when set, else the package's own folder; for `context build` and the SessionStart banner | `doctor.py` and `run_open.py` still find it from `__file__` themselves: folding them is its own task |
| Give a builder its rules | `references/run/builder-rules.md`, its one page, linked from a task's orders (D56) | Never copied into a brief; the builder reads no other council reference unless the page sends it there |
| Print the task tree | `council tree` (`src/council/commands/tree.py`): the request, then the plan's tasks under each Serves quote | Reads only through `records/` |
| Read a project's own decisions at setup | `references/roster/decision-records.md`, read by council-init: a project's own decisions log is adopted in place as the book's (D53), and each decision stated outside one a `- PROPOSED decision:` line under conventions.md's `## Proposed`, citing `file:line`; the map's `## One way per job` table filled from the records and the code | No command accepts one: the user's yes is moved by hand |
| Find the project's book | `council.records.book.pages`: each page's `- <page>: <path>` line under the config's `## Book`, else its default under the council home (the decisions log: the memory file, `memory.locate`); `council book` prints them, `council run open council-review` fills the brief's `## The book` and `council context build` names the first three on its first line, all through `council.commands.book` (D52) | The one-way-per-job table stays in `map.md` (`map_file`); the design page points at it |
| Write a known-problems line | `council.records.book.add`, for `council book note` and `book waive`: a dated line at the end of its section, the file made from `references/templates/known-problems.md` the first time, the same words written once, through `paths.atomic_write` (D55) | A fixed problem's line is deleted by hand |
| Write a project's setup files | `council init scaffold` (`commands/init.py`, `init_write.py`): from `references/templates/`, never over a file already there; a Gates row is ✓ only from a probe in the setup run (a failed probe whose broken twin could not run, by `gate_output.could_not_run`, as `✓ … fails today`), every other candidate `✗ not probed`; on a `setup: quick` config, with a setup run open, only its `✗ not probed` rows are filled (`init_write.fill_unprobed`, by the header's column names); the candidate checks come from `init_checks.found` alone | The Chair writes the judgment: the roster rows and their markers, the Stack section, the map's prose |
| Start a first review with no setup | council-review's page (Convene, and `references/run/quick-setup.md`): a review in a project with no config runs `council init scaffold --quick` only to make the council home, and goes on reading none of its roster (D43, D48); every other mode runs council-init first (doctrine `01-convene.md`, step 2) | Never a roster tailored inline: the quick setup takes the catalog's seats as they are |
| Open a review, a build's check at the end, and a design | `council run open council-review` (`commands/run_open.py`): the plan from `references/templates/run-plan-review.tsv` and `<run>/brief.md` from `review-brief.md`, the run, its folder, the code root and the council home filled in; a missing template is a refusal, as the plan's is (D48). `council run open council-implement` writes the same brief with `build-brief.md`'s blocks on its `{{BUILD}}` lines, and its plan from `run-plan-implement.tsv` (D56). `council run open council-plan` and `council-research` write the plan from `run-plan-design.tsv` (the designer; `designer-2`'s rows commented, for what is hard to undo, D61) and the brief from `design-brief.md`, the designer's role text word for word (D60); a new project's setup run takes the same two designers from `run-plan-init.tsv`'s commented rows, its brief from the same template filled by the Chair (D63). `council run open council-health` writes the plan from `run-plan-health.tsv` (the reader; the runner's rows commented) and the review's brief with `health-brief.md`'s block on its `{{HEALTH}}` line (D65); `council run open council-postgame` writes the plan from `run-plan-postgame.tsv` (the reader and the runner) and the review's brief with `postgame-brief.md`'s block on its `{{POSTGAME}}` line (D67); `council run open council` is refused, naming the plan run and the build run it is made of (D64) | The Chair fills only the brief's `<…>` lines and never rewords the role texts; no seat comes from the roster |
| Take a restore point, and go back to it | `council restore point` (`commands/restore.py`, `records/restore.py`): a commit of the code root's files by `git.files_tree` and `commit-tree`, kept by `refs/council/restore/<run>`, in `<run>/restore.md`, once per run; `council restore show` prints what changed since and the commands that put every file back (D57) | Nothing in the project moves, and no command runs the undo: that is the owner's call |
| Record how long the checks take | `council gates timed <minutes>` (`commands/gate_list.py`), from the runner's `checks:` line: the config's `- checks take: <n> min (measured <date>)` line, replaced in place or added after `- gate time limit:`, through `paths.atomic_write`; read by `council.records.config.checks_take`, and printed last by `council gates` | A missing line means not measured yet; a review's estimate uses the line |
| Write a seat's card | The Chair at Brief (doctrine `04-brief.md`, Cards first), before the seat blocks, for each selected seat with none; the rules live in `references/templates/seat-card.md`'s comment alone | Setup writes none; a refresh rewrites only a card that exists |
| Read the build log's Converge table | `council.records.converge.read`, for the status's closing card | |
| Stamp a time | `council.clock`: `now_date` (the one date-only stamp), `now_min` and `now_sec` (local), `now_utc`; `local_moment`, `utc_moment` and `iso_moment` read a stamp back | |
| Read a diff's files and lines | `council.diff` (`files`, for `council patch`; `header`, the one reader of a hunk header, for `cite_origin.hunks`, `hygiene` and `index.hunks`) | |
| Check a run plan | `council run plan check` (`src/council/commands/plan_check.py`; a delivered plan's tasks in `plan_tasks.py`, `references/run/run-plan.md`, Plan tasks). `council state` (each phase from Brief on), `council seat … queued/running` and `council doctor` reach the same check through `council.commands.plan.check` | A closed run's plan is judged by the settings of its day; Full needs a decision of the user's since the run opened (D7) |
| Prove a build task | `council gate before-<id>` / `after-<id>`, checked by `council check` (`references/build-proof.md`). For an `ok` change proof of a task with saved rounds, `council check` runs the after check in a scratch copy written from the tree's own blobs, first with the change on (the control, which must pass), then with every round saved since the task's first taken off, newest first, the task's test files and every round file the command names kept as they are now (`council.commands.revert_check`; `proof_reach.named_files`): it must then fail, or the proof reads `REVERT-PASSED`. A control that fails when the after-check's tree is not the files' now is `AFTER-STALE`; a proof with no revert check whose after-check ran on other files is named under `Not proved:` | A revert check that can't be made is said, and listed under `Not proved:`; never a pass |
| Check the Chair's steps | `council run audit`, the one checker: from the records, and from the session transcript the size and cost before the first dispatch, the status card at it, the rulings as one question, the closing card and how the helper was called (`commands/audit_steps.py`, `audit_calls.py`). `evals/run_replay.py` replays the saved runs in `evals/fixtures/runs/` through it: each passes, and each planted mutation FAILs on its step alone | A step the Chair must take gets an audit item with a scenario in `evals/run_audit.py`, never a second checker |
| Export a run for a fixture or a bug report | `council run export --anon <run> <dest>` (`commands/run_export.py`): only the files the audit reads, through `records/`; paths, session ids and free words through `records/anon.Anon`; times kept; the transcript's part for the run as transcript.jsonl | A fixture is made by `evals/run_replay.py --remake` from scripted runs, never copied from a real one |
| Check a document's contract | A structural pin in `evals/run_structural.py` | Only for documents; behaviour is proved by running it (D25) |
| Build what a user installs | `scripts/build_release.py <folder>`: the tracked files under its `SHIPPED` list, one place, with the reason for each, and the three files written for the tree (`plugin.json` without `experimental.evals`, `marketplace.json` of `"./"`, a README); a checkout with uncommitted shipped changes is refused unless `--worktree` (never for a release) | `evals/run_release.py` proves the tree stands alone; a file the plugin needs at run time goes under a shipped folder, never in `docs/`, `evals/`, `tests/` or `scripts/` |
| Publish what a user installs | `scripts/publish_release.py <remote> <branch>`: builds, runs `evals/run_release.py --tree` on the build, commits exactly the build's records (their modes from git) in a scratch repository with the branch's tip as parent, and pushes, never forced; the same tree is nothing to do, a version not newer than the tip's is refused. `.github/workflows/release.yml` runs it at each `v*` tag, a person by hand (CONTRIBUTING.md) (D45) | No git command of the publish lives in a workflow or a doc |
| Hold a limit (a size, a count, a lint warning) | A number in `evals/ratchet.json`, measured by `evals/run_ratchet.py`; it may only go down, and `--update` keeps a gain | Never a hand-kept list of files or exceptions |

## 9. Naming

- **Bash** (the hooks and the launcher only): snake_case functions, `<noun>_<verb>` or a plain verb
  (`mark`, `block`). Locals are declared with `local`.
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

Measured on 2026-11-17:
- `bin/council` is a 53-line bash launcher: it finds a Python 3.8+ and starts `src/council/`, which
  holds about 22,500 lines of Python. The bash that stays is the five hooks, frozen by the ratchet.
- No script parses `session-state.md` or `run-plan.tsv` by hand: every reader goes through
  `src/council/records` (S1).
- The skills and agents are under their size caps: council-implement is at 14,480 of 20,000
  characters (its log template and its Deliver now load at the stage that uses them), council-init at
  19,875, the verifier contract at 7,980 of 8,000. A review run's method load is 55,023 bytes.
- `python evals/run_all.py --fast` is the fast tier (about a minute); the full suite still takes about
  30 minutes on Windows. Many structural evals still check that a phrase is present; new behaviour is
  proved by a scenario (D25).

The cleanup's workstreams. [`design/cleanup-plan.md`](design/cleanup-plan.md) has the target layout
(`src/council/`, D32), the rules every session follows, and the sessions in order:

| WS | What |
|---|---|
| 0 | This page, `decisions.md`, the root `CLAUDE.md` |
| 1 | One Python library for config and run files; every script moves onto it; the copies go |
| 2 | `bin/council` split into Python modules, one area per branch, with commands, output and exit codes unchanged (the eval suite is the proof). *Started (S3):* `bin/council` hands ported commands to `src/council/__main__.py`; `home`, `sharing` and `run status` live in `src/council/commands/`, and bash and Python writers share run-file locks (D33). *S4:* `cap` and `cap check` (the agent gate) followed; `seat`, `correct` and `cap allow` wait on the ledger and redaction (S8) and the state writer (S8b). *S5:* `run plan check`, `run plan show` and `route recommend`; the bash that stays runs the same plan check through `python_run`. *S6:* `gate` (one gate, `--all`, `--invalid`), `gates` and `changed`, with the repair glue: a gate stopped at its limit takes every process it started on Windows and POSIX, and `python_run` tries no next Python when the command that ran exits 127 itself (`COUNCIL_RAN`). *S7:* `collect`, `check` and `index`, on `records/` readers for seat files, citations, quotes and gate verdicts; `check` hands the user's words to bash's redaction and back (`COUNCIL_REDACT`), and `index` leaves earlier council work and the impact graph to bash. *S8:* `map status`, `fingerprint`, `doctor`, `memory` (index, select, check, propose, accept, reject), `prior`, `impact`, `ask save` and `ledger`, with redaction in `records/redact.py`: `check` is one Python pass and `COUNCIL_REDACT` is gone, `index` finds earlier work and refreshes the impact graph itself, and `bin/council` went from 5,171 lines to 3,541. *S8b + S9:* every remaining command: `state`, `run open|close|resume|events|audit|turn-end`, `seat`, `cap allow`, `correct`, `context`, `evidence`, `repair`, `tune`, `history`, `outcomes`, `tui`, `status`, `pet`, `help` and `version`, and the SessionStart hook's body as `council run session-start`. `bin/council` went from 3,541 lines to 53: it finds a Python and starts it, and no hook sources it. The scripts run in the command's own process. *S11:* `scripts/` moved into the package, the tools into `commands/` and the views into `views/`: nothing is loaded by path, no script runs `bin/council` back, and `council gate` reaches the repair trail through the one runner. The copies went onto one owner each (§8): a file's lines, git, a file's bytes, a run file's lock, the stamps through `clock`, the status card's stop through `records/usage.py`. `src/council/` and `scripts/` together went from 24,629 lines to 23,248, the cut of packs included. Left: the folds whose copies disagree on odd input (each a behaviour choice with its own scenario and CHANGELOG line), `ask.py` and `memory_write.py` reading the date with `time` themselves, and `gate_run.json_esc` |
| 3 | File layout: `references/` by audience, evals into fast unit and scenario tiers. *Done (P3):* `references/run/`, `spec-writer/` and `test-architect/`; the fast tier (`run_all.py --fast`) |
| 4 | Quality gates as ratchets (ShellCheck, ruff, a type check on the library, size and complexity limits frozen at today's worst), and this page's rules as tests. *Started (S2):* `evals/run_ratchet.py` holds sizes, ShellCheck warnings, parsers, config readers and call-backs; `ruff.toml` runs on the whole tree. The type check is still to come |
| 5 | Slop pass: story comments out, a naming pass, dead code deleted, duplicates folded |
| 6 | One rule, one place: rules cited by id, doctrine loaded per surface (#67). *P2:* 62 restated rules now live in their owner (§7) with a pointer left behind, a brief links only its own seats' cards and docs, and `evals/run_structural.py` checks that each folded rule's wording is in its owner only. Ten copies that disagreed were settled one way on the user's rulings, and a check keeps the stale wording out. A review run's method load fell from 59,387 to 56,970 bytes, and is 55,023 now; `run close` records each run's figure beside the Chair's tokens (`stages.method_bytes`). *Done (P2),* with the duplicates the final review found folded since, and the build's and post-game's Deliver forms loaded at Deliver |
| 7 | Tests: a fast tier, behaviour over phrase pins, the Chair drill eval (#70). *Started:* the fast tier, and `evals/run_replay.py`, which replays saved runs through `council run audit` with no model; phrase pins are still being turned into scenarios |
