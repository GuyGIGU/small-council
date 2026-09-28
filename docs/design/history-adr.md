# ADR: history across runs, without a database or a dashboard

## Problem

Each run records its plan, seats, gates, repairs and claims, but nothing reads them together. The
roadmap asks for historical analytics "only when enough real run data exists". The owner's
projects hold four runs between them; a dashboard of rates over four runs would present noise as
trends.

## Constraints

- **Filesystem state only.** Reuse what exists: run folders and `ledger.tsv`. No migration.
- **Never mistake a count for a rate.** Every rate must say how many runs support it.
- **Stay small.** No server, no mandatory service, no new dependency. Python stays optional.
- **Read-only.**

## Options

1. **SQLite.** Import every run into a database and query it. This gives fast queries, but it is a
   second copy of the state that can drift, and a schema to migrate — for four runs.
2. **A web dashboard** over the run folders. The roadmap defers it, and it would show vanity
   numbers today.
3. **A CLI report** that reads the run folders through the cockpit's snapshot. It always shows
   counts, and shows a rate only past a stated bar.

## Decision

Option 3, as `council history [--json]` (`scripts/history.py`, schema `council.history/2`).

This schema is superseded in 0.14 by `council.history/3`; the original decision below is retained.

- **Always shown.** Counts are always reported: runs by status, mode and month.
- **Shown only past the bar.** A median, a share or a ratio needs **5 runs that carry its data** —
  five runs, not five items: five claims in one run are still one run. A share's range counts at
  most five items from any run, as the seat advice does.
  Below that, the report gives the count and says "too few". The measures behind this bar are:
  - cost and agents per completed run;
  - tokens per agent (workers and verifiers);
  - how far actual cost was from the plan's estimate;
  - how often a finished repair trail was resolved;
  - how often the verifier caught a checked claim.
- **Build proofs kept apart.** A build's before/after proofs and gate probes are counted apart from
  the project's gates, because a before-check is meant to fail.
- **Missing data is named.** The report lists runs with no plan, no events or malformed events, and
  runs still open.
- **Seat evidence** comes from the same code as `council ledger advice`, over the same window of the
  ledger's last 20 runs (the ledger is tracked; run folders are not).
- **Estimate accuracy** compares the agents' tokens with the plan's estimate less the Chair's 20k,
  because seats.tsv never records the Chair.

## Tradeoffs

- The bar of five is a judgement, lower than the seat advice's, because these facts are per run,
  not per item.
- Every run folder is read on each call. That is fine for hundreds of runs, and a reason to revisit
  at thousands.
- Run folders are local and ignored by git, so history covers this clone only.

## Alternatives rejected

- A database.
- Charts.
- Cross-project aggregation.
- Any automatic action taken on the numbers: `council tune` proposes, and the user decides.

## Revisit when

- A project passes a few hundred runs, or a query is needed that files cannot answer quickly.
- Owners want history shared across clones.
- The benchmark and history together justify a dashboard view that answers a question the CLI
  cannot.
