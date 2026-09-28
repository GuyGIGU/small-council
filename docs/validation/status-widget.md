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
  planned seat. It also labels outdated claim indexes.

## Tests (automatic; Windows, Git Bash 5.3.9, Python 3.14; all 17 checks run on committed code 6bd6bb9, 2026-09-28)

| Suite | Result | Covers |
|---|---|---|
| `evals/run_status.py` (new) | 87/87 | accounting through the helper; the two readers agreeing on eleven helper-written cases, including no-agent runs; the added-run check is separate; corrections and their refusals; every state, including failing, recovering and blocked driven through `council gate` and `council repair`; the widget's escaping, size, time and labels |
| `evals/run_cli.py` | 525/525 | the whole helper, including accounting, planned-verifier collection and missing/stale-index close warnings |
| `evals/run_tui.py` | 24/24 | cockpit, shared status line, snapshot/2, and stale-index labels with no writes |
| `evals/run_history.py` | 18/18 | older runs left out and named |
| `evals/run_tune.py` | 25/25 | tuning from complete runs only |
| `evals/run_seats.py` | 33/33 | unknown and older ledger costs never priced; a verified run with an unknown cost stays verified |
| `evals/run_hook.py` | 139/139 | session start; open runs name text/widget commands and read_me; closed or absent runs do not |
| `evals/run_structural.py` | 631/631 | widget/exact-usage rules, Workflow file placement, and refusal-preserving helper calls |
| `evals/run_impact.py`, `run_context.py`, `run_evidence.py`, `run_repair.py`, `run_memory.py` | 21/21, 37/37, 25/25, 37/37, 55/55 | evidence covers Workflow parts, joined copies and true conflicts; other suites check side effects |
| `evals/bench.py self-test`, `run_context_pilot.py`, `run_phrases.py` | 46/46, runs clean, 74/74 | unchanged areas; the phrase check is advisory |
| `scripts/quick_validate.py` | 0 warnings | |

All checks above ran in a detached throwaway worktree at `6bd6bb9`; subsequent changes are
validation-document updates only. There were no model calls or paid evaluations.

The raw run records, rendered cards, older suite logs, Track A test logs and replay report are saved
outside the repository under `Documents/Small Council Validation/2026-09-28`. A SHA-256 manifest there
verified all 336 copied files against the temporary originals.

CI runs every suite on Windows, macOS and Linux. The branch is not pushed, so those two platforms are
not yet run.

**CI maintenance (2026-09-28).** Both workflows now use v7 of
[checkout](https://github.com/actions/checkout),
[setup-python](https://github.com/actions/setup-python),
[setup-node](https://github.com/actions/setup-node) and
[upload-artifact](https://github.com/actions/upload-artifact), where applicable; their v7 action
manifests were checked to use Node 24. The behavioural workflow also installs Node 24.
The [Ubuntu 26.04 image rollout](https://github.com/actions/runner-images/issues/14748) starts
2026-10-19 and is scheduled to finish 2026-11-19. On the first CI run after rollout begins, inspect
the runner image and Tool versions output before attributing a failure to code. No run on that
future image is claimed here.

**Automatic replay of the recorded failure (2026-09-28, `6bd6bb9`).** In a disposable copy of
`2026-09-27-193355-review`, the four verifier parts were restored beside the joined file.
`evidence build` exited 0 with 12 claims, exactly one link per claim, 10 CONFIRMED and 2 REFUTED.
SHA-256 fingerprints confirmed the original run files were unchanged. This checks the fix against
the original inputs; it is not a new live council run or a re-score of the old review.

## Validated in real use

The Track A follow-up of 2026-09-28 fixes copied verifier rows, false collection gaps, stale claim
index display and close warnings, SessionStart widget instructions, and portable correction JSON.
These fixes have regression checks; a new real council run has not yet validated them.

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
  across 212), and showed the real stale state: "No recent activity … 3 h 50 min".

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
  progress and blocked. Unknown is a fault state for a missing/unreadable status file; stale was seen on the real Chrollo preview.
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
  - terminal text is supported; IDE extensions reportedly show text and the command, but that host behaviour is unverified.
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
- **Its synthesis omitted evidence states**, producing 13 missing-state issues. Workflow parts
  were readable (12/12 claims linked), but copying them into a joined file created duplicate rows
  and a conflict. After moving the parts, the Chair rebuilt after close without `--run`; the
  refusal was hidden by `| tail -1`, and the run closed with its stale Judge-time claim index.
  The card therefore showed 12 unverified claims despite 10 confirmed and 2 refuted verdicts.
  The second review never built its claim index and wrote one part outside the verifier glob.
- **Both reviews falsely failed collect:** the brief listed the queued verifier as a worker.
  Track A excludes planned verifiers from worker collection and tests the corrected behaviour.
- **The waiting state was set and cleared by the Chair** to exercise it. The go-ahead came from the
  user's standing instruction.
- **The controlled failure** was `test -f .council/smoke-ok` before and after creating the file.

## What was not verified

- macOS and Linux (CI will run them when the branch is pushed).
- Recovery in progress and blocked in a real run (simulated and helper-driven only).
- claude.ai/code and the IDE extensions.
- A card after an app restart.
- A Chair other than this session following the new doctrine unprompted.
- A false stale warning during a long Workflow; unknown remains a fixture-tested fault state.
