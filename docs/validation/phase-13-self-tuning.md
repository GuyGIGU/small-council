# Phase 13 — conservative, inspectable self-tuning

## What changed

- **`council tune [--json]`** (`scripts/tune.py`) proposes from the project's own record:
  - **budget:** the estimate per worker. It is proposed once five completed runs measure tokens
    per worker and the median is more than a quarter off.
  - **roster:** seats whose advice clears its bar. Listed only, for a council-init refresh.
  - **held:** context packs, run size and verification depth. Never proposed without a benchmark.
- **`council tune apply|revert budget --user-said "…"`** writes or undoes one line under
  `## Run preferences`. The user's words are redacted first. Each change is logged with its
  evidence as `T-<n>` in `.council/tuning.md`.
- **`council route recommend`** budgets with that line when it is set:
  - worker and verifier estimates;
  - the ceilings that shrink a run to fit a user's budget.

  Without the line its output is unchanged.
- **Doctrine and docs:**
  - Convene notes the configured estimate;
  - the council-init refresh puts tuning proposals to the user;
  - the config template explains the line;
  - the design is in `docs/design/self-tuning-adr.md`.

## Why

The roadmap's self-tuning phase is conditional: only once metrics are trustworthy, and
conservatively. The record supports exactly one calibration — a cost estimate — and no behaviour
change. This phase builds the tuning path, with its evidence bars, so each knob can move only
when its evidence exists, and only on the user's words.

## Architecture and compatibility

- **What it writes.** Only `council.config.md` (one line, only via `apply` or `revert`) and
  `.council/tuning.md`. It keeps the config's BOM and line endings, and writes both files
  atomically.
- **Existing projects.** Configs without the line behave exactly as before.
- **Where it runs.** `tune` takes no `--run`.

## Tests

`evals/run_tune.py`: 20 checks, about 47 s (it drives the helper), no model. They check:
- the budget waits on no record;
- no change is proposed within a quarter;
- a proposal appears, with its evidence and the command to apply it;
- the JSON output;
- seven refusals, each saying why and writing nothing;
- apply writes one line in the right place;
- the log records T-1 with evidence and words;
- a secret-looking string in the words is redacted;
- the route then budgets 150k;
- nothing else changes;
- after apply, nothing more is proposed;
- applying twice is refused;
- revert restores the config byte for byte, and the route returns to 80k;
- reverting twice is refused;
- a revert over a hand edit is refused, and the edit is kept;
- an existing hand-set value is replaced in place and restored on revert;
- a BOM and CRLF config keeps both;
- a config without `## Run preferences` is refused.

Deliberately breaking three safeguards fails the matching check each time:
- dropping the redaction;
- forcing LF endings;
- skipping the hand-edit guard.

Also run: structural 623/623, quick validation 0 warnings, phrases 74/74.

## Evidence on real data

No project has five completed runs with workers. On the Chrollo record `council history` gives
2 of 5, so `council tune` there would answer "waiting".

## Metrics / baseline comparison

None. Whether a calibrated estimate improves sizing decisions is unmeasured.

## Known limitations

- One knob.
- The thresholds (five runs, a quarter) are judgements.
- Tokens per worker counts any non-verifier seat as a worker.

## Deferred

Behaviour knobs (context packs, run size, verification depth). Each needs:
- benchmark evidence;
- a write path;
- its own ADR amendment.

## Not verified

- A real project reaching the budget bar.
- A Chair presenting a tuning proposal in a live refresh.
- macOS and Linux (CI once pushed).
