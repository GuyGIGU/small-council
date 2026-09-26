# ADR: seat learning from the ledger

## Problem

A refresh proposes roster changes from `council ledger`, "with the numbers shown". The numbers are
raw counts. In one real project the ledger holds two runs: a council-init whose seats were never
judged (read as 0% shipped) and one plan run of eight items per seat. A roster change made from
that is made from noise. It either drops a lens that happened to have one weak run, or keeps a noisy one
because it happened to have one good run.

## Constraints

- Advisory only: the user decides every roster change; nothing edits a roster, a route or a run.
- No new state and no format change: `ledger.tsv` stays as it is, older ledgers read unchanged.
- Bash stays sufficient for the raw record; Python 3.8+ stays optional.
- The rule must be stated plainly enough for a Chair to repeat it to a non-programmer.

## Options

1. Keep raw numbers and add a doctrine rule ("ignore seats with fewer than N runs"). Cheap, but
   nothing enforces it, and a council-init row still reads as a failing seat.
2. Bayesian scores with priors per seat. Principled, but the priors would be invented, and scores
   invite ranking seats against each other on differences that are not there.
3. Count only runs that judged a seat's items, give a plausible range for its useful share, and
   advise from a small vocabulary only past an explicit bar.

## Decision

Option 3, as `council ledger advice [N] [--json]` (`scripts/ledger.py`):
- **Judged runs only.** A run counts toward usefulness when its synthesis credited some item, kept or
  cut. Other runs (council-init, builds) count toward tokens only.
- **Useful = kept and not refuted**, the ledger's own "shipped".
- **Ranges.** The range is a 90% Wilson interval that counts at most five items per run, because
  one run's items share a brief, a model and a day.
- **The bar.** A seat is weighed only after 3 judged runs and 15 items. Past it, the first rule
  that matches applies:
  - drop? — only after 8 judged runs, useful at most 15%, and phrased as a question for the user;
  - lower priority — useful at most 30%;
  - narrow or pair with a verifier — at least 30% of verified kept items refuted, with at least 10
    such items;
  - pair — fewer than 2 items a run;
  - retain — useful at least 50%;
  - otherwise unclear.
- **Cost.** A seat whose tokens per useful item exceed twice the median of the weighed seats is
  marked costly (with at least three seats to compare).

The plain `council ledger` table keeps its numbers. It shows `-` instead of `0%` for a seat that no
run judged, and points to the advice.

## Tradeoffs

- The thresholds are judgment calls, not fitted to outcomes — there are none to fit yet.
- The per-run cap is a heuristic for correlation within a run, not a model of it.
- "Useful" is a proxy: kept is the Chair's call and refuted only covers what a verifier checked, so
  a seat whose kept items were never verified looks better than it may be.
- A recast seat starts a new record under its new slug.
- Severity is not recorded, so one P1 counts the same as one nit.

## Alternatives rejected

- Automatic roster edits.
- Routing weights learned from the ledger.
- Seat scores shown to workers in briefs, which would bias the next run.
- A dashboard.

Each of these would act on numbers that cannot yet carry the weight.

## Revisit when

- A project reaches about twenty judged runs.
- The benchmark (Phase 10) shows whether an advised change improved outcomes.
- Severity or escaped defects are recorded per seat.
