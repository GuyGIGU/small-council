# Phase 9 — seat learning

## What changed

- `council ledger advice [N] [--json]` reports each seat's record over the last N completed runs
  (default 20). It counts:
  - only runs that judged its items;
  - useful items (kept and not refuted), with a 90% plausible range;
  - refuted items among those a verifier checked;
  - tokens per run and per useful item.
- It gives advice only past a stated bar: 3 judged runs and 15 items of evidence, at most five from
  any one run. Below the bar it says "too little to judge" or "never judged".
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

`evals/run_seats.py`: 30 checks, no model, about 3 s. They cover:
- the range arithmetic and the per-run cap;
- split and round-2 workers;
- unjudged runs;
- the bar's edges;
- each piece of advice, reached well inside its region;
- one useful item in five over four runs is still "unclear";
- dropping only after eight runs, and only as a question;
- the costly mark;
- the window, loose credit (also through a round-2 worker), unreadable lines, CRLF, a BOM and a
  form feed;
- uneven runs: one big run counts as at most five items of evidence;
- no ledger;
- the helper handoff, with each refusal's own message.

Removing the per-run cap makes four of the checks fail, so they test what they claim.

Also run:
- structural: 602/602 at the first commit;
- the helper suite (`run_cli.py`, which exercises the plain ledger table): 520/520 on `59c6485` in
  16.5 min on Windows Git Bash.

## Independent review

A reviewer checked `59c6485` without access to my reasoning. It found:

| # | Severity | Finding | Fix |
|---|---|---|---|
| 1 | medium | "at most five items a run" was a total of 5 × judged runs: one big run, or runs where the seat raised nothing, could stand in for three runs of evidence | evidence is counted run by run (at most five from each run, its useful items scaled alike); the bar counts that evidence |
| 2 | medium | the refresh doctrine's worked example could never come out of the advice (14 items, 7 verified) | the example is now real output of the code (6 runs, 8 of 30 useful, 12 of 20 refuted → narrow) |
| 3 | low | loose credit was checked per row, missing credit that arrives through a round-2 worker | checked per seat per run, after folding |
| 4 | low | a BOM, a form feed or a blank line made the advice and the plain table read different rows | `utf-8-sig`, split on `\n` only, and the table skips a row with no run |
| 5 | low | `council ledger advice 00` reached Python's own usage text | refused by the helper |
| 6 | low | list membership made long ledgers quadratic | sets and per-run tallies |
| 7 | low | tokens per seat-run counted worker rows (split workers twice) | totalled per seat per run |
| 8 | low | this document promised a helper-suite result it did not give | given above |

The reviewer also found two tests that could not fail: one tested refusals by exit code alone, and
one tested the 100% clamp on input that could never pass 100%. Both now assert what they claim.
It also noted that the plain table still diluted a mixed seat's shipped share with a council-init
run's items. Shipped now counts only the items a synthesis judged, and the table says so.

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

## Platform check update — 2026-09-28

Automatic macOS and Linux checks passed for the released code in CI runs
`36305577961` and `36319880515`; this is not validation by a person using those hosts.
