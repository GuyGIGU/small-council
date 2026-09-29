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
  - exact recorded tokens grouped by the run plan's requested model (tokens are not money; inherited
    seats' actual model is unknown);
  - missing or malformed data.
- **Only when 5 runs carry the data:**
  - the median cost, agents and tokens per agent;
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

`evals/run_history.py` checks history, and `evals/run_model_routing.py` checks the model plan rules.
Both run without model calls or paid work.
They check that:
- no runs is said plainly;
- four runs give counts and "too few (4 of 5 needed)", never a median;
- five runs give the right median cost (80k), agents (2), tokens per agent (40k) and estimate ratio
  (0.44×, the Chair's 20k left out);
- one run with five repair trails and five checked claims shows no share ("too few runs, 1 of 5");
- failure categories come from failed attempts, never RESOLVED;
- deep JSON is survived;
- seat evidence reads the ledger's last 20 runs;
- the proofs and probes are kept apart from project gates;
- repairs (4 resolved, 2 stopped, with a range) and categories are right;
- claims: 5 caught out of 13 checked;
- status, mode and month counts are right;
- missing plans and events are named;
- malformed files, a folder that is not a run, and a bad events.tsv are survived and named;
- a symlinked run folder is not read;
- reading changes nothing;
- the helper handoff works, with three refusals each giving its own message.

## Independent review

The same review (of `1d6e02b`) found in history:

| Severity | Finding | Fix |
|---|---|---|
| medium | Shares were gated on items, not runs: one run with five claims showed "verifier caught 60%". | A share needs five runs that carry its data, and counts at most five items from any run. Lowering the bar to one run fails a check. |
| medium | "Failure categories" counted RESOLVED, from the closing row of a resolved trail. | The category comes from the trail's failed attempts. The test data now matches what the real repair producer writes. |
| low | Seat evidence used as many ledger runs as there were local run folders. | The same 20-run window as `council ledger advice`. |
| low | Deep JSON crashed the report; junctioned folders were read; conventions.md was re-read for every run (11 s on a large home). | Fixed in the cockpit's reading layer, which history uses; history no longer reads memory. |
| low | The estimate ratio compared agents' tokens (no Chair) with an estimate including the Chair's 20k. | The Chair's share is left out of the estimate. |

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

## Platform check update — 2026-09-28

Automatic macOS and Linux checks passed for the released code in CI runs
`36305577961` and `36319880515`; this is not validation by a person using those hosts.
