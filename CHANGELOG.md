# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] — 2026-09-15

The secret weapon for tough problems: the experts argue a big feature out before it's built, and a
post-game checks the finished work against what you actually asked for.

### Added

- **The war room** (inside council-plan). For a big or tough feature — or when you say "debate it" —
  the seats answer each other before the Chair judges. Round 1 stays blind; then each seat reads the
  others' proposals and answers the points that name it, with evidence. Every point ends agreed,
  settled by the code, sent to the verifier, or as a fork you rule on. Two rounds, never a third; the
  same workers are resumed, so it adds tokens, not agents. The plan records how the council decided.
  The protocol lives in `references/war-room.md`.
- **council-postgame.** Checks finished work against your original request, word for word: what you
  asked → what was planned → what was built, where it drifted, what's missing or was built unasked, and
  one next move, handed to council-implement or council-plan on a yes. Blind verifiers check every
  "built" claim and never see the plan or the log. It also works on work done without the council,
  even in a repo with no `.council/`. council-implement offers it when the build's log says it's
  worthwhile.
- **Your request, kept.** Every run saves your words in `ask.md` before anything else. `council ask
  save` files them under `.council/asks/`, redacting anything that looks like a secret — keys and
  tokens by their shape, passwords, credentials in URLs, private-key blocks — and every deliverable
  points at its request, so the chain survives cleaning up `runs/`. Filed requests stay out of git:
  council-init and the first filing put `asks/` in `.council/.gitignore` — drop that line to share
  them with the team.
- **Helper:** `council ask save` (it follows a continued request, re-files rather than duplicates, and
  never writes outside `.council/asks/`); `collect` checks a war room's round-2 files and waits for
  seats still answering; `check` confirms each post-game part quotes the request, word for word;
  `index` keeps earlier council work out of a post-game, whose verifier reads it; `prior` scans
  post-games; `memory select` counts the run's mode, for lessons scoped to one mode; `run open
  council-postgame` works without a council home; `run close` warns when a run never filed its request.
  The SessionStart hook stays quiet in a folder that holds only post-game results.
- **Evals:** helper, hook, structural and phrase checks for all of it; drills D18–D23; four more suite
  cases (dormant until someone runs the suite).

### Changed

- council-implement takes a post-game as a third kind of input, and its log records the request, the
  starting commit and a converge table.
- Every plan maps each part of the request to a task, or to your words that ruled it out.
- The verifier also answers MET / PARTLY MET / NOT MET / CAN'T TELL against a request; the worker knows
  the war room's two rounds.

## [0.5.0] — 2026-09-15

Proof. Until now nothing showed the council behaves the way its doctrine says. 0.5 adds a behavioural
suite that runs Claude for real and scores it, with and without the plugin.

### Added

- **A `claude plugin eval` suite** (`evals/suite/`, 12 cases):
  - triggering cases, and near-misses where no mode may start — each also checks the ask was handled,
    so a run that never started can't pass;
  - sizing cases that stop at the proposal — right-sized, seats not going, nothing dispatched early;
  - a Squad review run end to end from a `/council-review`: workers dispatched, the auth bypass sent to
    a blind verifier of its own and reported in the deliverable;
  - a seeded Solo review scored for recall (the planted bug) and precision (memory respected), with the
    answer key outside the fixture;
  - verifier calibration on two true and two false claims, from a dispatch that stays blind;
  - resuming an unfinished run instead of restarting it;
  - council-init on a Godot game — the council fitting a non-web stack.
- **Results history:** `python evals/record_eval.py` saves each run's summary under `evals/history/`,
  compares it with the newest earlier clean run of the same shape (ablation mode and tags), and flags
  any case whose score dropped. It refuses partial and errored runs.
- **A manual CI workflow** (`.github/workflows/evals.yml`) for the suite: Claude Code and both models
  pinned, the Bash sandbox installed, and a cost ceiling.
- **Structural and validation checks for the suite:** every case has a prompt and a grader; every
  scaffold exists and is executable LF bash; every tool a grader counts is one the run can call; every
  grader regex compiles; the near-misses assert that no mode starts in either arm.

### Changed

- **Plans quote their constraints.** Every task carries the hard rules, memory entries and decisions
  that bind it, word for word, and a real structural choice is laid out as two stances for the user to
  rule on before tasks are grouped.

## [0.4.0] — 2026-09-15

Tailored experts. 0.3 made the council disciplined; 0.4 makes its experts experts in *your*
project, whatever the stack.

### Added

- **Seat cards.** council-init writes `.council/cards/<slug>.md` per seat: each principle of the
  seat's doc translated to this project in one line, the severity rubric in this repo's terms, where
  to look, and what isn't a finding here — at most ~6 KB. Workers read the card first and open the
  full doc only for the principles they cite; the card's first line is their proof of reading.
- **Four stack-agnostic lenses:** Accessibility (Pickering), Concurrency & runtime (Goetz), Untrusted
  input & bytes (Patterson) and Operability (Nygard). The catalog now has fourteen seats.
- **Gates carry a probe, what they need, and their side effects.** `council gate --all` skips a gate
  marked not runnable, and never runs one whose side effects involve cost, hardware, deploys or
  credentials — those run only by name, with your go-ahead.
- **A stack fingerprint** (`council fingerprint`): the manifests and code languages, recorded at
  init. Prepare and the doctor notice when the stack moves and suggest a refresh.
- **Scoped memory.** Entries carry **Scope:** and **Anchor:** fields. `council memory select` gives
  a run only the entries in scope; `council memory check` flags entries whose anchored file, line or
  symbol is gone.
- **Earlier council work, gathered once.** `council index` ends with the reviews, logs, research and
  plans that mention the changed files or cover them through their `areas:`; `council prior` does the
  same for any paths.
- **The seat ledger.** Closing a completed run adds a row per seat to `.council/ledger.tsv`: items
  raised, kept, cut and refuted, and tokens. `council ledger` shows each seat's record; Convene
  estimates from it, and a refresh proposes roster changes with the numbers shown.
- **One lens, several areas:** a roster may give a lens several rows, each with its own slug and
  surface (`dodds-web`, `dodds-admin`).
- **A seat-doc template** for project-local lenses: `status: draft` until you accept it, and every
  principle cites repo evidence.
- **Doctor checks** for repeated slugs, missing or oversized cards, cards whose doc is gone, stale
  memory anchors, a changed stack, and Gates tables without side effects.

### Changed

- **Every inherited seat doc gains "Applying this seat to another stack"** — the origin stack, the rule,
  and a translation table — and keeps its origin-stack examples (TypeScript, Next.js, tRPC, Prisma,
  Postgres) in a final section. Principle numbers and meanings are unchanged; titles that named an
  origin product now name the idea.
- **Brief** selects the memory in scope with `council memory select`, once Assign has named the
  seats; **Convene** checks the fingerprint, so a changed stack goes in the approval message.
  **Learn** writes Scope and Anchor into accepted entries, and the ledger is recorded at close.
- **The Gates and Roster tables are read by their header names,** so older configs keep working.
- **The review and plan owner tables name the four new seats,** and a verifier copies each item's
  synthesis number into its table, so verdicts land on the right seat in the ledger.
- **A seat's brief block gives the full doc's absolute path** (`- doc:`), since a card names its doc
  relative to the plugin.

## [0.3.0] — 2026-09-15

The discipline release. The method moves out of prose the model has to remember and into three
places:
- stage doctrine, read at the moment of action;
- a helper script for every mechanical step;
- hooks that enforce the contracts.

It is built from a verified audit (47 confirmed findings) and a study of 22 peer projects. See
[`docs/design/doctrine-0.3.md`](docs/design/doctrine-0.3.md).

### Added

- **The `council` helper** (`bin/`, bash and git only; on PATH while the plugin is enabled). It
  covers `run open / status / close`, `state`, `seat`, `index`, `gate` / `gates`, `collect`, `check`,
  `map status` and `doctor`. The SessionStart hook shares its council-home resolver, which now handles
  bare repos and submodules.
- **Stage doctrine** in `references/doctrine/01–10`, one file per stage, read on entry. The stages
  are now Convene · Prepare · Assign · Brief · Work · Collect · Judge · Challenge · Deliver · Learn.
- **A seat check (SubagentStop hook).** A council worker or verifier can't finish without a valid
  file. It is blocked once, with the reason, and can never loop.
- **A change index every seat shares:** hunks, changed symbols, callers and covering tests, computed
  once instead of re-traced by each seat.
- **Blind verification:**
  - a verifier gets only the claim and its location;
  - each P1 and each protected subject gets its own verifier;
  - new verdicts, MISCITED and CANNOT VERIFY;
  - a mechanical citation and origin pre-check (`council check`) runs first.
- **Richer findings:** each carries its origin (introduced, touched or pre-existing, from `git
  blame`), its basis (seen or inferred) and "refuted if". Workers keep a live seat file with an index
  block, cap their questions for the user at three, and show conflicting evidence with both sides.
- **Several open runs at once**, each with its own status. Seat states carry agent ids. Resume
  re-invokes the run's own mode skill.
- **Run preferences in the config:**
  - an approve-without-asking size, default Squad (a `/command` starts runs up to it);
  - an agent cap, default 10 including verifiers.
- **Run visibility:** skipped seats and their reasons appear in the approval, a progress line shows
  as seats finish, and the actual cost is reported at close.
- **Build loop:**
  - a gate baseline before the first edit;
  - before and after evidence for each task;
  - a clean-context diagnosis after two failed verifications;
  - a converge pass at the end;
  - per-task commits offered;
  - "notes for later tasks" at the top of the log.
- **Plans** are ordered as vertical slices, walking skeleton first, with Touches and Done-when on each
  task. **Research** scouts first and uses rival hypotheses for "why" questions.
- **Memory:**
  - a `## Rejected` list, so rejected proposals are never proposed again;
  - an admission rule;
  - proposals written with evidence and effect;
  - consolidation by numbered operations instead of rewrites.
- **Surface markers per seat** in the roster. init's mapping squad runs as a proper council run, and
  init offers a permission rule for the helper.
- **Evals:**
  - `run_cli.py` for the helper;
  - seat-check and multi-run cases in `run_hook.py`;
  - `run_phrases.py`, advisory, now separate from the blocking structural checks;
  - drills D12–D14.

### Changed

- **context-core is now a slim kernel:** the eleven laws, the stage index, the helper, the file
  layout, the limits and resume.
- **The modes are organised by stage** (`## At <Stage>` sections).
- **Worker and verifier contracts, v2.** For changes, the burden of proof is on the builder, and a
  builder's own account is never evidence.
- **Performance principles are renumbered "Principle 1–6"**, so they can't be mistaken for severities.
  An unmeasured optimization is now P3.
- **test-architect's fix mode** is now checked by the verifier.

### Fixed — from the audit

- **Resume only reloaded the core, not the mode.** It now re-invokes the run's mode skill.
- **Synthesis and verification existed only in the Chair's context,** and two verifiers could
  overwrite one file. Now there's `synthesis.md`, one `verify-<n>.md` per verifier, and a check that
  every shipped item has a verdict.
- **One shared active-run pointer let concurrent runs erase each other.** Runs now carry their own
  status and are found by scanning.
- **Every seat re-traced the same blast radius.** The shared change index replaces that.
- **The structural eval passed reversed rules and failed harmless edits.** It is now split into
  blocking structural checks and advisory phrase checks.
- **A `/command` could launch a Full run without a cost check.** It now approves only up to the
  configured size.
- **"Performance P1" meant a principle in one place and a severity in another.** The principles are
  renamed.

### Fixed — from the 0.3 self-review

A ten-agent review of this release confirmed 24 problems. All are fixed, and each has an eval.

- **Gate commands lost their quoting.** `council gate <name> -- '<command>'` now runs one quoted
  command exactly as written, and keeps separate words as separate arguments.
- **A paired seat could prove it read only one of its two docs.** Briefs and seat files carry one
  `ref:` line per doc, and `collect` checks each.
- **After a compaction the hook could resume the wrong run** — a paused one, or another session's.
  Runs record the session that opened them; the hook resumes only that one and lists the rest.
- **`collect` passed a seat whose worker had failed, or whose file was only a header.** It now flags
  a seat still running, failed or blocked, an empty index, and index lines it can't read.
- **Commands could land on the wrong run.** `run open` refuses a second in-progress run on the same
  tree unless you say `--alongside`. With two open, every command needs `--run` (a folder name works).
- **Empty table cells shifted columns, and a pipe inside a gate command split its row.** Rows keep a
  placeholder for empty values; cells split only outside backticks; the doctor flags a row whose cell
  count is off.
- **The change index** listed prose words from Markdown as symbols and missed shell functions. It now
  reads code files only, knows `name() {`, spots test files by their path, and says when its search
  budget ran out.
- **Index lines written as a list, backticked paths and en-dash ranges** read as zero items or broken
  citations. They're accepted now.
- **Re-dispatching a seat overwrote its token count.** Tokens add up, and each new agent id counts.
- **Runs were sized without their verifiers.** Sizes now include them, and Challenge has an overflow
  rule for when the cap is tight.
- **init's mapping squad opened a run before `.council/` existed.** `run open council-init` creates it.
- **A run resumed in a new session would wait forever** for workers that died with the old session.
  The hook and the kernel now say to mark them failed and re-dispatch each once.
- **The diagnosis worker had no brief or output file,** and a re-verification overwrote the first
  verdict. Both are defined now (`diagnose-<n>.md`, `verify-<n>b.md`).
- **The verifier couldn't open a research claim's URL.** It has web tools now.
- **The seat check let through any reply that mentioned "BLOCKED".** Only a line that starts with it
  counts.
- **An old open run could disappear from `run status`** behind twenty newer ones.
- **The helper and hooks could be committed without the executable bit.** The validator checks it.
- **The blocking eval still checked wording.** Those checks moved to the advisory phrase eval.

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
