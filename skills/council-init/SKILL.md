---
name: council-init
description: Summon the Small Council for this project — detect the stack and surfaces, recruit and recast the expert roster with surface markers, dry-run the real check commands, build the codebase map, and write .council/ (config, memory, map). Run once per repo, when the stack changes, or to refresh a stale config. Use when a council plan, build or research starts in a repo with no .council/council.config.md or a quick one, when a review offers the full setup, or the user says "set up", "init", "summon", or "refresh" the council.
---

# Council Init — summon the council for this project (stage 0)

One installed plugin gives each repo a bespoke council, built to fit it.
- Follow the council's discipline: **map the repo, don't deep-read it.**
- First read `${CLAUDE_PLUGIN_ROOT}/references/roster/expert-catalog.md`: the seats, their "applies
  when" rules, and the recast rules.
- The council home is the main checkout's `.council/`; `council home` prints it. Call the helper as a
  plain `council <command>` — never through a shell variable or alias, or as `bash <path>/bin/council`
  while it is on PATH: permission rules match the command text. If `command -v council` fails, write
  `bash "${CLAUDE_PLUGIN_ROOT}/bin/council" <command>` in full. Have the user restart only when
  `council run open` refuses and says to.

## Phase A — Detect the stack and surfaces (classify, don't review)

- **Open the setup run first:** `council run open council-init`. It creates `.council/` and its
  `.gitignore`; the probes and the scaffold need it. Keep it open through Phase D.
- **`council init detect`** does the inventory and writes nothing: the `stack-fingerprint:` line,
  each check the manifests and scripts declare (with the `probe:` and `broken:` lines to run, its
  needs and side effects), and a `seat:` line per catalog seat with the surface the file list shows.
  It reads the root, `scripts/` and `tools/`.
- **Then read what it doesn't:** what CI runs, the README's "how to run tests", a second level of
  folders (`apps/*/package.json`), and the tracked files by extension
  (`git ls-files | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -20`), which catches the
  Xcode projects, notebooks, game engines and firmware a manifest list misses.
- **Surfaces are yours to judge** — which of these exist:
  - UI components; a server or API;
  - a relational DB or migrations; other persistent state (files, caches, save data);
  - an LLM or prompt pipeline; a numerical or simulation engine;
  - a game loop; a mobile app; infrastructure as code; a CLI.

  A `seat:` line whose rule "needs a look" is a question for Phase B, not a drop.

Cap your reads at config and skeleton files; the decision records are read in Phase D.

## Phase B — Recruit, recast, drop

For each catalog seat, decide **include / recast / drop** by its "applies when" rule.
- **Recast before you drop.** Most "no surface" seats have an analogous one:
  - any persistent store → data integrity;
  - any computation-heavy engine → numerical correctness;
  - any hot loop → performance.

  Seats dropped for "zero surface" have produced a quarter of a review's findings once
  recast. Drop only when there's truly nothing to look at (no UI at all → no UI, UX or Frontend seats).
- **Every seat gets:**
  - a lowercase **slug** — the name of its seat file;
  - a named practitioner who fits the stack;
  - its **Surface markers**: 2–6 globs or words in this repo's own idioms (`migrations/**`,
    `APIRouter`, `*.tscn`, `save_game`) that say where the seat's lens lives. They make assignment
    mechanical and every skip evidenced. No `|` inside a marker (the roster is a table): list
    alternatives separately.
  - For a recast seat: it keeps its reference doc, and you record why it was recast.

  No card yet: a seat's card is written the first run that selects it (doctrine Brief, Cards first).
- **One lens, several areas.** In a monorepo, or a repo with distinct parts (a web app and an admin,
  an app and its firmware), a lens may take several rows — one per area, each with its own slug
  (`dodds-web`, `dodds-admin`) and surface.
- **John Carmack chairs** — always on, never a seat. **Fowler (structure) and Beck (tests) are never
  dropped.**
- **A domain the catalog doesn't cover** (a game engine's frame loop, firmware, a DSL) → propose a
  project-local seat with its own reference doc under `.council/refs/`, drafted from
  `${CLAUDE_PLUGIN_ROOT}/references/templates/seat-doc.md` and the project's real constraints. Cite
  repo evidence for every principle, and leave it `status: draft` until the user accepts it.

## Phase C — Dry-run the gates

Keep the project's **real** commands — never assume `tsc` / `vitest` / `cypress`: tests, lint,
build/compile, and any e2e or regression harness.
- **Probe each check you keep, once, with detect's `probe:` line**
  (`council gate probe-<name> -- '<fast form>'`). A command detect didn't list (from CI or the
  README) takes the same form, with a fast form you choose (`--version`, `--collect-only`, the quick
  suite); the scaffold gives it no row, so you write that row in Phase E.
- **Gate commands run under bash** (Git Bash on Windows). Bash drops a `\` outside quotes: write
  paths with `/`, or quote them. Judge a gate by what `council gate` reports, never through a pipe or
  your own shell: a `cmd /c` run straight from a Bash tool exits 0 without running anything.
- **Judge each result.** `could not run` is a missing tool or a wrong command: fix it, or leave it
  ✗ with the reason — a gate that can't run here fakes a green, worse than none. A `FAIL` from a tool
  that ran (a linter that found problems, a failing test) is the code's, not the gate's: it is
  runnable. Run its `broken:` line too: when the twin could not run, the scaffold writes the row
  `✓ … runs, and fails today`, not mandatory. With no twin it writes ✗ (Phase E sets it right).
- **Its run plan opens ready for setup:** `run-plan.tsv` is solo, the Chair only, self-verified, each
  default saying so in its reason. Change a value only where this repo differs, with the reason,
  then `council run plan check`.
- **Never probe** a gate that deploys, spends money, flashes hardware or needs credentials: ask
  first. If it stays unprobed, the scaffold writes its Checked cell `✗ not probed: …`, and
  `council gate --all` skips it.
- **Mandatory gates, and a slow suite at verify:** reviews wait for grounding gates.
- **Prove each mandatory gate can fail.** One that only greps its tool's output, or ends in
  `|| true`, passes with the tool missing — green for ever. Run detect's `broken:` line (the command
  with its tool broken): `council gate probe-<name>-broken -- '<broken command>'` must fail. The
  scaffold makes a gate mandatory only when its probe passed and its twin failed, and writes both
  into its Probe cell; one that still passes is ✗ until fixed — for a runner kept in `$( )`, add
  `|| exit $?` right after it.
- **Needs and Side effects** come from detect: check them. `council gate --all` never runs one with
  cost, hardware, deploy or credential side effects; those run only by name, on the user's go.

### The checks this project is missing

After the dry-runs, compare what the project has against the five in
`${CLAUDE_PLUGIN_ROOT}/references/guardrails.md` — **formatter, linter, type check, test runner,
dependency audit**. Anything already there keeps the project's own command.

Then list what's missing, cheapest-first, **one plain line each: what it would catch, in the user's
words, not the tool's** — "a linter (ruff) — catches unused variables, dead code and obvious mistakes,
in about a second". Say what a project with none of them means: every council report on it says
NOTHING WAS CHECKED, because `council gate --all` has nothing to run. Then one question:

> Fit the ones you want? Nothing is installed until you say so.

On a yes, write `<home>/plans/guardrails.md` from the reference's template (its "Fitting them":
`## Task Sequence`, then `### <n>. <title>` and its rows, `Ref: references/guardrails.md`) — one
task per check, cheapest first — and offer council-implement. Each task's **Serves** quotes three or
more of the user's own words, as they said them; when their yes was a word or two ("Both"), quote
the question with it — "Fit the ones you want? — Both" — since the plan check refuses a shorter
quote. **council-init installs nothing itself**, so every install gets before-and-after evidence, a
blind verifier and a log row. Every task's Done-when is two-sided (it fails on a deliberate
violation and passes once it's removed), and a new lint, format or type gate is ratcheted
(`council changed`, `Mandatory: no`): the reference's "proved both ways" and "The ratchet". A task
names nothing under `.council/`: the Gates row is added after the build.

On a no, write `guardrails: declined <date>` into the config once the scaffold has written it. `council doctor` then reports
the project's missing checks as a warning rather than an error, so the decision sticks without being
asked again; delete that line to have them fitted.

## Phase D — Write the scaffold, then build the map

**`council init scaffold`** writes the mechanical files from the templates, each only where none
exists: the config (`last-verified: <date> @ <sha>`, the line `council fingerprint` prints, the
template's run preferences, the Fowler and Beck rows, a Gates row per check from this run's probes),
`conventions.md` when there is no memory file, and `map.md` stamped with `map-commit`. Its
`Left for the Chair:` lines name the rest.

Fill the map's prose:
- **Keep to what the code doesn't say by itself:**
  - where things live;
  - the flows that matter;
  - hot spots, from git history (`git log --since=12.months --name-only --format= | sort | uniq -c | sort -rn | head`);
  - the vocabulary;
  - the conventions new code must match.
- **Fill its `## One way per job` table, and find the project's recorded decisions:**
  `${CLAUDE_PLUGIN_ROOT}/references/roster/decision-records.md`.
- **A small repo** → do it yourself, then `council run close`.
- **A large repo** → a mapping squad of at most 4 workers, run like any council run:
  1. The setup run (Phase A). One run, not two.
  2. Make its plan a squad: `size` squad, and one mapping worker per area from the rows at the foot
     of `run-plan.tsv`, their estimate added to `estimated-tokens`; then `council run plan check`.
     The helper starts no worker the plan doesn't select.
  3. Write a brief whose `## Seats` has one block per top-level area: `ref: none`,
     `out: seats/<area>.md`, `cap: 8`, the area's paths as the slice. Format: "an `## Index` of at
     most 8 map rows, each `<n> · map · <section> · <path> · <one-line fact>`, then the map template's
     sections for your area, a path on every row".
  4. Dispatch them following stage 5, then run `council collect`.
  5. Merge the results into one map of at most ~250 lines, then `council run close`.

## Phase E — Propose, then write

The order, honestly: the scaffold wrote only facts nobody has to agree to (the probes' results, the
fingerprint, the template's defaults, the map from the code). What the user decides is proposed
first and written only on their yes. Present:
- the roster, with recasts, drops, the reasons, and each seat's surface markers;
- the gates (✓/✗) and their side effects;
- the run preferences, sharing included: team or just me (when to ask:
  `${CLAUDE_PLUGIN_ROOT}/references/run/sharing.md`);
- a model per role, proposed from yours: `${CLAUDE_PLUGIN_ROOT}/references/run/models.md`;
- a three-line summary of the map.

Adjust on request. On confirmation, write into `.council/council.config.md`:
- **the roster rows**, in place of the `<Seat>` row, each with its recast note;
- **`## Stack`**, in place of its placeholder;
- **`## Hard rules`**, which the scaffold writes empty: a `- ` line for each non-negotiable the
  user confirms (CLAUDE.md's and AGENTS.md's too); none, and it stays empty;
- **the run preferences** and models as answered (the defaults are the user's to change: approve
  without asking up to Squad, agent cap 10); sharing: Phase F;
- **the Gates rows the probes can't write:** a row for each command detect didn't list; `✓ <date>`
  for a `FAIL` from a tool that ran with no twin (Phase C); the count of problems of each check that
  fails today, in `## Notes`; any Run at or Mandatory cell this repo needs otherwise.

Then:
- **`asks/`** (the user's own words) stays out of git through `.council/.gitignore`. A user who
  wants the team to see them says so: write `!asks/` in place of that line; nothing adds it back.
- **Memory:** keep an existing `conventions.md` wherever it is, and record its path in the config's
  Memory section; the scaffold wrote `.council/conventions.md` only when there was none. Obvious
  accepted patterns seen during detection go under `## Proposed`, never straight into the confirmed
  sections; so does each decision Phase D found, citing its `file:line`.

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

   **Just me** (refreshes too): no note; run `council sharing just-me` and relay what it says is left.
2. **Offer permission rules** — written only on a yes — in `.claude/settings.local.json`, so the
   bookkeeping doesn't prompt at every step. `council doctor permissions` prints the block to paste:
   `Edit(.council/**)` and one rule for each bookkeeping command (`Bash(council run:*)` and so on).

   Edit rules cover Write too. Add the council home's real path as well, exactly as `council home
   rule` prints it — the home belongs to the **main** checkout, so the relative rule misses it from a
   linked worktree or a subdirectory. On Windows that is `Edit(//c/Users/…/.council/**)`: Claude
   Code matches the drive lower-case with no colon, so `//C:/Users/…` never matches.

   **These rules match the command text.** They cover `council run status` typed plainly and nothing
   else: a call through a shell variable, an alias or `bash <path>/bin/council` matches none of them
   and asks every time. So every council call is a plain `council <command>` (context-core, "The
   helper"). Only if `command -v council` fails here, add the fallback form the same way —
   `Bash(bash *bin/council run:*)` and so on — or the list does nothing.

   **`council gate` and `council changed` are deliberately not on the list**: both run whatever
   command they are given, so a blanket `Bash(council *)` would allow every command on the machine.
   Say this to the user in one line: *"the checks will ask you each time — that's on purpose, because
   a gate runs whatever command it names. Don't pick 'don't ask again' for `council gate` or
   `council changed`."* Never widen this list to `council *`.

   **`council cap` stays off too**: `council cap allow` records the user's go past the agent stop,
   so it must ask every time. So does `council correct`.

   At a **refresh**, read `.claude/settings.local.json` first: if it holds `Bash(council *)` or a
   `council gate` rule from an earlier version, offer to replace it with this list, and say why; an
   `Edit(//C:/…)` rule never matched, so offer the one `council home rule` prints in its place. If
   it holds an earlier, shorter version of this list, offer to add the rules it lacks: name them, use
   the form the file already uses, leave every other rule in the file as it is, and write only on a
   yes. After a plugin update, `council doctor` names the rules a project's list lacks.
3. **Nothing else to install.** The plugin's hooks orient council sessions, flag open runs, restore
   the method after a compaction and check every seat file before a worker finishes.

## Refresh (re-runs)

Configs drift. On a re-run, or "refresh the council":
- Run `council doctor` and fix what it reports. `council fingerprint check` says whether the stack
  moved; `council memory check` lists memory entries whose anchored file, line or symbol is gone.
- **Memory:** offer to add Scope and Anchor to entries that lack them — one proposal per entry, as
  numbered operations, applied on the user's yes.
- **A `setup: quick` line** (the quick setup a first review made) means the full setup is still to
  do: in the setup run, probe the checks `council init detect` lists; `council init scaffold` then
  fills the Gates rows that still read `✗ not probed` and writes the map's skeleton. Tailor the
  roster (Phase B), build the map (Phase D), write `## Stack`. It chose just me: ask about sharing.
  Take the `setup: quick` line out last, after the user's yes.
- **Cards:** rewrite only a card that exists and whose doc, surface or stack changed (a recast too),
  from `${CLAUDE_PLUGIN_ROOT}/references/templates/seat-card.md`. A seat without one gets it the
  first run that selects it.
- **Roster changes from the record.** `council ledger advice 20` weighs each seat only on runs that
  judged its items and advises only past its bar (3 judged runs, 15 items, at most 5 from any run).
  Propose a change only where it advises one, with the numbers shown — "UX (Friedman): 6 judged
  runs, 8 of 30 items useful (plausible 16–41%) — narrow its surface to `src/ui/**`?"
  Below the bar, say the record is too thin and change nothing. A lens the runs keep flagging outside their lanes is a
  separate proposal: name the runs. The user decides; nothing changes without a yes.
- Re-check **every path and gate** in the config against the repo, dry-running the gates again
  (`council run open council-init` first — `council gate probe-<name> -- '…'` needs an open run;
  close it when you are done), and update `last-verified`.
- **A Gates section still written as a list** (backticked commands under `## Gates`, no table): move
  every command into the Gates table, one row each, dry-run them as in Phase C, and fill every cell.
  Until then the helper reads no gate and every report says NOTHING WAS CHECKED: show the diff and
  say what each row came from.
- **Merge, don't overwrite.** Show a diff. Any section the user added or edited — hard rules, a
  pinned gate, a manual recast, Notes — is theirs: merge around it and surface conflicts for them to
  resolve.
- **Older layouts** → offer to migrate to the current template, which adds Surface and Run
  preferences, and show the diff.
- **Legacy run folders** (`.council/<mode>-output/`) stay where they are as history. An old run still
  marked open → close it on the user's say-so: `council run close --run <dir> --status abandoned`.
- **Permission rules:** bring the council rules in `.claude/settings.local.json` up to Phase F's
  list, as Phase F step 2 says — on a yes.
- **Refresh the map** if `council map status` shows it far behind.

## Output

Tell the user, plainly and numbered:
- the roster: recasts, drops and why;
- the gates (✓/✗);
- the files written;
- anything that needs their decision.
