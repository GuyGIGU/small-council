# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] — 2026-09-15

Renamed **Ultra Council → Small Council** and rebuilt around what ~50 real council runs across three
projects showed: runs left open, proposals lost, artifacts scattered, a gate that lied, and fan-outs
bigger than the job.

### Changed

- **Ships as a Claude Code plugin** — this repo is its own marketplace. One install; one shared
  `references/` read through `${CLAUDE_PLUGIN_ROOT}` instead of a copy inside every skill; absolute
  reference paths for workers by construction.
- **context-core rebuilt as nine named phases** — scope & size, map, brief, partition, dispatch,
  collect, synthesize, verify, deliver/remember/close. Verification now comes *before* delivery and
  memory (it used to follow them); resume is a rule for every phase rather than a phase of its own; the
  doctrine is folded into the skill, so compaction re-attaches it whole.
- **One council home:** the main checkout's `.council/`, even from a git worktree. Deliverables go to
  tracked folders (`plans/`, `reviews/`, `logs/`, `research/`); run scratch goes to ignored
  `runs/<date>-<mode>/`. Each mode used to pick its own path, and artifacts scattered across worktrees.
- **Right-sized runs:** the Chair recommends Solo, Squad, or Full with an estimated cost, and skips a
  seat with nothing in scope — recording why — instead of dispatching every seat every time.
- **council-init** dry-runs every gate, recasts before it drops, stamps `last-verified`, writes
  `.council/.gitignore`, builds the codebase map, migrates the legacy `CLAUDE.md` block, and refreshes
  stale configs.
- **council-implement** also takes a review (fix mode), verifies each task adversarially, and appends to
  its log after every task, at a fixed path.
- **council-plan** reads an existing spec first and gives every task a "Done when".
- **council-review** resolves its target from the merge-base, has seats check blast radius, and ends
  with a fix hand-off.
- **test-architect**'s output formats moved to `references/test-architect-formats.md`, loaded when
  needed; **spec-writer** orients from the map first.

### Added

- **council-research** — evidence-graded investigation that saves its answer to `.council/research/`
  and keeps the map true.
- **The codebase map** (`.council/map.md`), stamped with a commit and refreshed incrementally — the
  cheapest context the council has, read by every run and every council-enabled session.
- **`council-worker` and `council-verifier` agents** — the worker contract lives in one place; the
  verifier returns CONFIRMED / REFUTED / UNCERTAIN for claims and OK / INCOMPLETE / REGRESSION /
  SCOPE-CREEP for changes.
- **SessionStart hook** — orients council-enabled sessions, flags unfinished runs, and says "resume,
  don't restart" after a compaction. Silent in other projects.
- **Proof of reading:** line 2 of each seat file echoes its reference doc's title; the completeness gate
  checks it.
- **Templates** for the config (a fixed schema: roster with slugs, gates with a Checked column, hard
  rules), memory (Accepted Patterns / Enforced Conventions / Decisions / Proposed), and the map.
- **Evals:** `evals/run_hook.py`; structural checks for the new invariants, size budgets, and version
  consistency; a rewritten validator for the plugin layout; drills D5–D11.

### Fixed — from the field

- **Runs were never closed**, so `active-run` went stale and old runs looked in flight. Runs now end
  `status: complete` and empty the pointer; the hook flags anything left open.
- **Memory proposals were lost** when a session ended before the user answered. They're written to
  `## Proposed` the moment they're made.
- **`session-state.md` grew into 350-line ledgers.** It's now a status board of at most ~40 lines;
  history goes to `log.md`.
- **A gate piped through `tail` reported green** while the test runner was missing. Gates are judged by
  exit code and never piped.
- **Configs pointed at renamed docs and deleted files.** Init dry-runs gates; refresh re-verifies every
  path.
- **The performance seat pointed at an unshipped "external" doc** in the catalog.
- **The drill fixture labelled its own seeded bug** in a code comment.

### Removed

- `using-council` (replaced by the hook), per-skill `manifest.json` files (Claude Code doesn't read
  them), the `.skill` zip packaging (`build.sh`, `package_skill.py`, `run_package.py`), and
  `fetch-references.sh` (it would overwrite the tuned reference docs with upstream copies).

## [0.1.0] — 2026-07-08

First public release, as **Ultra Council** — a derivative work of
[Carmack-Council](https://github.com/SamJHudson01/Carmack-Council) by Sam Hudson (MIT). See
[`NOTICE`](NOTICE) for the full attribution.

### Added

- **`context-core` pipeline** — a reusable 10-phase context-engineering pipeline (map → brief →
  partition → isolate → aggregate → verify → remember → compact) that every mode runs on.
- **`council-init` auto-tailoring** — detects a project's stack and real check commands, selects and
  recasts the expert roster from `references/roster/expert-catalog.md`, and writes
  `.council/council.config.md`.
- **`using-council` bootstrap** — loads at session start and re-establishes the method after a context
  compaction.
- **Evals harness** — structural evals, package evals, and live-agent behavioral drills, run in CI on
  Ubuntu and Windows.
- **Generic, stack-agnostic skill bodies**, with a worked, illustrative configuration under `examples/`.

### Carried forward from Carmack-Council

- The named-expert council idea and the domain reference documents (`security.md`, `refactoring.md`,
  and the `quality-*.md` set), which remain under the original MIT license.
- The council modes `council-review`, `council-plan`, `council-implement`, `spec-writer`, and
  `test-architect`, rewired to the `context-core` two-layer contract and driven by the per-project config.

### Packaging

- `.skill` zip packages built by `scripts/build.sh` + `scripts/package_skill.py`, with LF-normalised
  line endings and a validator that hard-failed on a missing reference.

<!-- Add compare/release links once this repo has tags, e.g.
[Unreleased]: https://github.com/<owner>/<repo>/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/<owner>/<repo>/releases/tag/v0.2.0
-->
