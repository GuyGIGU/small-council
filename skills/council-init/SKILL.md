---
name: council-init
description: Summon the Small Council for this project — detect the stack and surfaces, ask why each part was chosen and propose its watch lists, dry-run the real check commands, build the codebase map, and write .council/ (config, memory, map, the book). Run once per repo, when the stack changes, or to refresh a stale config. Use when a council plan, build or research starts in a repo with no .council/council.config.md or a quick one, when a review offers the full setup, or the user says "set up", "init", "summon", or "refresh" the council.
---

# Council Init — summon the council for this project (stage 0)

- Follow the council's discipline: **map the repo, don't deep-read it.**
- First read `${CLAUDE_PLUGIN_ROOT}/references/watch-lists.md`: the checklist pages, what each
  covers and when it applies. There is no roster of expert seats (D72).
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
  needs and side effects), and a `watch list:` line per checklist page with what the file list shows
  for it.
  It reads the root, `scripts/` and `tools/`.
- **Then read what it doesn't:** what CI runs, the README's "how to run tests", a second level of
  folders (`apps/*/package.json`), and the tracked files by extension
  (`git ls-files | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -20`), which catches what a
  manifest list misses (Xcode projects, notebooks, firmware).
- **No code yet** (no manifest, only documents tracked): the stack comes first, before Phase B
  (`${CLAUDE_PLUGIN_ROOT}/references/run/book.md`, A new project's stack).
- **Surfaces are yours to judge** — which of these exist:
  - UI components; a server or API;
  - a relational DB or migrations; other persistent state (files, caches, save data);
  - an LLM or prompt pipeline; a numerical or simulation engine;
  - a game loop; a mobile app; infrastructure as code; a CLI.

  A `watch list:` line with nothing seen is a question for Phase B, not a drop.

Cap your reads at config and skeleton files; the decision records are read in Phase D.

## Phase B — Each part's reason and watch lists

The stack page (`${CLAUDE_PLUGIN_ROOT}/references/run/book.md`) has a row per language, framework,
library, tool and service, with why it was chosen and its watch lists (D73).
- **The reason** comes from a record (cite its `file:line`) or the owner: ask once at Phase E for
  every row with none. One not given is `not recorded`, never invented.
- **Watch lists** are reference pages, never seats: for each part, the pages of
  `watch-lists.md` whose "applies when" fits it, or `—`. Look for the analogous part before leaving a
  list out — any persistent store → `quality-postgres`'s integrity rules; a hot loop →
  `quality-performance`. Every codebase gets `refactoring` on its main language's row, and one with
  tests `quality-testing` on its test runner's.
- **A domain no page covers** (a game engine's frame loop, firmware, a DSL) → propose a project's own
  watch list under `.council/refs/<name>.md`, in the shape of a shipped page and from the project's
  real constraints. Cite repo evidence for every line, leave it `status: draft` until the owner
  accepts it, and name its path on its row.

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
- **Mandatory gates, and a slow suite at verify:** plan and research runs wait for grounding gates.
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
quote. **council-init installs nothing itself**, so every install is built and proved as a task. Every task's Done-when is two-sided (it fails on a deliberate
violation and passes once it's removed), and a new lint, format or type gate is ratcheted
(`council changed`, `Mandatory: no`): the reference's "proved both ways" and "The ratchet". A task
names nothing under `.council/`: the Gates row is added after the build.

On a no, write `guardrails: declined <date>` into the config once the scaffold has written it. `council doctor` then reports
the project's missing checks as a warning rather than an error, so it isn't asked again; delete that line to have them fitted.

## Phase D — Write the scaffold, then build the map

**`council init scaffold`** writes the mechanical files from the templates, each only where none
exists: the config (`last-verified: <date> @ <sha>`, the line `council fingerprint` prints, the
template's run preferences, a Gates row per check from this run's probes),
`conventions.md` when there is no memory file, and `map.md` stamped with `map-commit`. It writes no
roster, markers or cards (D72). Its
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
- **A large repo** → at most 4 plain mapping workers, one area each, in the setup run (one run):
  1. Its plan: `size` squad, one `map-<area>` row set per area from the foot of `run-plan.tsv`, their
     estimate added to `estimated-tokens`; then `council run plan check`.
  2. `<run>/brief.md` from `${CLAUDE_PLUGIN_ROOT}/references/templates/map-brief.md`, one
     `### map-<area>` block per area, every `<…>` filled.
  3. All in ONE message, `subagent_type: small-council:council-worker`, no `name`, no `model`:
     `Seat: map-<area> — <its line> · council-init run`, `Brief: <abs run>/brief.md`, `Reference:
     none — your role is in your brief block`, `Write <abs run>/seats/map-<area>.md`; then `council
     seat map-<area> running agent=<id>`, and `done` on each return.
     No stage doctrine, no `council collect`.
  4. Merge their files into one map of at most ~250 lines, then `council run close`.

## Phase E — Propose, then write

The scaffold wrote only facts nobody has to agree to; what the user decides is proposed first and
written only on their yes. Present:
- the gates (✓/✗) and their side effects;
- the run preferences, sharing included: team or just me (when to ask:
  `${CLAUDE_PLUGIN_ROOT}/references/run/sharing.md`);
- a model per role, proposed from yours: `${CLAUDE_PLUGIN_ROOT}/references/run/models.md`;
- a three-line summary of the map;
- **the book** (`${CLAUDE_PLUGIN_ROOT}/references/run/book.md`): the design page, the stack page and
  the decisions log, each the project's own file where it has one, never a second; the stack page's
  rows with their reasons and watch lists (Phase B). Ask once for the reasons no record gives.

Adjust on request. On confirmation, write into `.council/council.config.md`:
- **`## Stack`**, in place of its placeholder;
- **`## Book`**: each page's path; then each page it names that is not there yet, from its template;
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
  sections; so does each decision Phase D found outside an adopted log, citing its `file:line`.

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
   and asks every time. So every council call is a plain `council <command>`. Only if `command -v council` fails here, add the fallback form the same way —
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
3. **Nothing else to install:** the plugin's hooks do the rest.

## Refresh (re-runs)

Configs drift. On a re-run, or "refresh the council":
- Run `council doctor` and fix what it reports. `council fingerprint check` says whether the stack
  moved; `council memory check` lists memory entries whose anchored file, line or symbol is gone.
- **Memory:** offer to add Scope and Anchor to entries that lack them — one proposal per entry, as
  numbered operations, applied on the user's yes.
- **A `setup: quick` line** (the quick setup a first review made) means the full setup is still to
  do: in the setup run, probe the checks `council init detect` lists; `council init scaffold` then
  fills the Gates rows that still read `✗ not probed` and writes the map's skeleton. Write the stack
  page with its reasons and watch lists (Phase B), build the map (Phase D), write `## Stack` and the
  book. It chose just me: ask about sharing.
  Take the `setup: quick` line out last, after the user's yes.
- **An older config's expert seats** (`council doctor` warns: a `## Roster` section, a `- cards:`,
  `- ledger:` or `- seat models:` line), which no run reads (D72, D74). Propose, as numbered
  operations: each roster row's own page under `.council/refs/` named as a watch list on its stack
  row; each memory entry scoped to a seat's slug re-scoped to that seat's paths; then the section and
  the lines removed. Write on the owner's yes. List the card files under `.council/cards/` as unused:
  the owner deletes or keeps them; never delete one.
- Re-check **every path and gate** in the config against the repo, dry-running the gates again
  (`council run open council-init` first — `council gate probe-<name> -- '…'` needs an open run;
  close it when you are done), and update `last-verified`.
- **A Gates section still written as a list** (backticked commands under `## Gates`, no table): move
  every command into the Gates table, one row each, dry-run them as in Phase C, and fill every cell.
  Until then the helper reads no gate and every report says NOTHING WAS CHECKED: show the diff and
  say what each row came from.
- **Merge, don't overwrite.** Show a diff. Any section the user added or edited — hard rules, a
  pinned gate, a stack row's watch lists, Notes — is theirs: merge around it and surface conflicts for them to
  resolve.
- **Older layouts** → offer to migrate to the current template, which adds Run preferences and the
  Book, and show the diff.
- **Legacy run folders** (`.council/<mode>-output/`) stay where they are as history. An old run still
  marked open → close it on the user's say-so: `council run close --run <dir> --status abandoned`.
- **Permission rules:** bring the council rules in `.claude/settings.local.json` up to Phase F's
  list, as Phase F step 2 says — on a yes.
- **Refresh the map** if `council map status` shows it far behind.
- **The book:** `council book` names a missing page; fill or cut pages as `references/run/book.md` says.

## Output

Tell the user, plainly and numbered:
- the stack page: each part, its reason and its watch lists;
- the gates (✓/✗);
- the files written;
- anything that needs their decision.
