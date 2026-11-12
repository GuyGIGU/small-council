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

## Records

| Id | Decision | Source | Held by | Supersedes |
|---|---|---|---|---|
| D26 | Usage figures are exact or marked: blank means unknown, never zero, and every figure carries a basis (complete, running, partial, suspect, older, none). | 0.14 (`docs/design/status-widget-adr.md`) | `status.py`; `evals/run_status.py` | |
| D27 | The event stream is append-only and written only by the helper. | 0.9 (`references/event-stream.md`) | `council run events check` | |
| D28 | Memory is filed only on the user's words; an observed-failure entry needs a verdict that establishes it and is labelled "observed failure, not a rule". | 0.13 (`docs/design/memory-provenance-adr.md`) | `council memory`; `evals/run_memory.py` | |
| D29 | Rates across runs are shown only past five runs that carry their data; self-tuning changes one knob (the estimate per worker), only on the user's words, logged and reversible. | 0.13 (`history-adr.md`, `self-tuning-adr.md`) | `history.py`, `tune.py` suites | |
| D30 | Model routing is opt-in (`- seat models: on`) and only for mapping and survey worker seats; the Chair and the verifier stay on `inherit`. | 0.17 (`docs/design/model-routing-adr.md`) | `council run plan check` | |
| D31 | Advisory routing (`council route recommend`) proposes; it never mutates a run, launches an agent or claims to meter tokens. | 0.10 (`docs/design/adaptive-routing-adr.md`) | `evals/run_cli.py` | |
