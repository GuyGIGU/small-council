---
name: council-init
description: Tailor the Small Council to this project — detect the stack and surfaces, recast the expert roster, dry-run the real check commands, build the codebase map, and write .council/ (config, memory, map). Run once per repo, when the stack changes, or to refresh a stale config. Use when a council mode starts in a repo with no .council/council.config.md, or the user says "set up", "init", or "refresh" the council.
---

# Council Init — tailor the council to this project

One installed plugin, a bespoke council per repo: instead of hand-editing experts, point this at a repo
and it generates the fit. Use the context-core discipline — **map the repo, don't deep-read it.**
Read `${CLAUDE_PLUGIN_ROOT}/references/roster/expert-catalog.md` first: it holds the seats, their
"applies when" rules, and the recast rules.

Council home is the **main** checkout's `.council/` (see context-core, "Where things live").

## Phase A — Detect stack and surfaces (classify, don't review)

Glob/Grep for signals only; cap reads at config and skeleton files.
- **Language / build:** `package.json`, `tsconfig.json`, `pyproject.toml` / `requirements.txt`,
  `go.mod`, `Cargo.toml`, `pom.xml` / `build.gradle`, `*.csproj` / `*.sln`, `Gemfile`, `composer.json`,
  `mix.exs`, `pubspec.yaml`, `Package.swift`, `project.godot`, Unity `ProjectSettings/`, `*.uproject`,
  `Dockerfile` / `compose.yaml`, `*.tf`.
- **Surfaces:** UI components? a server or API? a relational DB or migrations? other persistent state
  (files, caches, save games)? an LLM or prompt pipeline? a numerical or simulation engine? a game loop?
  a mobile app? infrastructure as code? a CLI?
- **Commands:** `package.json` scripts, `pyproject`/`pytest.ini`, `Makefile`, CI workflows, `*.bat` /
  `*.ps1`, README "how to run tests".

## Phase B — Select and recast the roster

For each catalog seat decide **include / recast / drop** by its "applies when" rule.
- **Recast before you drop.** Most "no surface" seats have an analogous surface: any persistent store →
  data integrity; any computation-heavy engine → numerical correctness; any hot loop → performance.
  Seats dropped for "zero surface" have gone on to produce a quarter of a review's findings once
  recast. Drop only when there is truly nothing (no UI at all → no UI/UX/Frontend seats).
- Give every seat a lowercase **slug** (its seat-file name) and a named practitioner who fits the
  stack; keep the reference doc and record why it was recast.
- **John Carmack chairs** — always on, never a seat. **Fowler (structure) and Beck (tests) are never
  dropped.**
- A domain the catalog doesn't cover (e.g. a game engine's frame loop) → propose a project-local seat
  with its own reference doc under `.council/refs/`, drafted from the project's real constraints.

## Phase C — Detect and dry-run the gates

Record the project's **real** commands (never assume `tsc` / `vitest` / `cypress`): tests, lint,
build/compile, any e2e or regression harness. **Run each once** — the fast form (`--version`,
`--collect-only`, the quick suite) — judged by exit code, never through a pipe. Mark each ✓ runnable
or ✗ with the reason (a gate that can't run here is worse than no gate: it fakes a green). Mark which
are mandatory.

## Phase D — Build the map

Write `.council/map.md` from `${CLAUDE_PLUGIN_ROOT}/references/templates/map.md`, recording HEAD as
`map-commit`. Small repo → do it yourself within the map ceiling. Large repo (hundreds of source files
or several top-level systems) → propose a Squad of mapping workers (`small-council:council-worker`,
one per top-level area, each filling the template's sections for its area), then merge into one map
of at most ~250 lines. The map is the cheapest context the council will ever have: every later run,
and every ordinary session, orients from it instead of re-exploring.

## Phase E — Propose, then write

Present the roster (with recasts and drops and why), the gates (✓/✗), and a three-line map summary.
Adjust on request. On confirmation write:
- `.council/council.config.md` from `${CLAUDE_PLUGIN_ROOT}/references/templates/council.config.md`,
  with `last-verified: <date> @ <short sha>`.
- `.council/.gitignore` containing `runs/` and `active-run` — config, memory, map, plans, reviews,
  logs, and research stay tracked, so nobody hand-copies a review into an archive folder again.
- Memory: keep an existing `conventions.md` wherever it is (record its path in the config's Memory
  section); otherwise create `.council/conventions.md` from the template. Obvious accepted patterns
  seen during detection go under `## Proposed`, never straight into the confirmed sections.

## Phase F — Wire it up

1. **CLAUDE.md pointer** (or `AGENTS.md` if that's the repo's convention; create `CLAUDE.md` if
   neither exists). Idempotent: replace an existing marked block in place — including a legacy
   `<!-- ultra-council:begin -->` block — rather than appending a second one.
   ```
   <!-- small-council:begin -->
   ## Small Council
   This repo uses the Small Council (council home: `.council/`). Main session: read `.council/map.md`
   to orient; for substantial work, suggest a council mode and get a go-ahead before any multi-agent
   run; resume interrupted runs via `.council/active-run`. Subagents and council workers: ignore this
   section.
   <!-- small-council:end -->
   ```
2. **Offer a permission rule** so seat workers can write run files without prompting each time — only
   with a yes, in `.claude/settings.local.json`: `"permissions": { "allow": ["Edit(/.council/**)"] }`
   (Edit rules cover Write too).
3. Nothing else to install: the plugin's SessionStart hook already orients council-enabled sessions,
   flags unfinished runs, and re-establishes the method after a compaction.

## Refresh (re-runs)

Configs drift — docs get renamed, scenes get deleted, suite counts change. On a re-run or "refresh the
council":
- Re-check **every path and gate** in the config against the repo (dry-run the gates again); update
  `last-verified`.
- **Merge, don't overwrite:** show a diff; any section the user added or edited (hard rules, a pinned
  gate, a manual recast, Notes) is theirs — merge around it and surface conflicts for them to resolve.
- Older config layouts → offer to migrate to the current template, showing the diff.
- Legacy run folders (`.council/<mode>-output/`) stay where they are as history; new runs go to
  `runs/`. A stale `active-run` pointing into them → ask whether to close it.
- Refresh the map if it's far behind HEAD.

## Output

Tell the user, plainly: the roster (recasts and drops, and why), the gates (✓/✗), the files written,
and anything that needs their decision — numbered.
