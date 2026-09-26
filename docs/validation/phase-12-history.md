# Phase 12 — history across runs, gated on enough data

## What changed

`council history [--json]` (`scripts/history.py`) reads every run of the council home through the
cockpit's read-only snapshot, and the seat ledger through the advice code. It reports:

- **Always:**
  - runs by status, mode and month, and the planned sizes;
  - the project's gates by runs and failures, with a build's before/after proofs and gate probes
    counted apart;
  - repair trails and failure categories;
  - claim verdict totals;
  - seat evidence;
  - missing or malformed data.
- **Only when 5 runs carry the data:**
  - the median cost, agents and tokens per worker;
  - actual cost over the plan's estimate;
  - the share of finished repair trails that resolved;
  - the verifier's share of caught claims (with a 90% range).

  Below that, the report says "too few (n of 5 needed)".

The design is in `docs/design/history-adr.md`.

## Why

The roadmap asked for historical analytics only once real data exists. This report is the
analytics layer with that condition built in: it will not show a trend it cannot support, and it
says how far the data is from the bar.

## Architecture and compatibility

- **Read-only, and built on existing files.** It reads run folders and `ledger.tsv`: no database, no
  server, no migration.
- **Old runs still count.** Legacy runs (no plan, no events) are counted and named.
- **Scope.** `history` takes no `--run`: it reads every run of this council home.

## Tests

`evals/run_history.py`: 14 checks on Windows, 15 where symlinks can be made. No model, about 3 s.
They check that:
- no runs is said plainly;
- four runs give counts and "too few (4 of 5 needed)", never a median;
- five runs give the right median cost (80k), agents (2), tokens per worker (60k) and estimate
  ratio (0.40×);
- the proofs and probes are kept apart from project gates;
- repairs (4 resolved, 2 stopped, with a range) and categories are right;
- claims: 5 caught out of 13 checked;
- status, mode and month counts are right;
- missing plans and events are named;
- malformed files, a folder that is not a run, and a bad events.tsv are survived and named;
- a symlinked run folder is not read;
- reading changes nothing;
- the helper handoff works, with three refusals each giving its own message.

## Evidence on real data

Read-only on the Chrollo Project home (2026-09-26), the report finds:
- 4 runs: 3 complete and 1 in progress; council-init 2, plan 1, implement 1;
- every rate "too few" — at most 2 completed runs with a cost, and no run with a filled plan;
- project gates such as tests (2 runs, 1 failed) and marks-corpus (2 runs, 1 failed);
- 12 before-checks, all failing as intended, 11 after-checks with none failed, and 15 probes, 2 of
  which failed;
- no repairs and no claims recorded;
- 11 seats, none weighed;
- all 4 runs predate the run plan and the event stream.

## Metrics / baseline comparison

None beyond the counts: no project has enough runs to show a rate.

## Known limitations

- The bar of five is a judgement.
- The report covers this clone's run folders only.
- Tokens per worker count any non-verifier seat as a worker.

## Deferred

- A dashboard.
- Cross-project history.
- Rates by time window.

## Not verified

- A project with enough runs to show a rate.
- macOS and Linux (CI runs the checks once pushed).
