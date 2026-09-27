# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.13.0] — 2026-09-27

The sixth evolution milestone (Phases 6–13) gives each run a checkable record, and learns from that
record only as far as it supports. It adds:
- an evidence ledger;
- a bounded repair trail;
- observed-failure memory, filed only on the user's own words;
- seat advice;
- a baseline-versus-council benchmark harness;
- a read-only run cockpit;
- history across runs;
- one conservatively tuned setting.

**Upgrading:** no migration or new mandatory dependency, and older runs stay readable.
- The new commands use optional Python 3.8+. Without it, each says so, and the existing commands
  still work.
- Context packs are now off unless the project config has `- context packs: on` under
  `## Run preferences`, or the user asks for them in a run.
- A build now stops after a gate fails three times.

### Added

- **Conservative self-tuning.** `council tune` proposes from the project's own record: the estimate
  per worker that `council route recommend` budgets with (per agent), once five completed runs
  measure it and it is off by more than a quarter; roster changes whose seat advice clears its bar (made only
  through a council-init refresh); and nothing about behaviour — context packs, run size and
  verification depth are held until a benchmark shows a change helps. `council tune apply budget
  <value> --user-said "…"` writes the value the user was shown as one line under `## Run
  preferences`, logging the evidence, the user's redacted words and the exact line it replaced in
  `.council/tuning.md`; `council tune revert budget` puts those bytes back and refuses over a hand
  edit. Only a ceiling the user gives can shrink a run. Without the line, the route is unchanged.
  Optional Python 3.8+.

- **History across runs, gated on enough data.** `council history [--json]` reads every run of the
  council home and reports runs by status, mode and month, the project's gates (a build's
  before/after proofs and gate probes counted apart), repair trails, claim verdicts, seat evidence
  and missing data. A median, share or ratio — cost and agents per run, tokens per agent, actual
  cost over the plan's estimate, repairs resolved, the verifier's catches — appears only once five
  runs (not items) carry its data; below that it says "too few". Read-only; no database or
  dashboard.

- **A read-only run cockpit.** `council tui` draws one screen from the run's own files — the
  plan's decisions and skipped seats with their reasons, seat states and tokens, agents against
  the cap, gates, each repair task's next step, claim verdict counts, memory proposals waiting and
  the last events. `--watch` redraws every two seconds and stops by itself when the run closes;
  `--json` prints the same snapshot as data (`council.run-snapshot/1`). It never writes a file or
  an event; strips control characters from every value it draws; draws legacy and malformed runs;
  follows no link or junction; opens files on Windows so the helper can still replace them while it
  reads; and prints plain ASCII with `COUNCIL_ASCII=1`. Optional Python 3.8+; no curses, no server.

- **A baseline-versus-council benchmark harness.**
  - **Cases.** Three build cases (`evals/suite/bench-*`, tag `benchmark`) run through
    `claude plugin eval` with both arms: the same plain prompt, model, tools and project, with and
    without the plugin.
  - **`evals/bench.py score`** judges each kept run on hidden checks (encoded in
    `evals/bench/*.hidden`), restored original tests, frozen and protected files, scope, removed
    assertions, a required test and false completion claims.
  - **`compare`** reports the arms side by side and calls nothing a result below ten pairs.
  - **Tests the run cannot fake.** The scorer runs the hidden and original tests in an isolated
    Python that imports the real `unittest` first, under random module names, with a nonce-tagged
    result outside the project. A pass needs:
    - the exact test count;
    - no skips;
    - a canary assertion that fails.

    It also rules out six fakes, and reads final reports so that a product sentence ("cannot
    delete") is not a disclosure while "not fixed yet" is.
  - **`self-test`** (in CI, no model) proves each case is unsolved when untouched, solvable, and
    scored as intended on every trap.
  - **Budget.** A pilot is paid and awaits the owner's budget (see `evals/bench/README.md`).

- **Seat learning, advisory only.** `council ledger advice [N] [--json]` says how much each seat's
  record can support: runs that judged its items, useful items (kept and not refuted) with a 90%
  plausible range that counts at most five items from any one run, refuted items among those
  verified, and tokens per useful item. It advises (retain, lower priority, narrow, pair, drop?,
  unclear) only past a stated bar of 3 judged runs and 15 items of evidence counted that way, and
  "drop?" only after eight, as a question for the user. A council-init refresh proposes roster
  changes only where the advice clears the bar. It never changes a roster, a route or a run.
  Optional Python 3.8+. An independent review found that the first version capped evidence per run
  only in total, so one big run could still count as three; that and seven smaller gaps are fixed.

- **Phase 8 memory foundation.** Scoped selection includes a settled entry's meaning and origin
  when recorded. User-confirmed observed failures have a separate F category with required scope,
  origin, evidence and verdict; they are historical leads, never rules. Legacy AP/EC/D entries
  remain readable. Focused local evals cover retrieval and incomplete-entry exclusion.

- **Observed failures must be supported to be served.** An F entry reaches a brief only with a
  verdict that establishes it (OBSERVED, REPRODUCED, or a verifier's CONFIRMED, REFUTED, MISCITED,
  REGRESSION, INCOMPLETE, SCOPE-CREEP — never INFERRED, ASSUMED or UNCERTAIN), a scope narrower
  than every run, and a Failure field; a Rule written into one is never shown as its meaning.
  `council memory`, `select` and `check` open the files its Evidence names: an entry whose files are
  gone, or whose cited lines no longer show a verifier's verdict, is left out with the reason, and
  `memory check` (and `doctor`) report it. Memories without observed failures behave as before.
  After an independent review, the audit also refuses an id two entries share, any spelling of an
  every-run scope (read the way the scope matcher reads it), a verdict that is not the verifier's
  own capitalised word on a cited line, the memory file cited as its own evidence, links that lead
  outside the project and placeholder fields; and a cited line number too large to exist can no
  longer make every memory command loop forever.

- **Observed failures from a run's verified record, filed only with the user's words.** (Later: the
  user's words are flattened to one line before redaction, so a secret split across lines is
  still caught.)
  `council memory propose claim <id>` drafts an F entry from a claim the blind verifier refuted or
  miscited; `council memory propose repair <task> --scope <paths>` from a build task's recorded gate
  failures. The helper fills the fields from `claims.jsonl` or `repairs.jsonl` — not from a summary —
  redacts secret-looking text (a private key whole), keeps copied text from forming fields or
  comments, scopes a claim only by cited files that exist, refuses duplicates and anything that could
  not be served, and files the draft under `## Proposed` with an id no entry uses. `council memory accept|reject F-<n> --user-said "<their words>"`
  applies the user's answer with the date and their words, and writes only when the result checks
  out and nothing else in the memory changed. Optional Python 3.8+; the manual path remains.

- **Phase 7 bounded repair trail.** `council repair record|show|check` snapshots each failed build
  gate and its reruns, suggests an advisory failure category and expert lens, distinguishes a red
  baseline, and stops after three failed executions of the same gate. The second failure recommends
  independent read-only diagnosis; a nonempty pass closes the trail. It never runs a gate, dispatches
  an agent, changes code or attributes a failure to the edit. Python 3.8+ is optional, with a manual
  log fallback. Local fixture checks do not establish live model behavior.

- **Phase 6 evidence ledger.** `council evidence build|show|check` projects synthesis claims,
  evidence states, source-seat ids and blind-verifier rows into deterministic run-local
  `claims.jsonl`. The existing Markdown remains authoritative. Checks flag absent or stale links,
  missing reproduction artifacts and conflicting verifier rows; they do not establish claim truth.
  Python 3.8+ is optional. Older runs remain readable without migration, though an evidence check
  on one may flag missing new fields.

### Changed

- `council ledger` shows `-` rather than `0%` shipped for a seat that no run judged (a
  council-init or build run credits no items), and points to `council ledger advice`.

- A third failed build-gate execution now stops the build's product edits and cannot fall through to
  a verifier fix or success commit. Blocked tasks do not count as built; helper-only token usage is
  labelled as such on the receipt. No automatic rollback is performed.

- **Context packs are opt-in.** The Chair builds seat context packs only when the project config
  has `- context packs: on` under `## Run preferences`, or the user asks for them in a run. A
  missing line means off; new configs start with `context packs: off`. Packs add material to every
  worker and their effect on findings is unmeasured until the Phase 5.5 live paired run.
  `council context build` and `show` are unchanged.

### Fixed

- **Context packs for a project reached through a link.** The pack builder resolved the code root
  but checked the run, output and expansion paths as spelled, so under a link — macOS's `/var` is
  one to `/private/var`, and a Windows temp folder can have an 8.3 name — it refused every pack as
  outside the project. A path spelled through the root's own link is now read under the resolved
  root; links below the root are still refused. Found by macOS CI, the first time it reached the
  context evals.
- **CI shows every failing suite.** Each check now runs even after an earlier one fails, so one run
  reports them all, and the job still fails if any does. macOS had stopped at the first.
- **macOS: a byte-order mark at the start of a state file is stripped again.** macOS's awk reads a
  `/\357\273\277/` regex as three characters, so a session-state file starting with a mark kept it
  there. A second run could then open on the same tree, and `council state` updated the wrong key.
  The five strips now take the mark as a string from the environment.
- **Windows CI.** The helper and hook evals resolve the runner's temp folder to its long name
  (`RUNNER~1` → the real one), so two path checks no longer fail there only.

The last two fixes were written on 2026-09-19 (`fix/0.7.1-ci`) but never merged, which is why `main`'s
own CI has failed these four checks since then.

## [0.12.0] — 2026-09-24

The fifth evolution milestone makes a seat's assigned context level actionable without replacing
the Chair's brief or the worker's reference docs.

**Upgrading:** no migration or new mandatory dependency. New packs are generated only on request,
after `brief.md` and a valid run plan exist. Older runs and brief-only dispatch still work.

### Added

- **`council context build <seat>` and `show`.** A selected seat receives a run-local Markdown pack
  at its validated `minimal`, `focused` or `full` level. `--expand PATH` can be repeated to request
  omitted evidence explicitly. The generated metrics sidecar makes the selection inspectable, and
  successful builds are recorded in the run event stream when one exists.
- **Precision-context contract and evals.** The provider is optional Python 3.8+; the contract
  documents relevance signals, selection boundaries, explicit expansion and fallback behavior.

### Known limits

- Selection is a bounded heuristic, not proof that omitted files are irrelevant. It cannot override
  the brief's hard constraints, infer runtime behavior, or modify a project's `CLAUDE.md`.
- If Python is unavailable or generation fails, the complete brief and reference docs remain the
  dispatch path; a missing pack must not be presented as built.

## [0.11.0] — 2026-09-23

The fourth evolution milestone adds a bounded, inspectable impact graph alongside the existing
change index. It distinguishes what changed from direct static importers and likely tests without
claiming complete runtime coverage.

**Upgrading:** `council index` still works with Bash and Git alone. With optional Python 3.8+, it
also writes `<run>/impact.tsv`; `council impact` refreshes that graph from the saved baseline.
Older runs and the manual routing workflow need no migration.

### Added

- **Impact graph v1.** Versioned TSV rows record Git change provenance, touched definitions,
  direct import/dependent links, likely tests, path-based surfaces and explicit provider limits.
  The Git delta includes committed, staged, unstaged, untracked, renamed and deleted paths.
- **Incremental language providers.** Python AST handles static imports and definitions, including
  common `src/` layouts; JS/TS resolves literal relative imports and nearby declarations. Both
  are bounded and evidence-labelled. No project code, compiler or external service is run.
- **Focused impact evals and ADR.** Temporary-repository tests cover the graph contract, rename
  and deletion consumers, deterministic output and the CLI integration on all CI platforms.

### Fixed since 0.10.0

- Run plans now reject a missing Chair, incompatible Solo/Full team sizes, or independent and
  adversarial verification without a selected verifier.
- Seat events preserve concurrent update order; abandoned event locks can be recovered.

### Known limits

- Relationships are direct and static. Dynamic imports, aliases, transitive dependencies and
  actual test coverage require further evidence; a missing edge is not a clean bill of health.
- Python is optional. If unavailable or the provider fails, the existing `index.md` remains the
  fallback and the helper reports that the graph was not refreshed.

## [0.10.0] — 2026-09-23

The third evolution milestone adds an explainable, optional routing recommendation before a run.
It is a deterministic heuristic, not a new dispatcher or a claim of measured cost savings.

**Upgrading:** existing manual sizing and run plans still work. The routing command is read-only;
it does not change past or current runs, select a model, or launch agents.

### Added

- **`council route recommend`.** Proposes task risk, complexity, uncertainty, council size,
  generic seat archetypes, verification and an estimated token budget. Each choice carries a reason.
  Explicit inputs can override the initial assessment; an agent cap and optional budget ceiling
  constrain the proposal. Unaffordable or unverifiable recommendations say `needs-rescope` instead
  of lowering required verification or disguising the estimate. `--classic` exposes a static
  comparison policy.
- **Adaptive routing contract.** `references/adaptive-routing.md` defines the advisory boundary,
  manual roster mapping, plan validation and limits of the heuristic.

### Known limits

- The earlier no-history estimate was roughly 60–100k tokens per worker, and the existing docs
  describe past runs as averaging around 100k. These are planning baselines, not proof that routing
  improves outcomes or cost. Reliable per-task effectiveness data, impact analysis and learned
  policy tuning are deferred.

## [0.9.0] — 2026-09-23

The second evolution milestone adds a run-local event stream for CLI-observable lifecycle actions.
It is a small, versioned TSV contract for later inspection and analytics, without adding a server or UI.

**Upgrading:** new runs get `events.tsv` automatically. Older runs continue without an event file;
the helper does not invent history for them.

### Added

- **Append-only run events.** Run, phase, status, seat and gate actions add sequenced UTC rows under
  a per-run lock. The schema and event meanings are documented in `references/event-stream.md`.
- **`council run events show` and `check`.** Show gives a short chronological view; check validates
  the schema and continuous sequence. `council doctor` also flags a missing or damaged event stream.

## [0.8.0] — 2026-09-22

The first evolution milestone makes the Council's routing decisions inspectable and enforceable
without replacing its execution model. New runs now carry a small versioned plan before any context
or worker is dispatched.

**Upgrading:** nothing to migrate. Runs opened by an older version have no plan stamp and continue
to work as legacy runs. Every new run gets `run-plan.tsv` automatically.

### Added

- **A versioned run-plan contract.** `run-plan.tsv` records size, risk, complexity, uncertainty,
  selected and skipped seats with reasons, context allocation, agent and token budgets, and required
  verification in five plain TSV columns.
- **`council run plan check` and `show`.** The checker rejects placeholders, unknown or duplicate
  fields, invalid vocabularies, mismatched run identity and mode, missing seat context or budget,
  and a selected roster over either the plan or project cap. `show` renders a valid plan plainly.
- **Pre-dispatch enforcement.** The helper refuses to enter Brief, Build or a later standard stage with an
  invalid plan, and refuses to queue or start an identity the plan did not select. `council doctor`
  reports incomplete early plans as warnings and invalid later plans as errors.

### Changed

- Convene now records run-level judgments in the starter plan; Assign completes and validates its
  seat rows before it records workers. Brief starts from the checked plan, so its context and budgets
  cannot silently drift from the routing decision.

## [0.7.1] — 2026-09-18

A repair release. A deep review of 0.7.0 found its checks passing in places where they had not
actually looked. Seven independent hunts each had their findings checked blind against the code,
and deliberate breakage showed which of those problems the tests would catch. Most fixes here make
a check read what agents, models and projects really write, and refuse what it can't read instead
of passing it.

**Upgrading:** if `council doctor` says the Gates section is an "older layout (a list …)", run a
council-init refresh once to move it into the Gates table. Until then `council gate --all` checks
nothing, and every build says so.

### Added

- **`council run resume`.** A run carried into a new session, or past `/clear`, was called "not this
  session's run" at the next compaction, and a paused run had no way back. `run resume` marks the run
  in progress, drops a pause's `closed:` stamp and records this session as its driver; context-core,
  the doctrine, the hook and the paused-run error all point at it.
- **The evals run on macOS with its own bash 3.2.** CI gains a `macos-latest` leg, where
  `COUNCIL_EVAL_BASH=/bin/bash` starts the helper and both hooks with the system bash, so the bash 3.2
  and BSD-tools promise is finally tested.

### Changed

- **Every command refuses words it doesn't take.** `--flag=value` now works for every flag (before,
  only `--run=` and `--session=` did, so `run close --status=paused` closed a run as complete), and a
  stray word, flag or missing file is refused with exit 2 and a message instead of being ignored.

### Fixed

- **Gates tell the truth.** Under Git Bash, `cmd /c …` lost its `/c`, opened a prompt and exited 0,
  so a batch-file gate "passed" without running; only that switch is now rewritten, and a cmd that
  just opened its prompt fails. The Gates table's Run at, Mandatory and Checked cells are read as
  small vocabularies, so "verification", "required", a tick or **yes** no longer drop a mandatory
  gate from the verify set. With a red baseline a gate compares the failing tests its runner names,
  not whole lines. The guardrails reference says a failing runner must exit 1 to 255 (only the low
  8 bits reach the helper, so 256 failures read as a pass).
- **Every older Gates list is recognised**, including ``- tests: `pytest` `` and a command on the line
  under its list item, so `doctor` and `gate --all` say "older layout — a council-init refresh
  migrates it" instead of "no gates configured".
- **A Windows switch in a gate is named.** Git Bash turns `/p:Configuration=Release` into a path before
  a Windows tool sees it (only `cmd`'s `/c` and `/k` are rewritten), so `doctor`, `gates` and every
  gate run now point it out and say to write `-p:…` where the tool takes it (msbuild and dotnet do),
  else `//p:…`.
- **`council changed` looks at the files it names.** `--glob '*.{js,jsx}'` matched nothing (git
  pathspecs have no braces), so a fitted linter passed forever; braces are spelled out, a pattern
  that matches no file is an error, and long lists are passed in batches. The council's own files
  are skipped, as the change index skips them, so the ignore lines `run open` adds to an older home's
  tracked `.gitignore` never count as the user's change.
- **`council check` and `collect` read citations and items as models write them.** Notes, lists,
  links, bold, table columns, `L58`, `#L12` and trailing commas no longer read as missing files or
  bad lines, and bare paths, `path::symbol` and `path: 12` are checked instead of skipped. Items
  written as a table, `### 2 · …` or `3. P2 · …` are read; a synthesis whose items can't be read is
  no longer "0 items, 0 broken". Deleted code is labelled as the change's own, and a file the change
  only renamed no longer makes every line in it "touched". In a plan, research or post-game, a path
  that isn't on disk is an area or a file still to be written, not a broken citation; in a review an
  item with no `path:line` is named (`no-citation`) instead of passing.
- **The memory is read as projects write it.** Entries written as bold bullets, not only as
  `### AP-n:` headings, are read (one real project's 63 entries read as "no entries yet"), and
  entries under Proposed, Rejected or Retired are no longer served as settled. A configured memory
  path that doesn't exist is named instead of quietly turning memory off, and `doctor` points at the
  real file instead of advising an empty new one. A second memory file whose entries the council
  never reads is called out by `memory`, `memory select` and `doctor`. `memory select` takes seconds
  instead of minutes, and scopes written with brace globs, `all`, `./`, a leading `/`, backslashes
  or semicolons now match.
- **A Solo run selects the memory in scope too**, instead of reading the whole file or missing
  settled entries (the only select step was at Brief, which Solo skips).
- **`collect` judges each seat on its own.** The proof-of-reading key can't be switched off by
  writing it as `- **ref:**` or `Ref:`, and a reference doc that opens with front matter no longer
  fails an honest worker.
- **The seat check reads replies the way agents write them.** Any JSON spacing of
  `stop_hook_active` counts, BLOCKED is taken only as a reply (not "* Blocked users can …" in a
  report), and the seat file is found wherever the Wrote line names it, with words before the path
  or a full stop after it. A named absolute path that doesn't exist now blocks. In a review it sends
  back an item that names no place at all, and it takes `- (none)` for an empty lane, as `collect`
  does.
- **A war-room worker lost in round 2 is re-dispatched for round 2.** Marked failed in a new session,
  it used to have `collect` flag its finished round-1 file and say "re-dispatch it once", which re-runs
  round 1. The failure is now the round-2 row's, and `collect` says to record a fresh `<slug>-r2`
  worker.
- **Several `council seat` calls at once keep every row.** They shared one temp file and could lose
  rows or the header; they now take turns behind a lock. `tokens=74.3k` was stored as 743; `k`, `M`
  and comma thousands are read, and a value with no number is refused.
- **The change index names every file.** Past 80 files it stopped naming them, so whole areas of a
  big change were never assigned; the rest are now listed at the end and Assign says they still
  need an owner (`COUNCIL_INDEX_CAP` lowers the cap). Renamed and non-ASCII names come out right.
- **`council map status` works from any folder**, and when the map's commit is gone after a rebase
  or squash, the SessionStart hook and `doctor` say so instead of presenting the map as current.
- **A bare repository's council is found in the worktree that holds it**, not whichever worktree
  sorts first, so adding a worktree no longer moves everyone's home.
- **After `/clear` the hook no longer says to wait** for workers whose notifications can never
  arrive; it says to run `council collect`, mark the rest failed and re-dispatch each once. A
  build's implementation log no longer counts as a finished deliverable.
- **A proof's saved test is found in Godot** (`-gtest=res://…`) and after `cd <dir> &&` or
  `npm --prefix <dir>`; a test file outside the project isn't counted as one the project keeps.
- **Filed requests stay where they belong.** `ask save` refused nothing: a `..` in the path, a request
  file that is a link or an `asks/` folder that is a link let it append the user's words to any file.
  All three are refused now. A re-save no longer duplicates the user's own dated headings or deletes
  the words saved before. Redaction covers about twenty more everyday secret shapes (GitLab, npm,
  PyPI, Hugging Face, Slack app tokens and more), strips indented key bodies, and keeps the ordinary
  text around a snipped key. A password described in words ("the password is
  hashed-with-bcrypt-before-storage") stays readable; a passphrase of random words stays redacted.
- **Run scratch and the user's words stay out of git in every home.** `run open` and `ask save` now
  add the `runs/`, `asks/` and `active-run` ignore lines to older homes too, including outside git.
  A 0.7.0 home that shared requests by leaving the `asks/` line out is told when the line comes back.
  To share requests now, add a `!asks/` line (README and the design notes say so).
- **The post-game quote check is fair and safe.** Curly apostrophes and non-breaking spaces match, a
  "Quote:" title isn't taken for the quote, and a quote holding a secret never passes.
- **The ledger counts what was really written:** `from: hunt#1, #2`, `beck#1,2`, "REFUTED (latent)",
  and a `#` cell written `1.`. It reads the `· from:` field the format writes, so a reason that says
  "repeats from: beck" doesn't move the item to another seat.
- **council-init's mapping squad gets an Index line and a cap**, so a worker that follows init's
  brief is no longer sent back by the seat check.
- **test-architect names the verifier's temp folder the way the file tools open it** (`C:/…` on
  Windows, not `/tmp/…`), so verdicts aren't lost.
- **The design checks say what they check.** `quick_validate` rejects an unquoted
  `${CLAUDE_PLUGIN_ROOT}` path in hooks.json (the hook never runs from a folder with a space), and
  three helper checks now fail for the reason their names give.
- **A citation that lists several lines is no longer reported broken.** `council collect` and
  `council check` now read `path:12,40-55` — single lines and ranges in any mix, blanks around the
  commas allowed — and check every piece against the file's length, so `core/MAP.md:58,77` in a
  123-line file is `ok`, not `bad-line`. The origin blames every listed line, so a list of old and
  new lines reads `touched`, as a range does. A range with a second dash or a sign (`5-6-7`, `5-+7`)
  is now `bad-line`; it used to pass on the numbers before its first dash and after its last.
- **A memory anchor that lists lines is read whole.** `council memory check` split an entry's
  **Anchor:** on every comma before it looked for `path:line`, so `src/a.py:1,3` became `src/a.py:1`
  and a symbol named `3`: a false alarm ("nothing in the code is named 3 any more") when both
  lines exist, and a silent pass for a line past the end wherever its number is a word in the code.
  A piece that is only a line or a range (`3`, `40-55`, blanks allowed) now stays with the
  `path:line` before it, so `src/a.py:1,3, summary` is two anchors, `src/a.py:1,3` and `summary`,
  and every listed line is checked against the file's length. The conventions template now says an
  anchor may list lines.

## [0.7.0] — 2026-09-16

Proof instead of opinion: the council now says out loud when nothing was actually checked, offers to
fit the checks a project is missing, and ends every build with the same six-line receipt — including
the shortcuts it took.

### Added

- **The missing checks, offered once.** council-init now compares the project against five
  guardrails — formatter, linter, type check, test runner, dependency audit — and lists what's
  missing, cheapest-first, one plain line each on what it would catch. On a yes it writes
  `<home>/plans/guardrails.md` and hands it to council-implement, so each one is fitted with
  before-and-after evidence, a blind verifier and a log row. It installs nothing by itself. New
  reference `references/guardrails.md` carries the per-stack commands (Node, Python, Go, Rust, .NET,
  Java, Ruby, PHP, Swift, Godot, Unity, C/C++, shell) and the **ratchet**: a newly fitted linter or
  type checker judges only the files a change touches, so it is green on day one and can only get
  stricter, with the count of pre-existing problems written down once as "not yours".
- **The receipt.** Every build ends with the same six lines: what was built · does it work, and who
  actually proved it · what the machine checked · **shortcuts I took** (or "none") · **not proved**
  (or "nothing") · cost and log path. A shortcut is defined, not left to taste: a hardcoded value, a
  skipped case, a swallowed error, a loosened check, a test that asserts less than the behaviour, a
  TODO, or a fix whose only proof was a throwaway command. Each one also lands in the log's new
  `## Shortcuts and concessions` section, which git tracks, so the pile stays visible months later.
- **`council changed`.** A new helper verb: `council changed --glob '*.py' -- ruff check` runs a tool
  over just the files this change touches — committed on this branch, staged, unstaged and brand new,
  so it sees the code the council just wrote before any commit — and exits 0 when nothing matched.
  It is how a newly fitted check stays green on day one, and it replaces the fragile
  `git diff | xargs` pipeline: no pipe to break a config row, paths with spaces intact, deleted files
  dropped, `--each` for tools that read only their first argument.
- **Every fix leaves a test behind.** Before-evidence is now a test in the project's own suite
  whenever there is a runner — a throwaway command only when there isn't, and then it is named as
  such. `council check` reads every before/after verdict on disk and reports, per task, whether the
  before-check really failed, whether the after-check really passed, and whether the command names a
  test the project now tracks — a real test file, not just any path the command names, and one the
  build wrote counts before it is committed. Verdicts: `ok`, `BEFORE-PASSED` (the before-check never
  failed), `AFTER-FAILED`, `DIFFERENT-COMMAND` (the after-check wasn't the before-check),
  `NO-BEFORE`, `NO-AFTER` — and `NO PROOF` for a build that recorded none at all. The converge table
  gains a **Proof** column.

### Changed

- **`council gate --all` never reports success when nothing ran.** With no gates configured, no gate
  at the requested stage, or every gate skipped, it prints `NOTHING WAS CHECKED` and exits 4 (it used
  to print "no gates configured" and exit 0 — so every report on such a project read clean while
  nothing was checked). Its verdict line now names the numbers and the failures:
  `gates: 3 ran — 2 pass, 1 FAIL (lint, not mandatory) · 1 skipped`.
- **`council doctor`** treats a config with no gates as an error, not a warning — unless the config
  carries `guardrails: declined <date>`, which council-init writes when the offer is refused, and
  which demotes it to one warning.
- **A red baseline is no longer waved through.** council-implement asks one numbered question before
  task 1 when the gates exit 4 or a mandatory gate is already red, records the answer in the user's
  own words with its date, and repeats exactly one line in every receipt until it goes green.
- **`council run close`** warns when a build log has no `## Shortcuts and concessions` section.
- The verifier is handed the governing principle's own text, so the principle is checked rather than
  cited.

### Fixed

- **The permission rules council-init offers no longer allowlist every command on the machine.**
  `Bash(council *)` covered `council gate <name> -- '<any command>'`, which runs through `bash -c`;
  the offer is now a list of the bookkeeping subcommands, and the two verbs that run what they are
  given — `council gate` and `council changed` — keep asking every time. The offer now carries `Edit(.council/**)` plus the
  home's real absolute path, because the council home belongs to the **main** checkout — so from a
  linked worktree or a subdirectory a relative rule misses it. A council-init refresh reads
  `.claude/settings.local.json` and offers to replace an old blanket rule.
- **`council gate --all` counts a skipped required gate**, so "all pass · 2 skipped" can no longer
  hide a suite that never ran; a malformed Gates row is reported at every stage rather than vanishing
  under `--at`; a gate whose Run-at cell is empty is named instead of being dropped in silence; a
  check that ran but matched no files reads `pass — but nothing to check (0 files matched)` and is
  counted separately in the verdict line; and gate names with spaces stay whole in the FAIL list.

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
