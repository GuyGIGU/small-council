# Status widget and trustworthy run accounting

## What changed

- **Run records** (see `references/run-accounting.md`):
  - A run's `usage.tsv` holds every dispatch and usage report. The seat figures in `seats.tsv`
    (tokens, agent runs, runs with usage) are derived from it.
  - `council seat` refuses a token count that is not one exact, plausible number (a rounded `74.3k`
    included), and a role name given as an agent id. It takes a Workflow's agent count with
    `agents=`, and `agents=0` for a seat no agent ran.
  - A seat with no agent on record has an unknown agent count, never 0.
  - `council correct` lays an exact, evidenced figure over a seat without editing it, or adds an
    agent run the record missed (`unrecorded=yes`).
- **One per-seat rule in both readers.** The helper's `seat_rows` (the close line, the ledger) and the
  cockpit's `seat_usage` (the widget, `tui`, history, tune) share the rule. A total is stated only
  when every agent run's usage is known.
- **`council status [--widget | --json]`** is the shared plain-language reading (`scripts/status.py`).
  It gives the state, what needs the user, progress without a percentage, the latest check, recent
  activity, freshness, the cost when the records support one, and where the evidence is. It is
  rendered three ways:
  - a snapshot card for the desktop app's chat;
  - text ending with the exact terminal command;
  - the headline of `council tui`.
- **The doctrine:**
  - the Chair shows the card once at first dispatch, then only on request;
  - it records exact usage;
  - it sets `council state waiting="…"` when it stops for the user.
- **The SessionStart hook** tells a new session it may show any open run's card.
- **History and tune** cost only complete, exact runs, and name the rest. The ledger prices only
  checked figures.

## Why

Council work starts in chat, but a run could only be watched from a terminal, and its numbers could
not be trusted. The one real long run of September 2026 showed:
- four token counts typed in thousands;
- five Workflows of 26–49 agents recorded as 1 agent each;
- eight agent runs never recorded;
- a reader that took the first number it saw.

History and tuning would have learned from those numbers.

## Architecture and compatibility

- **Read-only views.**
  - `status.py` and `cockpit.py` write nothing: a fingerprint of the run is unchanged after every
    read, in tests and on the real runs.
  - The widget fragment has no network, one inline script (the snapshot's age), and every record
    value escaped.
- **New files** are optional per run: `usage.tsv` and `corrections.jsonl`. `seats.tsv` gains a
  `reported` column.
  - A row without it is "older": readable, never totalled.
  - An older run carried on by the new helper keeps its old rows as they were; new seats get new rows.
- **Schemas:**
  - the snapshot moves to `council.run-snapshot/2` (a `usage` block replaces the flat totals);
  - history moves to `council.history/3`;
  - ledger rows gain an `accounting` column;
  - events add `run.waiting_changed` and `seat.usage_corrected`, and their details carry the new
    figures.
- **The TUI** gains the shared status line and the new cost wording, and stops listing the Chair as a
  planned seat. Nothing else changed.

## Tests (automatic; Windows, Git Bash 5.3.9, Python 3.14; every suite run on the final code, 869d5cf)

| Suite | Result | Covers |
|---|---|---|
| `evals/run_status.py` (new) | 81/81 | accounting through the helper; the two readers agreeing on eleven helper-written cases, including added and no-agent runs; corrections and their refusals; every state, including failing, recovering and blocked driven through `council gate` and `council repair`; the widget's escaping, size, time and labels |
| `evals/run_cli.py` | 520/520 | the whole helper, with the progress line, the close line and ledger rows updated to the new definitions |
| `evals/run_tui.py` | 22/22 | cockpit, including the shared status line and snapshot/2 |
| `evals/run_history.py` | 18/18 | older runs left out and named |
| `evals/run_tune.py` | 25/25 | tuning from complete runs only |
| `evals/run_seats.py` | 33/33 | unknown and older ledger costs never priced; a verified run with an unknown cost stays verified |
| `evals/run_hook.py` | 135/135 | session start, with the new status line |
| `evals/run_structural.py` | 629/629 | the kernel names the widget rule; the doctrine asks for exact usage |
| `evals/run_impact.py`, `run_context.py`, `run_evidence.py`, `run_repair.py`, `run_memory.py` | 21/21, 37/37, 21/21, 37/37, 55/55 | unchanged areas, rerun to catch side effects |
| `evals/bench.py self-test`, `run_context_pilot.py`, `run_phrases.py` | 46/46, runs clean, 74/74 | unchanged areas; the phrase check is advisory |
| `scripts/quick_validate.py` | 0 warnings | |

CI runs every suite on Windows, macOS and Linux. The branch is not pushed, so those two platforms are
not yet run.

## Validated in real use

Three real runs, with real agents. Each record below was checked against its source.

**1. The September Chrollo build** (begun on 0.7.1; read by the new version, then corrected).
- `council tui` and `council status` read the in-progress legacy run. Nothing on disk changed.
- Two independent agents re-derived every seat's figures from the session transcripts, and all 19
  matched. They also found 8 agent runs that were never recorded: a first check of a task, two
  surveys, and a 5-agent survey Workflow.
- `council correct` laid the figures over the run with their evidence: 38 for the 19 recorded seats,
  and 8 for the 4 missed entries, added with `unrecorded=yes`. `seats.tsv` is byte-for-byte
  unchanged.
- Both readers now give 26,430,386 tokens across 220 agent runs: every agent run the transcripts show.
  A chat preview card showed the run, taken before the 8 missed runs were added (it read 24.8M
  across 212).

**2. A fresh council review of this change** (clone of the branch, run `2026-09-27-193355-review`).
- Real agents: two expert seats, then four blind verifiers dispatched as one Workflow.
- Recorded exactly from their notifications:
  - 129,872 tokens (1 agent run);
  - 140,727 tokens (1 agent run);
  - 356,050 tokens across 4 agent runs (the Workflow, with `agents=4`).
  - The close line: "~627k tokens across 6 agent run(s)". The ledger rows are marked checked.
- **Shown as real cards** in the desktop app: running (at first dispatch), a failing check (a
  controlled one), and completed. The completed card shows the failure as recovered.
- **Exercised on this run but read only as text or data:**
  - waiting: set and cleared by the Chair before dispatch, as a deliberate exercise;
  - paused and resumed.
- **Shown only by simulated runs and helper-driven tests, never in a real run:** recovery in
  progress, blocked, stale, and unknown.
- Every read was fingerprinted, and none changed the run.
- **The code was patched and pulled in the clone during this run** (for each finding below), so
  this run mixes versions.
- **Found by the run, then fixed with a test for each:**
  - a check re-run under the same name overwrote its saved failure, so recovery was invisible;
  - a paused run's working agents were called "without a usage report";
  - a resumed run kept its stale cost line;
  - the Chair was counted as a seat;
  - the PowerShell command pointed at a Git bash without its tools;
  - "0 tokens so far across 2 finished agent runs" was said while both agents were still working;
  - "Run finished" appeared twice.
- **The review's findings.** The seats reported 12 items; the verifiers confirmed 10 and refuted 2.
  All 10 were fixed. They include the two readers disagreeing on a finished seat with no agent,
  corrections read differently by bash and Python, and a 13-digit cell crashing the views.

**3. A second, smaller review, run entirely on one version** (commit b4741d5, run
`2026-09-27-202712-review`).
- One seat (105,186 tokens) and a 2-agent verifier Workflow (129,378 tokens, `agents=2`), recorded
  exactly. The close line: "~235k tokens across 3 agent run(s)". The ledger rows are marked checked.
- A real card was shown at first dispatch, with plain seat names ("Untrusted input", "Verifier") and
  the start time in place of the folder name.
- The seat reported 6 edge cases in the unknown-versus-zero and added-run rules; the verifiers
  confirmed all 6. All were fixed after the run, with a test each (commit 869d5cf).

**The post-game.** A blind grader checked the finished work against the request. It found no unmet
requirement, and 7 partly met. The fixes since then:
- a seat with no agent on record is now unknown, never 0;
- the 8 missed Chrollo agent runs are added;
- the main view uses plain names;
- this section no longer overstates which states were seen for real.

## Metrics / baseline comparison

None claimed. This is an inspection and bookkeeping change. Whether the council beats plain Claude
Code remains unmeasured (the paid benchmark is deferred).

## Known limitations

- **A card is a snapshot.** It never updates itself. After an hour it says to ask again. Whether cards
  survive an app restart is not verified.
- **Where the widget works:**
  - verified in the Claude desktop app's Code tab;
  - reportedly also on claude.ai/code;
  - absent from the terminal and the IDE extensions, which get the text and the command.
- **What the token figure measures.** It is the harness's own figure for each agent run. It tracks
  context size, not spend.
- **Chair discipline matters:**
  - a dispatched agent never recorded is not counted until it is added from evidence;
  - a report without an agent id can't be de-duplicated;
  - a resumed agent is assumed to report a running total.
- **Stale runs.** "No recent activity" after 60 minutes can be a long-running Workflow, not a stall.
  The card says both.

## Deferred

- The history dashboard.
- The paid council-versus-Claude-Code benchmark.
- A refresh button on the card (it would add a chat message and a model call).

## Shortcuts taken

- **The validation reviews were the Chair's own tasks**, derived from the Phase 5 instruction; the
  user never asked for those reviews.
- **Its synthesis was written as an index only**, so `council evidence check` reports the claims
  without declared evidence states. The verifier Workflow wrote one file per agent; they were merged
  into `verify-1.md` and the parts moved aside. The card honestly shows the claims as unverified.
- **The waiting state was set and cleared by the Chair** to exercise it. The go-ahead came from the
  user's standing instruction.
- **The controlled failure** was `test -f .council/smoke-ok` before and after creating the file.

## What was not verified

- macOS and Linux (CI will run them when the branch is pushed).
- Recovery in progress, blocked, stale and unknown in a real run (simulated and helper-driven only).
- claude.ai/code and the IDE extensions.
- A card after an app restart.
- A Chair other than this session following the new doctrine unprompted.
- Stale and unknown states (fixture-tested only).
