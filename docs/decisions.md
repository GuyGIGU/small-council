# Decisions

The settled decisions of Small Council, one line each, cited by id from code reviews,
[`architecture.md`](architecture.md) and plans. A settled decision is not re-argued and not "fixed" by
a later change. To change one, add a new entry that supersedes it: same table, the old id in its
**Supersedes** cell, and the old row's status set to `superseded by Dn`. Ids are never reused or
renumbered.

**Source** says where the decision was made and argued: an ADR in `docs/design/`, a CHANGELOG
version, or the user's words on a date. **Held by** says what keeps it true: a test, a hook, a helper
refusal, or `prose` when only the text holds it. A `prose` row is a candidate for enforcement.

## Method

| Id | Decision | Source | Held by | Supersedes |
|---|---|---|---|---|
| D1 | One head: the Chair (the main session) decides; seats advise in their own context windows; the user rules. | kernel laws 1, 9 (`skills/context-core`) | prose; structural pins on the laws | |
| D2 | Mechanics live in the helper, not in prose: a step a script can do or check is a `council` command. | kernel law 5; CONTRIBUTING | prose | |
| D3 | Prose points down, never sideways. A mode never restates the kernel, a dispatch message never restates an agent's contract, and a rule lives in one place. | CONTRIBUTING | prose; WS6 enforces it | |
| D4 | Parallel readers, one writer: agents read and write only their own seat or verify file, and only council-implement's Chair edits project code. | kernel law 2 | `seat-gate.sh`; agent contracts | |
| D5 | Every claim is blind-verified against the code: the verifier never sees who made a claim, why, or the plan. | 0.3 doctrine (`docs/design/doctrine-0.3.md`) | verifier contract; post-game brief rules | |
| D6 | The helper never guesses between runs: an ambiguous run is a refusal naming `--run`. | `resolve_run`'s contract (`evals/run_cli.py` header) | `resolve_run`; `evals/run_cli.py` | |
| D7 | The user's go is their recorded words (`council state decision="…"`), dated after the event it unlocks; never inferred, never the Chair's words. | 0.15, 0.21 | `decisions_since` refusals (Full size, third check, cap, one checker per batch) | |
| D8 | Every run is sized, budgeted, reported and closed; a run can't close complete before Deliver or skip a required stage. | kernel law 10; 0.21 | `council run close`, `council state` refusals | |
| D9 | Approval carries forward: an instruction to proceed approves up to the config's `approve without asking` size; Full always needs the user's explicit size-and-cost go. | 0.20 | `council run plan check` | |
| D10 | Rulings, not stalls: inside the approved scope the Chair decides and logs a `Ruling:`; it stops only for destruction, a push or shared branch, a public contract, or scope or budget beyond approval. | 0.22 | prose (council-implement) | |
| D11 | A build ends at its plan's last task plus one fix round after converge; anything beyond is a follow-up, never a hunt inside the build. | 0.22 | prose (council-implement) | |
| D12 | Proof, not opinion: a build task's proof is a before/after gate pair, or a declared preservation pair, checked by `council check`; NOTHING WAS CHECKED is never a pass. | 0.7 (`docs/design/quality-0.7.md`) | `council check`, `council gate` exit 4 | |

## Shape and size

| Id | Decision | Source | Held by | Supersedes |
|---|---|---|---|---|
| D13 | A skill stays under 20,000 characters and 500 lines (Claude Code re-attaches only its start after compaction); a stage doctrine file under 6,000 characters; the verifier contract under 8,000; a review run's method under 59,407 bytes. | `evals/run_structural.py` (size budgets) | `evals/run_structural.py` | |
| D14 | Modes are thin: they invoke `context-core` and add `## At <Stage>` sections only where they differ. | CONTRIBUTING | structural pins | |
| D15 | Seats come from the catalogue and the project's config, never from a skill; John Carmack chairs and is never a seat. | 0.1.0 | structural pins | |
| D16 | Sharing: `team` commits `.council/` with the project; `just me` keeps it out of git and out of anything teammates read. | 0.19 | `council sharing`; `council check` hygiene | |

## Build checking

| Id | Decision | Source | Held by | Supersedes |
|---|---|---|---|---|
| D17 | Build tier: `light` (the default) records a before/after pair only for risky tasks; `full` records one for every task. The tier sets how much proof, never what counts as proof. | 0.22 | `council check`; structural pins | |
| D18 | Checking: `one per batch` (the default) gives a build one verifier, at converge; a second needs the user's go. `per task` verifies risky tasks one by one and batches the rest. A verifier judges the Done-when and nothing wider; a post-game's next tasks cite the request. | issues #46, #56, #66; the user, 2026-11-12 | `batch_check_refusal`, the agent gate, `council check`; `evals/run_cli.py`, `evals/run_hook.py` | |
| D35 | A plan task carries the tree: `Serves` quotes the part of the request it serves, word for word (a support task quotes its parent's); `Owner` names the job of the map's one-way-per-job table it extends, or says `New way:` and why, which goes to the user as a ruling and into memory as a decision; `Rests on` lists its facts with their evidence states. A task resting on an `ASSUMED` or `INFERRED` fact outside the repo depends on a probe or research task. `council run plan check` refuses a delivered plan that breaks one; a map without the table skips the owner check and says so. | the user, 2026-11-13 (`docs/design/task-tree.md`, decided items 1 and 4; #93) | `council run plan check` (`src/council/commands/plan_tasks.py`); `evals/run_cli.py`, `tests/py/test_plan_tasks.py` | |
| D36 | "I don't know yet" is an answer. A builder's `NEEDS: <question>` is a correct outcome, recorded `done`, never `failed`; a failure nobody can explain stops code changes until a probe measures it; the Chair may run one probe or research seat a run inside the approved budget and asks the user before a second. On a build or a fix the verifier returns INCOMPLETE for a change that contradicts a recorded decision or adds a second way beside the map's table, citing the id or row. | the user, 2026-11-13 (`docs/design/task-tree.md`, decided item 3; #64, #93) | prose (`references/run/repair-loop.md`, Unknowns; `references/build-proof.md`, Checking); `evals/run_cli.py`; drill D29 | |

## Helper and hooks

| Id | Decision | Source | Held by | Supersedes |
|---|---|---|---|---|
| D19 | Every refusal says what to do next: the command, the flag, or who must say go. | 0.22 | `evals/run_cli.py` checks the refusal text | |
| D20 | A hook never blocks work because of its own fault: unreadable input, a missing helper or a helper fault lets the call through. Nothing a hook prints goes to stdout (Claude Code may read it as JSON). | 0.17 | `evals/run_hook.py` fault cases | |
| D21 | A council command is never piped into head, tail or grep (the pipe hides its exit status and refusals); redirect to a file and read that. | 0.21 | `hooks/bash-gate.sh` | |
| D22 | Bash 3.2 portable (macOS), Git Bash on Windows, Linux; no jq; paths reach awk through `ENVIRON`. Holds for every line of bash that remains. | CONTRIBUTING | CI on three OSes; ShellCheck on changed files | |
| D23 | Contract names are frozen: skill, agent and command names, arguments and exit codes, run-folder files and TSV columns, event types, config keys, JSON schemas, parsed formats, env vars ([architecture §6](architecture.md#6-contracts-names-a-cleanup-never-renames)). Renaming one is its own decision with a migration, never part of a cleanup. | the user, 2026-11-12 | prose; the eval suite pins the names | |
| D24 | Python 3.8+ is a hard dependency. New logic is written in Python; the bash helper moves to Python modules one area at a time, with commands, output and exit codes unchanged. Hooks stay thin bash. | the user, 2026-11-12 | not yet (WS1–WS2) | |
| D25 | Behaviour is proved by running it: a scenario that runs the helper or a hook beats a pin that a phrase is present. Structural pins are for document contracts only. | the user, 2026-11-12 (the cleanup plan) | not yet (WS7) | |
| D32 | Standard library only at run time: the plugin installs nothing on the user's machine. Linters and type checkers are development tools, used in CI only. The Python package lives in `src/council/`, with `records/` the only code that parses a council file. | the cleanup plan (`docs/design/cleanup-plan.md`), 2026-11-12 | not yet (the ratchet in S2) | |
| D34 | A ported command starts one Python process and no probe: `bin/council` runs `src/council/__main__.py` with `-E -s` on the first candidate (`python` then `python3` under Git Bash, MSYS2 and Cygwin; `python3` then `python` elsewhere; chosen without running anything, nothing remembered). The entry parses under Python 2.7 and refuses one older than 3.8 with exit 85 before importing anything but `sys`; exit 85, 126, 127 or 49 (the Microsoft Store's stand-in, its 9009 as MSYS reports it) sends the call to the next candidate, so no ported command exits with one of those; with none left, the D24 refusal. Not `-I`: Python 2.7 and 3.0-3.3 stop on it before reading the file, so the entry takes its own folder off the path itself. The dispatcher imports only the module of the command it runs, and a stdlib module only some commands need (`tempfile`, `shutil`) is imported where it is used. `impact_python` keeps its probe, in the same order, for the `scripts/` entry points until they are ported (S9). | the planning session, 2026-11-13 (S3: `council home` went from 237 to 581 ms) | `evals/run_cli.py` (python launcher); `tests/py/test_launch.py` | |

## Records

| Id | Decision | Source | Held by | Supersedes |
|---|---|---|---|---|
| D26 | Usage figures are exact or marked: blank means unknown, never zero, and every figure carries a basis (complete, running, partial, suspect, older, none). | 0.14 (`docs/design/status-widget-adr.md`) | `status.py`; `evals/run_status.py` | |
| D27 | The event stream is append-only and written only by the helper. | 0.9 (`references/run/event-stream.md`) | `council run events check` | |
| D28 | Memory is filed only on the user's words; an observed-failure entry needs a verdict that establishes it and is labelled "observed failure, not a rule". | 0.13 (`docs/design/memory-provenance-adr.md`) | `council memory`; `evals/run_memory.py` | |
| D29 | Rates across runs are shown only past five runs that carry their data; self-tuning changes one knob (the estimate per worker), only on the user's words, logged and reversible. | 0.13 (`history-adr.md`, `self-tuning-adr.md`) | `history.py`, `tune.py` suites | |
| D30 | Model routing is opt-in (`- seat models: on`) and only for mapping and survey worker seats; the Chair and the verifier stay on `inherit`. | 0.17 (`docs/design/model-routing-adr.md`) | superseded by D37 (was `council run plan check`) | |
| D37 | A model per role: `- models: builder=, review=, verifier=` in the config names the model of each role's agents, as the Agent tool takes it (`inherit`, `fable`, `opus`, `sonnet`, `haiku`). Every role defaults to `inherit`; council-init proposes a split from the session's model and the user confirms it. The Chair stays on the session's model. A verifier is never on a weaker model than the builder it checks (haiku < sonnet < opus < fable; `inherit` is the session's model; in a build the Chair, which builds, counts as a builder). `- seat models:` keeps D30's mapping and survey overrides. `lead=` waits for #63. | the user, 2026-11-12 (#65; `docs/design/cleanup-plan.md`, #65) | `council run plan check` (`src/council/commands/plan_models.py`); `evals/run_cli.py` (models), `tests/py/test_models.py`, `tests/py/test_plan_models.py` | D30 |
| D31 | Advisory routing (`council route recommend`) proposes; it never mutates a run, launches an agent or claims to meter tokens. | 0.10 (`docs/design/adaptive-routing-adr.md`) | `evals/run_cli.py` | |
| D33 | A run file's lock is taken only from a holder that is dead, never from one that reads alive, however old. Its owner file names the holder by the operating system's process id, whichever language wrote it: Python `os.getpid()`, bash its Windows id under Git Bash, MSYS2 and Cygwin (`/proc/$BASHPID/winpid`, read in the holding shell; 2.8 ms). bash reads an owner as alive if it is alive under either reading, its own `kill -0` or, on Windows, `ps -W` (~50 ms; `/usr/bin/kill -0 -W` finds only processes MSYS started), so a waiter there looks on its first try and every tenth, and gives up at 20 s by the clock; Python stays strict: line 1 is an operating-system id, checked with OpenProcess (0.04–0.07 ms), and it never reads `gates.lock` before S6. Unchanged: the owner file is made with O_EXCL, an ownerless lock is stale at 10 s, reclaiming goes through `<lock>.recover`, and a lock is stale only while its file still names that holder. An owner line no process could have written (not digits, 0, or past the id type: 2^32-1 on Windows, 2^31-1 elsewhere) is no owner in both languages, so the lock goes stale once 10 s old like an ownerless one: no live holder can have written it, and the 10 s covers a writer still taking the lock. Limits: only Python, on Windows, treats a live process made more than 2 s after the owner file as another process given a dead holder's id; bash's either-reading check errs only toward alive, so a dead holder whose number is a live process of the other kind blocks waiters until they give up, loudly; plugin versions mixed during an update are unsupported. `gates.lock` keeps bash's own id on line 1 until S6: it has no Python reader or writer before then, and three scenarios stop its holder with bash's `kill -TERM` or `kill -9 "$(head -n 1 …/owner)"`, which on Windows takes only bash's numbers ("gate lock: a gate call stopped by a signal releases its lock…", "gate lock: a gate call killed outright leaves its lock…", "gate time limit: a helper stopped by TERM stops the gate…"). S6 moves it to the operating-system id and changes how those scenarios find the pid; the helper itself never signals a process named in an owner file (its gate stops use the `$!` it kept). | the planning session's answer to S3's lock proposal, 2026-11-13 | `evals/run_cli.py` (lock across languages); `tests/py/test_owners.py` | |
