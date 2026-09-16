---
name: council-init
description: Summon the Small Council for this project — detect the stack and surfaces, recruit and recast the expert roster with surface markers, dry-run the real check commands, build the codebase map, and write .council/ (config, memory, map). Run once per repo, when the stack changes, or to refresh a stale config. Use when a council mode starts in a repo with no .council/council.config.md, or the user says "set up", "init", "summon", or "refresh" the council.
---

# Council Init — summon the council for this project (stage 0)

One installed plugin gives each repo a bespoke council. Instead of hand-editing experts, point this at
a repo and it builds the fit.
- Follow the council's discipline: **map the repo, don't deep-read it.**
- First read `${CLAUDE_PLUGIN_ROOT}/references/roster/expert-catalog.md`: the seats, their "applies
  when" rules, and the recast rules.
- The council home is the main checkout's `.council/`; `council home` prints it. If the helper isn't
  on PATH, run it as `bash "${CLAUDE_PLUGIN_ROOT}/bin/council"`.

## Phase A — Detect the stack and surfaces (classify, don't review)

- **Start with an inventory** — it works for any stack:
  - count tracked files by extension (`git ls-files | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -20`);
  - list config-like files up to two levels deep;
  - read what CI runs.

  This catches firmware, Xcode projects, notebooks and game engines that a list of manifest files
  would miss.
- **Then confirm with manifests:** `package.json`, `tsconfig.json`, `pyproject.toml` /
  `requirements.txt`, `go.mod`, `Cargo.toml`, `pom.xml` / `build.gradle`, `*.csproj` / `*.sln`,
  `Gemfile`, `composer.json`, `mix.exs`, `pubspec.yaml`, `Package.swift` / `*.xcodeproj`,
  `project.godot`, Unity `ProjectSettings/`, `*.uproject`, `CMakeLists.txt` / `west.yml`,
  `Dockerfile` / `compose.yaml`, `*.tf`, `*.ipynb`.
- **Surfaces** — which of these exist:
  - UI components; a server or API;
  - a relational DB or migrations; other persistent state (files, caches, save data);
  - an LLM or prompt pipeline; a numerical or simulation engine;
  - a game loop; a mobile app; infrastructure as code; a CLI.
- **Commands:** from `package.json` scripts, `pyproject`/`pytest.ini`, `Makefile`, CI workflows,
  `*.bat` / `*.ps1`, and the README's "how to run tests".
- **Fingerprint:** `council fingerprint` prints the stack's line (its manifests and code languages).
  It goes in the config, so Prepare can tell when the stack moves.

Cap your reads at config and skeleton files.

## Phase B — Recruit, recast, drop

For each catalog seat, decide **include / recast / drop** by its "applies when" rule.
- **Recast before you drop.** Most "no surface" seats have an analogous one:
  - any persistent store → data integrity;
  - any computation-heavy engine → numerical correctness;
  - any hot loop → performance.

  Seats dropped for "zero surface" have gone on to produce a quarter of a review's findings once
  recast. Drop only when there's truly nothing to look at (no UI at all → no UI, UX or Frontend seats).
- **Every seat gets:**
  - a lowercase **slug** — the name of its seat file;
  - a named practitioner who fits the stack;
  - its **Surface markers**: 2–6 globs or words in this repo's own idioms (`migrations/**`,
    `APIRouter`, `*.tscn`, `save_game`) that say where the seat's lens lives. They make assignment
    mechanical and every skip evidenced. No `|` inside a marker, because the roster is a table — list
    alternatives separately.
  - For a recast seat: it keeps its reference doc, and you record why it was recast.
  - A **card** (Phase E) that translates its doc to this project.
- **One lens, several areas.** In a monorepo, or a repo with distinct parts (a web app and an admin,
  an app and its firmware), a lens may take several rows — one per area, each with its own slug
  (`dodds-web`, `dodds-admin`) and surface.
- **John Carmack chairs** — always on, never a seat. **Fowler (structure) and Beck (tests) are never
  dropped.**
- **A domain the catalog doesn't cover** (a game engine's frame loop, firmware, a DSL) → propose a
  project-local seat with its own reference doc under `.council/refs/`, drafted from
  `${CLAUDE_PLUGIN_ROOT}/references/templates/seat-doc.md` and the project's real constraints. Cite
  repo evidence for every principle, and leave it `status: draft` until the user accepts it.

## Phase C — Detect and dry-run the gates

Record the project's **real** commands — never assume `tsc` / `vitest` / `cypress`: tests, lint,
build/compile, and any e2e or regression harness.
- **Run each once, in its fast form** (`--version`, `--collect-only`, the quick suite). Judge it by
  exit code, never through a pipe.
- **Mark each one** ✓ runnable, or ✗ with the reason. A gate that can't run here is worse than no
  gate, because it fakes a green.
- **Never probe** a gate that deploys, spends money, flashes hardware or needs credentials: ask
  first. If it stays unprobed, its Checked cell reads `✗ not probed: <why>`, and `council gate --all`
  skips it.
- **Mark which gates are mandatory.**
- **Record more than the command** — the config's Gates columns: the **Probe** (the exact dry-run
  you ran), what it **Needs** (tools, env vars, credentials, hardware) and its **Side effects**
  (none, writes the tree, network, cost, hardware, deploy, credentials). `council gate --all` never runs a gate
  whose side effects involve cost, hardware, deploys or credentials; those run only by name, with
  the user's go-ahead.

## Phase D — Build the map

Build `.council/map.md` from `${CLAUDE_PLUGIN_ROOT}/references/templates/map.md`, and stamp HEAD as
`map-commit`.
- **Keep to what the code doesn't say by itself:**
  - where things live;
  - the flows that matter;
  - hot spots, from git history (`git log --since=12.months --name-only --format= | sort | uniq -c | sort -rn | head`);
  - the vocabulary;
  - the conventions new code must match.
- **A small repo** → do it yourself.
- **A large repo** → a mapping squad of at most 4 workers, run like any council run:
  1. `council run open council-init` — it creates `.council/` and its `.gitignore` if they don't
     exist yet.
  2. Write a brief whose `## Seats` has one block per top-level area: `ref: none`,
     `out: seats/<area>.md`, the area's paths as the slice. Format: "the map template's sections for
     your area, a path on every row".
  3. Dispatch them following stage 5, then run `council collect`.
  4. Merge the results into one map of at most ~250 lines, then `council run close`.

## Phase E — Propose, then write

Present:
- the roster, with recasts, drops, the reasons, and each seat's surface markers;
- for each seat, two lines on what its card will say is P1 here and where it will look;
- the gates (✓/✗) and their side effects;
- the run preferences;
- a three-line summary of the map.

Adjust on request. On confirmation, write:
- **`.council/council.config.md`** from `${CLAUDE_PLUGIN_ROOT}/references/templates/council.config.md`,
  stamped `last-verified: <date> @ <short sha>`, with the `stack-fingerprint:` line `council
  fingerprint` printed. Run preferences start at the defaults, which are the user's to change:
  approve without asking up to Squad, agent cap 10.
- **`.council/cards/<slug>.md`**, one per seat, from `${CLAUDE_PLUGIN_ROOT}/references/templates/seat-card.md`.
  A card translates the seat's doc to this project, in at most ~6 KB:
  - every principle of the doc, numbered as in the doc, one line each on what it means here — the
    construct, a path or an idiom — or "not applicable here" with the reason;
  - the severity rubric in this repo's terms;
  - where to look, from the map's hot spots and the surface markers;
  - what is not a finding here.

  Its first line is what workers copy onto their `ref:` line, and its `source:` line names the doc.
  Write them yourself after the map, one seat at a time: list the doc's principles
  (`grep -n '^## Principle' <doc>`), read each principle's section only as you write its line, and
  save the card before starting the next. After a compaction, carry on from the first seat without
  a card.
- **`.council/.gitignore`** containing `runs/`, `asks/` (the user's own words stay on their own
  machine) and `active-run`, for older runs. Config, memory, map, plans, reviews, logs and research
  stay tracked. A refresh adds the `asks/` line unless the user has chosen to share their requests.
- **Memory:** keep an existing `conventions.md` wherever it is, and record its path in the config's
  Memory section. Otherwise create `.council/conventions.md` from the template. Obvious accepted
  patterns seen during detection go under `## Proposed`, never straight into the confirmed sections.

## Phase F — Wire it up

1. **The CLAUDE.md pointer** — in `AGENTS.md` instead if that's the repo's convention; create
   `CLAUDE.md` if neither exists. Idempotent: replace an existing marked block in place, including a
   legacy `<!-- ultra-council:begin -->` block, rather than appending a second one.
   ```
   <!-- small-council:begin -->
   ## Small Council
   This repo uses the Small Council (council home: `.council/`). Main session: check `.council/map.md`
   when orienting in unfamiliar code; for substantial work, suggest a council mode and get a go-ahead
   before any multi-agent run; `council run status` shows open runs. Subagents and council workers:
   ignore this section.
   <!-- small-council:end -->
   ```
2. **Offer permission rules** — written only on a yes — in `.claude/settings.local.json`, so council
   runs don't prompt at every step: `"permissions": { "allow": ["Edit(/.council/**)", "Bash(council *)"] }`.
   Edit rules cover Write too; the second rule lets the helper run without asking.
3. **Nothing else to install.** The plugin's hooks already orient council-enabled sessions, flag open
   runs, restore the method after a compaction, and check every seat file before a worker can finish.

## Refresh (re-runs)

Configs drift: docs get renamed, files get deleted, suite counts change. On a re-run, or "refresh the
council":
- Run `council doctor` and fix what it reports. `council fingerprint check` says whether the stack
  moved; `council memory check` lists memory entries whose anchored file, line or symbol is gone.
- **Memory:** offer to add Scope and Anchor to entries that lack them — one proposal per entry, as
  numbered operations, applied on the user's yes.
- **Cards:** rewrite the card of any seat whose doc, surface or stack changed, and write the missing
  ones.
- **Roster changes from the record.** `council ledger 20` shows each seat's runs, items raised,
  kept and refuted, and tokens. Propose changes with the numbers shown — "UX (Friedman): 6 runs, 2
  of 14 items shipped, 5 refuted — narrow its surface to `src/ui/**`?" — and likewise pairing seats
  that are always thin, or adding a lens the runs keep flagging outside their lanes. The user
  decides; nothing changes without a yes.
- Re-check **every path and gate** in the config against the repo, dry-running the gates again, and
  update `last-verified`.
- **Merge, don't overwrite.** Show a diff. Any section the user added or edited — hard rules, a
  pinned gate, a manual recast, Notes — is theirs: merge around it and surface conflicts for them to
  resolve.
- **Older layouts** → offer to migrate to the current template, which adds Surface and Run
  preferences, and show the diff.
- **Legacy run folders** (`.council/<mode>-output/`) stay where they are as history. An old run still
  marked open → close it on the user's say-so: `council run close --run <dir> --status abandoned`.
- **Refresh the map** if `council map status` shows it far behind.

## Output

Tell the user, plainly and numbered:
- the roster: recasts, drops and why;
- the gates (✓/✗);
- the files written;
- anything that needs their decision.
