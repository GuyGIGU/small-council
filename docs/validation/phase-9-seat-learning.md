# Phase 9 — seat learning

## What changed

- `council ledger advice [N] [--json]` reports each seat's record over the last N completed runs
  (default 20). It counts:
  - only runs that judged its items;
  - useful items (kept and not refuted), with a 90% plausible range;
  - refuted items among those a verifier checked;
  - tokens per run and per useful item.
- It gives advice only past a stated bar: 3 judged runs and 15 items. Below the bar it says "too
  little to judge" or "never judged".
- The rules and the reasoning are in `docs/design/seat-learning-adr.md`.
- `--json` gives the same report as data (`council.seat-advice/1`), for later history and tuning.
- The plain `council ledger` keeps its numbers, with two changes:
  - it shows `-` instead of `0%` for a seat no run judged;
  - it points to the advice.
- The council-init refresh proposes roster changes only where the advice clears its bar. Below the
  bar it says the record is too thin and changes nothing. The Learn stage says the same.

## Why

Refresh used to propose roster changes from raw counts. On the only real ledger available (below),
those counts rest on one judged run, and four seats read as 0% shipped although no run ever judged them.

## Architecture and compatibility

- **Read-only.** A new optional Python script reads `ledger.tsv`. Nothing is written, and the ledger
  format, run formats and routing are unchanged.
- **No Python.** Without Python 3.8+, `council ledger advice` stops and says to use the plain
  ledger, weighing no seat on fewer than 3 judged runs and 15 items.
- **New flag.** `--json` is a new boolean flag. Every other command refuses it.

## Tests

`evals/run_seats.py`: 24 checks, no model, about 2 s. They cover:
- the range arithmetic and the per-run cap;
- split and round-2 workers;
- unjudged runs;
- the bar's edges;
- each piece of advice, reached well inside its region;
- one useful item in five over four runs is still "unclear";
- dropping only after eight runs, and only as a question;
- the costly mark;
- the window, loose credit, unreadable lines and CRLF;
- no ledger;
- the helper handoff, including refusals.

Also run: structural 602/602. The helper suite (`run_cli.py`) exercises the plain ledger table; its
result is below.

## Evidence on real data

Run read-only on the one real ledger (Chrollo Project, 2026-09-26): 2 runs, 1 judged, 11 seats.
- Every seat is `collect`. Seven are "too little to judge: 1 judged run and 8 items".
- Four are "never judged" (the council-init run credited no items).
- The widest range is fowler: 2 of 8 useful, plausible 7–61%. Under the old table, that seat was a
  candidate for "narrow its surface".
- The kept-and-cut-beyond-raised note fires once (nygard-perf: 5 kept + 4 cut of 8 raised), so the
  record's crediting is loose there.

## Metrics / baseline comparison

None. No outcome data exists to show that advised roster changes improve runs. The thresholds are
stated judgment calls, not fitted values.

## Known limitations

- "Useful" is a proxy: kept is the Chair's call, and refuted covers only what a verifier checked.
- Severity is not recorded.
- A recast seat starts a new record.
- The per-run cap is a heuristic.

## Deferred

- Escaped defects per seat (from post-game runs).
- Severity weighting.
- Using the advice in `council route recommend`: routing works in generic lenses, not project seats.
- Learned budgets (Phase 13).

## Not verified

- Whether any advice, followed, improves a later run.
- A live Chair using `council ledger advice` at a refresh.
- macOS and Linux (CI runs `run_seats.py` on all three platforms once pushed).
