# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-07-08

First public release. Ultra Council is a derivative work of
[Carmack-Council](https://github.com/SamJHudson01/Carmack-Council) by Sam Hudson (MIT). See
[`NOTICE`](NOTICE) for the full attribution.

### Added

- **`context-core` pipeline** — a reusable 10-phase context-engineering pipeline (map → brief →
  partition → isolate → aggregate → verify → remember → compact) that every mode runs on. The
  original had no shared pipeline; this is the layer that makes the modes composable and resistant to
  context rot.
- **`council-init` auto-tailoring** — detects a project's stack and real check commands, selects and
  recasts the expert roster from `references/roster/expert-catalog.md`, and writes
  `.council/council.config.md`. One install now behaves like a bespoke council per project instead of
  a set of skills you copy and hand-edit.
- **`using-council` bootstrap** — loads at session start and re-establishes the method after a
  context compaction, so the pipeline never silently drops mid-run.
- **Evals harness** — `evals/run_structural.py` (framework invariants, no LLM), `evals/run_package.py`
  (every skill packages into a valid, CRLF-free, path-safe `.skill`), and `evals/behavioral-drills.md`
  (live-agent drills). CI runs the structural + package evals on Ubuntu and Windows.
- **Generic, stack-agnostic reference set** — the domain reference docs and every shipped skill body
  are neutral (no specific project's stack, seats, or gate commands hard-coded). A worked, illustrative
  configuration lives under `examples/`.

### Carried forward from Carmack-Council

- The named-expert council idea and the domain reference documents (`security.md`, `refactoring.md`,
  and the `quality-*.md` set), which remain under the original MIT license.
- The council modes `council-review`, `council-plan`, `council-implement`, `spec-writer`, and
  `test-architect`, now rewired to the `context-core` two-layer contract (a mode stays thin; the core
  owns the pipeline) and driven by the per-project config.

### Packaging

- `scripts/build.sh` + `scripts/package_skill.py` build each skill into a self-contained `.skill`
  zip, normalising line endings to LF so packages are byte-identical across platforms (a past bug
  dropped references on Windows when a shell copy loop hit CRLF).
- `scripts/quick_validate.py` hard-fails a build on a broken skill, malformed manifest, or a declared
  reference missing on disk — a packaged skill can never ship a blind review lane.

<!-- Add compare/release links here once this repo has a public home and tags, e.g.
[Unreleased]: https://github.com/<owner>/<repo>/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/<owner>/<repo>/releases/tag/v0.1.0
-->

