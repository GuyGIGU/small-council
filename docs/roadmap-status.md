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
- a fresh council review of the status-widget change (2026-09-27): two seats plus a verifier
  Workflow of four agents.

| Phase | Implemented | Automatically tested | Validated in real use | Deferred |
|---|---|---|---|---|
| 0 Baseline and audit | 0.8 (docs) | — | — | — |
| 1 Structured run model (run plan) | 0.8 | `run_cli` | Yes: the fresh run's plan was checked, and seats were gated on it. It counted 3 planned agents where 6 really ran (the verifier was a 4-agent Workflow), which only the new accounting shows. | Enforcing the agent cap at dispatch |
| 2 Event contract | 0.9 | `run_cli` | Yes: the fresh run wrote 32 events, and `events check` passed | — |
| 3 Adaptive routing | 0.10 | `run_cli` | No: the fresh run was sized by hand | — |
| 4 Impact engine | 0.11 | `run_impact` | Ran on the fresh run's diff (18 files); its correctness was not judged | Transitive and dynamic imports |
| 5 Precision context | 0.12 (opt-in, off) | `run_context`, byte pilot | No | The paired live comparison |
| 6 Evidence model | 0.13 | `run_evidence` | Partly: the fresh run built 12 claims, but its verifier file format left them unlinked | — |
| 7 Closed-loop diagnosis | 0.13 | `run_repair`, and `run_status` drives it through the helper | Partly: an earlier live drill recorded three failures, but its trace was lost | — |
| 8 Memory evolution | 0.13 | `run_memory` | No | — |
| 9 Seat learning | 0.13 | `run_seats` | The fresh run wrote the first checked ledger rows; advice needs three judged runs | — |
| 10 Benchmark harness | 0.13 (never run) | `bench.py self-test` | No | The paid comparison |
| 11 TUI | 0.13, plus the shared status line (unreleased) | `run_tui` | Yes: it drew the in-progress Chrollo run and the fresh run | Navigation and per-area screens |
| 12 Historical analytics | 0.13 (`council history`) | `run_history` | No: no council home has five complete, exact runs yet | The history dashboard |
| 13 Self-tuning | 0.13 (one knob) | `run_tune` | No: needs five measured runs; five make a proposal eligible, not reliable | Behaviour knobs (held until the benchmark) |
| Run accounting | Unreleased | `run_status`, `run_cli`, `run_seats`, `run_history`, `run_tune` | Yes: the fresh run's figures are exact from its notifications (627k tokens across 6 agent runs), and the Chrollo run was corrected from transcripts (24.8M across 212), each figure derived twice | Recording agents the Chair never logged |
| Status widget | Unreleased | `run_status`, `run_structural` | Yes: four cards rendered in the desktop app (the Chrollo preview, plus start, failing check and completion of the fresh run), and every read left the run unchanged | Live updates (the host shows snapshots); claude.ai/code and IDE extensions not verified |

Whether the council beats plain Claude Code is unmeasured.
