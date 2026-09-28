# Phase 13 — conservative, inspectable self-tuning

## What changed

- **`council tune [--json]`** (`scripts/tune.py`) proposes from the project's own record:
  - **budget:** the estimate per worker. It is proposed once five completed runs measure tokens
    per worker and the median is more than a quarter off.
  - **roster:** seats whose advice clears its bar. Listed only, for a council-init refresh.
  - **held:** context packs, run size and verification depth. Never proposed without a benchmark.
- **`council tune apply budget <value> --user-said "…"` and `revert budget`** write or undo one line under
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
  `.council/tuning.md`. It keeps the config's BOM, line endings and permissions, and writes the two
  files as a pair: if the config cannot be written, the log is put back.
- **Existing projects.** Configs without the line behave exactly as before.
- **Where it runs.** `tune` takes no `--run`.

## Tests

`evals/run_tune.py`: 25 checks after the review below (20 before), about 75 s (it drives the
helper), no model. The first version's checks were:
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

## Independent review

A reviewer checked `98e9250` (and `1d6e02b`) without access to my reasoning. The tuning findings:

| Severity | Finding | Fix |
|---|---|---|
| medium | An estimate of about 2.5M per worker or more shrank a run although the user set no budget: the route's "no ceiling" stand-in became reachable. | Only a ceiling the user gave (`--budget-tokens`) can shrink a run, and both readers accept 1k–1M only. |
| medium | A secret the user's words split across lines passed the line-by-line redactor, and Python then joined the lines into the tracked log. `memory accept\|reject` (Phase 8) had the same gap. | The helper flattens the words to one line before redacting, in both places. Both are tested, and each test fails against the previous helper. |
| medium | `apply` recomputed the proposal, so the log could pair "yes, use 150k" with 175k. | `apply budget <value>` must name the value shown; a different proposal is refused. |
| low | Revert was not byte-for-byte: 92500 came back as 92k, 1.5M as 1500k, an unreadable value was deleted, a missing final newline gained one, and a second line could be added beside an unreadable one. | The exact line replaced or inserted is logged, and revert puts back exactly that. An unreadable line is replaced, never duplicated. |
| low | A config that could not be written still left "applied" in the log. | Log and config are written as a pair, with the log put back on failure. |
| low | CRLF logs became LF, a BOM hid a first-line section, a line could land inside an HTML comment, and a new file took mkstemp's 0600 mode. | Line endings, the BOM, comments and file modes are all respected. |
| low | Tuning measured tokens per worker, while the route budgets per agent (the verifier included). | It measures and proposes tokens per agent. |

The review also found tests that could not fail:
- a route test checked only the verifier's estimate, so fixed ceilings passed;
- a hand-set 90k survived rounding.

There are now checks for:
- the 620k ceiling;
- no ceiling;
- an implausible estimate;
- exact undo of six awkward file shapes;
- value confirmation;
- CRLF logs;
- BOM sections;
- comments;
- file modes (POSIX);
- a failed config write.

## Evidence on real data

No project has five completed runs with workers. On the Chrollo record `council history` gives
0 of 5 under the 0.14 exact-accounting rules, so `council tune` there would answer "waiting".

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

## Platform check update — 2026-09-28

Automatic macOS and Linux checks passed for the released code in CI runs
`36305577961` and `36319880515`; this is not validation by a person using those hosts.
