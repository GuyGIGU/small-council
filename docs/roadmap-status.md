# Roadmap status — what is built, tested, used for real, and deferred

This page follows the evolution roadmap's phases (0–13), plus the status widget and run accounting
added after 0.13.0. It keeps four things apart:
- **Implemented**: the code exists.
- **Automatically tested**: machine checks pin it (listed suites; CI runs them on Windows, macOS and
  Linux).
- **Validated in real use**: a real council run with real agents exercised it, and the result was
  checked.
- **Deferred**: roadmap scope that was not built, or not measured.

Checks passing is never counted as validation in real use. The real runs so far:
- the September 2026 Chrollo build, begun on 0.7.1 and read by the new version;
- two fresh council reviews of the status-widget change (2026-09-27): two seats plus a 4-agent
  verifier Workflow, then one seat plus a 2-agent verifier Workflow, the second entirely on one
  version.

The 0.19.0 changelog also reports a second logged run: a plan followed by a 15-task build with blind
verification. The phase-by-phase evidence below has not yet been reconciled with that run's artifacts;
its older "not yet seen" entries describe the evidence recorded here, not an assertion that the
later run omitted those features. The current instruction and preservation-proof refinements have
local automated checks, not a new live agent run.

| Phase | Implemented | Automatically tested | Validated in real use | Deferred |
|---|---|---|---|---|
| 0 Baseline and audit | 0.8 (docs) | — | — | — |
| 1 Structured run model (run plan) | 0.8; the stop at the agent cap or token ceiling (a hook, `council cap allow`) in 0.15 | `run_cli`, `run_hook` | Yes: the fresh run's plan was checked, and seats were gated on it. It counted 3 planned agents where 6 really ran (the verifier was a 4-agent Workflow), which only the new accounting shows. The stop was seen live once (2026-09-29), in a practice run set up at its 2-agent cap: it refused a real agent start, the Chair asked, and once the user's go was recorded the agent ran. No real council run has reached it yet. | Stopping the agents a running Workflow starts (the hook sees only the Workflow call) |
| 2 Event contract | 0.9 | `run_cli` | Yes: the fresh run wrote 32 events, and `events check` passed | — |
| 3 Adaptive routing | 0.10 | `run_cli` | No: the fresh run was sized by hand | — |
| 4 Impact engine | 0.11; removed 2026-11-15 | — | No run showed it changed findings or tokens | — |
| 5 Precision context | 0.12 (opt-in, off); removed 2026-11-15 | — | No | — |
| 6 Evidence model | 0.13 | `run_evidence` | Partly: copied verifier parts caused duplicate conflicts; a later rebuild omitted --run after close and failed, leaving the Judge-time index stale. The second run never built an index | — |
| 7 Closed-loop diagnosis | 0.13 | `run_repair`, and `run_status` drives it through the helper | Partly: an earlier live drill recorded three failures, but its trace was lost | — |
| 8 Memory evolution | 0.13 | `run_memory` | No | — |
| 9 Seat learning | 0.13 | `run_seats` | The first checked ledger rows exist only in temporary review clones; no durable council home has accounting-2 rows. Advice needs three judged runs | — |
| 10 Benchmark harness | 0.13 (never run) | `bench.py self-test` | No | The paid comparison |
| 11 TUI | 0.13, plus the shared status line (0.14); removed 2026-11-15 | — | Never used | — |
| 12 Historical analytics | 0.13 (`council history`); removed 2026-11-15 | — | No | — |
| 13 Self-tuning | 0.13 (one knob); removed 2026-11-15 | — | No | — |
| Run accounting | 0.14 | `run_status`, `run_cli`, `run_seats` | Yes: both fresh runs' figures are exact from their notifications (627k across 6 agent runs; 235k across 3). The Chrollo run was corrected from transcripts, each figure derived twice, including 8 agent runs it never recorded: 26.4M across 220 | — |
| Status widget | 0.14 | `run_status`, `run_structural` | Partly: five cards rendered in the desktop app (the Chrollo preview; the first fresh run at start, at a controlled failing check, and at completion; the second at start), and every read left the run unchanged. Waiting and paused were read as text only. Stale was seen on the real Chrollo card. Recovery in progress and blocked are test-only; unknown is a missing/unreadable-record fault state | Live updates (the host shows snapshots); claude.ai/code and IDE extensions not verified |
| Limits, closing card and alerts | 0.15: the agent cap counts agent runs; spend against the estimate and an optional token ceiling; the stop at the limit; the closing card; `status --line` alerts; the memory-size warning; finding outcomes (removed 2026-11-15). 0.16: the card, text, `--line` and JSON (`usage.limit`) say whether new agents are stopped or allowed on the user's go | `run_cli`, `run_hook`, `run_status` | Partly: the stop was seen once, in a practice run (see Phase 1); the first logged real run (a Chrollo review, 2026-09-30) showed the spend against its estimate but neither the first-dispatch card nor the closing card — the numbered steps and the helper's reminders added after it are not yet seen in a real run | — |
| Desktop pet | 0.16: `council pet`; removed 2026-11-15 | — | No: never used in a real run | — |
| Python helper | Unreleased (S1–S11): every command in `src/council/`; `bin/council` a 53-line launcher | the whole suite, `tests/py`, the ratchet | Not recorded here: no logged real run on it yet | — |
| Builder agent per task (D42) | Unreleased: `council-builder`, one at a time, from a queued `task-<n>` seat; the agent gate and the seat gate hold it | `run_cli` (models, gates), `run_hook`, `run_replay` | No: no real build has dispatched a builder agent yet. A first-day walk-through on 2026-11-17 played every builder by hand | The paid builder-vs-Chair comparison (`evals/bench.py`) |
| Task tree (T1–T5) | Unreleased: plan tasks with Serves, Owner and Rests on; the report head and `council patch save`; the task's orders (`council context build task-<n>`); `council tree`; the `NEEDS: fix` stop | `run_cli`, `tests/py` | No: no real plan or build has used it | — |
| Revert check and the receipt lines | Unreleased: `council check` reruns an `ok` proof with the task's rounds taken off; prints `Checked by machine:`, `Not proved:` and `Your decisions:` | `run_cli` | No | — |
| Run audit from the transcript, and the replay | Unreleased: the close keeps `<run>/audit.md`; transcript items (size before dispatch, the cards, one rulings question, refusals tried again) | `run_audit`, `run_replay` | No: a 2026-11-17 walk-through with no real agents found false FAILs for agents sent before a run opened | — |
| Gates reused, `Covers` | Unreleased: a green gate on the same files is not rerun; `Covers` paths per gate | `run_cli` (gates) | No | — |
| Push freeze, model per role, memory budget | Unreleased: `- pushes:`, `- models:`, `- memory budget:`, `council memory tidy` | `run_cli`, `run_hook`, `run_model_routing`, `run_memory` | No | — |
| Council pane | Unreleased: a Claude Code mod (`hooks/council-view.tsx`) | `claude plugin test .` (CI's mod job) | No | — |

Whether the council beats plain Claude Code is unmeasured.

- 2026-10-18: the light build tier (references/build-proof.md, Tiers; `- build tier:` in the config) — implemented and pinned by evals/run_structural.py; not yet validated in a real run.
