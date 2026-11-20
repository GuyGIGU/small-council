# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **The post-game runs on the new path.** `/council-postgame` ("did we build what I asked?") is one page, like the review: the reader and the runner each check every part of your original request, one against the code and one by running it in a scratch copy, and the main session checks each verdict before you see it. The report and the next tasks council-implement builds from are unchanged. It costs about 500k tokens, as a review does (it was about 100–180k with one checker). Finish or pause an open post-game run before updating. D68, on the owner's word; built before any test of it.
- **A small request through `/council` is two agents, not four.** One part, one existing way and
  nothing hard to undo: the main session writes the design and reads the change against the book
  itself; one builder builds it and the runner proves it. A bug underneath, a real choice or
  anything hard to undo puts the designer and the reader back (D67).
- **A build keeps the book's design page true.** At the end of a build, the lines the build made
  untrue are corrected (in the project's own architecture file when the book uses one), and the
  report says what changed. `/council-health` checks a page's age before calling a difference
  drift (D67).
- **`council doctor` checks the book.** It warns, each with its fix, when the config has no book
  section (set up before 2.0: run a `council-init` refresh), when a page the book names is missing,
  when there is no design or stack page yet, and when the design page passes 120 lines or the stack
  page 60. Warnings only: a run still goes.

### Fixed
- **`council state restore=backup` is refused in a project that has git**, so a build can no longer
  start without its restore point; the refusal names `council restore point`.
- **A build writes its PR text again.** The 2.0.0 build page dropped the step that writes
  `<run>/pr-body.md`, so the step that shows it to you had nothing to show.
- The undo is now tested for a file the build turned into a folder, and the reverse; both come
  back. An ignored file inside such a folder is removed with it.

## [2.0.0] — 2026-11-19

**In short:** the rest of redesign 2.0, built on the owner's word before each stage's own test.
Your project keeps a short book every agent reads first; plan and research are a designer that
looks underneath before anything is built; a build leaves a restore point and ends with the reader
and the runner; `/council` runs the whole loop from one request, and `/council-health` shows where
the project drifted from its book.

### Before you update
- **Finish or pause any open council run first.** A plan, research or build run opened on 1.3.0
  follows its old page; close it paused (`council run close --status paused`) and start again
  after updating.
- **None of stages 2 to 5 has had its test yet** (redesign 2.0, section 12). Each stage is one
  commit, but each builds on the ones before it, so they can only be taken back newest first
  (stage 5, then 4, then 3, then 2), never one from the middle alone.
- **Then run `/council-init` once in each project (a refresh)**, so the project's book exists.
  Until you do, every brief shows the book's pages as not written yet, and `/council-health` has
  nothing to measure the project against.
- **A build now needs its restore point.** A build run opened on 1.3.0 and resumed after updating
  is stopped at the start of its build until it takes one (`council restore point`).

### Stage 2: the book
Built on the owner's word, 2026-11-19, before the stage's test (redesign 2.0, section 12), which is still owed.
- **Your project keeps a book every agent reads first** (D52): a design page (its parts, who owns
  each folder, the one way each job is done, where new code goes; two pages at most), a stack page
  (what it is built with and why; one page at most), the decisions log, and known problems. Setup
  writes them, or uses the project's own file where there is one and records its path under the
  config's new `## Book` section, so nothing is kept twice. With no such file the pages live in
  `.council/`. `council book` shows where each page is.
- **Setup asks you why** each part of the stack was chosen when no record says; a reason you don't
  give is written `not recorded`, never made up.
- **Every rule in the book carries its reason and its date**, and a line goes in only if leaving it
  out would change what an agent does.
- **A review checks the change against the book**: its reader reports a broken rule or decision, a
  second way of doing a job, and anything the change brings in that the stack page doesn't list.
- **What a review notes for later is kept** (D55): every item below the worth bar goes into known
  problems instead of being dropped (`council book note`), and when you say "stop raising this kind
  of thing" it is written there in your words (`council book waive`). Reviews read the file and
  don't raise either again.
- **The stack is your decision** (D54): a builder that would add a library, swap a tool or bring in
  a second language stops and asks you; a verifier rejects a change that does it without your word.
- **Your decisions stay where you keep them** (D53, superseding D28 in part): a project's own
  decisions log is read in place and no longer copied into the council's memory; without one,
  decisions stay in memory as before.
- **Helper:** `council book`, `council book note "<line>"` and `council book waive "<your words>"`;
  `council run open council-review` lists the book in the review's brief, and `council context build`
  names it on the first line of a task's orders. `council doctor permissions` now offers
  `Bash(council book:*)`.

### Stage 3: the build loop
Built on the owner's word, 2026-11-19, before the stage's test (redesign 2.0, section 12), which is still owed.
- **Every build can be undone** (D57): before it changes anything, the build takes a restore point,
  a saved copy of every file as it was, your unsaved work included, without moving anything. The
  report's last line, **Undo**, says in one sentence how to take the whole build back; nothing is
  undone unless you say so. `council restore show` prints the exact steps. The undo covers the
  files in your project folder that git keeps or could keep. It does not cover files git is told
  to ignore (such as `.env` or build output), the council's own `.council/` folder, or anything
  outside the project folder (a database, installed packages): those stay as the build left them.
- **One page for each builder** (D56): a builder now reads one page of rules instead of four
  references, and gets its task from the same one command as before.
- **A build is one page for the main session too** (D56): restore point, the project's checks before
  the first change, one fresh builder per task with the checks after each, then the check at the end,
  one fix round, the report, and the book updated. It loads about a third of what it did.
- **The check at the end is the review's pair** (D56, replacing build tiers and the converge
  verifier): a reader compares the whole change with the plan's behaviour lines and the book, and a
  runner runs the old and the new version side by side. Neither reads the builders' own reports.
  For each behaviour line the runner is asked to break the behaviour on purpose and show that its
  test catches it; a test that would not catch it is reported to you.
- **A bug under the work stops it first, and you choose** (D59): when the code a task rests on is
  wrong, the build shows it by a run and brings you a recommendation with three answers: fix it
  first, build anyway and note it, or stop. After a fix the original task goes on without asking you
  again.
- **The same report after every build** (D58): Works now (each behaviour line and how it was shown,
  with a before and after picture of a change you can see, where the session can start the
  project), Does not work, Your
  decisions, Not proved, Noted for later (also kept in known problems), Cost against the estimate,
  and Undo. A builder's own report is shorter: its fixed head and one line per thing it noticed.
- **Helper:** `council restore point` and `council restore show`; `council run open
  council-implement` now writes the build's plan with the reader and the runner, and their brief.

### Stage 4: the design step
Built on the owner's word, 2026-11-19, before the stage's test (redesign 2.0, section 12), which is still owed; its pass bar is not set yet.
- **A plan starts by saying back what you asked for** (D60): your request is written as lines you
  can check without reading code ("when a manager exports the report, a CSV downloads"). At most
  one question comes back to you, with the answer the council recommends. Those lines become what
  each task must do and what the build's tests prove.
- **One designer looks underneath before anything is planned** (D60): it reads the project's book
  and the code under your request, and says where the work fits and which existing way it extends,
  anything broken that the work would rest on (shown by running it, never argued), and any real
  choice for you. The panel of experts is no longer sent on plans or research; an expert's page is
  handed to the designer to read when the work touches something sensitive (who may see what,
  losing data, secrets, a public interface).
- **Your decisions come as consequences** (D62): each says what happens if you decide nothing, the
  recommendation first, and whether it can be undone.
- **A choice that is hard to undo gets two designs made apart** (D61): the stack of a new project, a
  data format, a public interface or a migration gets a second designer that never sees the first
  one's work. You see both side by side, where they agree, and the recommendation. A small request
  gets a three-line design and goes straight on.
- **A bug the request rests on is raised before planning on top of it**, with the same three
  answers a build gives: fix it first (the plan's first task, then the rest goes on), build anyway
  and note it, or stop. Anything else found goes into known problems.
- **Research is the designer on a question** (D60): an answer checked against the code, its
  confidence, your decisions as consequences, and no build.
- **A new project starts with its stack** (D63): setup on a project with no code asks what you want
  to build, two designers propose a stack apart (what each choice gives and costs), and your choice
  is written to the decisions log and the stack page.
- **Plan and research are one page each** (D60): each loads about a fifth of what it did.
- **Helper:** `council run open council-plan` and `council run open council-research` now write the
  run's plan with the designer (a second one ready to add) and the designer's brief.

### Stage 5: /council and /council-health
Built on the owner's word, 2026-11-19, before the stage's test (redesign 2.0, section 12), which is still owed.
- **`/council` does the whole job from one request** (D64): say what you want in your own words.
  It writes your request back as lines you can check, looks at the code underneath, brings you
  only the decisions that need you (as consequences), then builds it one task at a time with a
  restore point and the project's checks, has the reader and the runner check the whole change,
  fixes what they find once, and gives you one report with its undo line. The council picks how
  deep to go from the work; you never pick a size. A small request goes straight through to the
  one question before the build.
- **One estimate, one question before anything is built, one report** (D64): the cost of the whole
  job is shown before any agent starts. Before the build starts you are always asked once, in one
  message: the lines it will build, the branch, and the cost ("Build these, on <branch>? About N
  tokens, M minutes."). The report's cost is the whole job's.
- **`/council-health` says where the project has drifted from its book** (D65): one agent reads
  the whole project against its design page, stack page, decisions and known problems. You get at
  most five refactors worth doing, each with what it costs, why (what goes wrong if nothing is
  done) and whether it can be undone, each checked against the code first. Everything else goes
  into known problems, so it is kept but not shown twice. Nothing is built; say yes to a proposal
  and `/council-implement` builds it.
- **Helper:** `council run open council-health` writes the health pass's plan and its brief (the
  review's, with a health block); `council run open council` says the whole job is a plan run then
  a build run, and opens nothing.

### Changed

- **`/council` always asks you once before it builds**, even for a small request with nothing to
  decide: you see what will be built, on which branch, and what it costs, and nothing is built
  until you answer. It replaces the branch question, so it is still one question.
- **A build does not start without its restore point.** The helper refuses to begin building until
  the point is taken, so every build can be undone. A project outside git records that you chose
  the backup copy instead (`council state restore=backup`).
- **Fewer permission prompts:** `council restore` joins the commands council-init offers to allow,
  so taking and showing a restore point no longer asks each time. `council doctor` names it for a
  project set up before.

### Fixed

- **The undo now works in the cases it failed:** after the build switched to a new branch and left
  changes unsaved; on a new project with no saved history yet; a file you had deleted before the
  build no longer comes back; your own unsaved edits to the council's files, and the notes the build
  added there, are kept. When git cannot read the files, `council restore show` now says so instead
  of saying there is nothing to undo, and the point no longer claims unsaved work on a clean project
  that keeps its council files in git.
- **The check at the end of a build looks only at what the build changed.** Your own unsaved edits
  from before the build were being checked as if the build had made them.
- **A build's closing check no longer fails** on line numbers the fix round had moved.
- **After the conversation is compacted,** a session carrying on a plan, build, research, review or
  health run is told to re-read the right part of that mode's own page, not the old shared method.
- **A second health check on the same day** is saved beside the first instead of replacing it.
- **The book:** a page named with a note after it ("docs/arch.md — adopted") is found; a known
  problem written over several lines is kept as one line and still recognised when said again.
- **A finished review no longer fails its own closing check.** Since 1.3.0 the close's audit still
  asked a review for three stages it no longer has (assign, brief, collect) and reported a FAIL on
  every review. It now reads each one-page mode's stages from the one place that defines them.

## [1.3.0] — 2026-11-18

**In short:** a review is now two agents working at once — one reads the change, one runs it — and
you see its first checked findings in about 8 minutes, each in terms of what happens and what it
costs, with a recommendation.

### Before you update
- **A review now runs a reader and a runner.** The expert roster is not used by a review any more:
  no seat, card or catalogue page. Plan, research, post-game and build still use the roster.
- **A review opened on 1.2.0 can be finished on 1.2.0's page only.** Finish it before you update,
  or close it paused (`council run close --status paused`) and start a new review after updating.

### Changed
- **One page for a review** (D47, superseding D46). `/council-review` reads only its own page,
  `skills/council-review/SKILL.md`: the commands in order and the rules they need, under 16,000
  bytes (the method a review read before was under 50,000). It no longer loads context-core or the
  stage doctrine.
- **Two fixed agents** (D48, superseding D14 and D15 for reviews, and D43 in part). The reader traces
  each changed function to its callers and checks what the change's own record says against what the
  code does. The runner clones the project into the run's scratch folder, runs its checks on the old
  and the new version at once, and probes what changed. Their role texts are the ones measured in the
  redesign's comparison, word for word. A project with no council still gets the quick setup first,
  only to make its folder; the review reads none of its roster, and still offers `/council-init` at
  the end.
- **The main session checks each serious finding itself** (D49, superseding D5 in part). It opens
  the cited code before showing a finding and records its verdict in `<run>/verify-self.md`, labelled
  self-checked. A finding on a protected subject (authorization, data loss, injection, secrets,
  concurrency or ordering, public contracts) also gets a blind verifier, whose verdict wins.
- **What you see.** The reader's serious findings appear in chat as soon as it returns, the runner's
  when it does. The report has the same shape every time: Does not work, Your decisions, Not proved,
  Noted for later (five lines at most), and the cost against the estimate. An item reaches you only
  if you would act or decide on it; no code, no bare severity labels, no internal ids.
- **The estimate says time as well as tokens**: about 500k tokens, first findings in about 8 minutes,
  the whole review in the project's measured checks time plus about 8 (about 20 minutes until the
  checks have been timed once).
- **Both agents run on the session's model** (D51, superseding D37 in part): a review's plan gives
  them no model row, `- models: review=` no longer applies to a review, and council-init no longer
  proposes a lower model for it.
- **A review no longer proposes memory entries at its end.** What it finds and you don't act on is
  under Noted for later; the project's own record of known problems comes with the next stage.
  Setup does not time the checks yet: the first review's runner does.
- **A worker may take 100 turns**, up from 60 (finish its file by about turn 75), and may run the
  project's checks in a `git clone` under the run's scratch folder when its brief allows it — never
  in the project itself. A verifier stays at 60.

### Helper
- **`council run open council-review`** writes the review's fixed plan and its brief from
  `references/templates/run-plan-review.tsv` and `review-brief.md`, filling in the run, its folder,
  the code root and the council home. A missing template is a refusal.
- **A review's stages** (D50, superseding D8 in part) are convene, prepare, work, judge, challenge,
  deliver and learn; assign, brief and collect are no longer required. A review run is still opened,
  budgeted, reported and closed, and can't close complete before Deliver. Its method load is its one
  page, and `council run close` says so.
- **`council evidence check` accepts the main session's own check on a review** at any verification
  level; a verifier's row still outranks it.
- **`council gates timed <minutes>`** records how long the project's checks take, as the config line
  `- checks take: <n> min (measured <date>)`; the next review's estimate uses it. `council gates`
  prints the line last when there is one.

### Decisions
- D47 to D51, on the owner's word (redesign 2.0, stage 1). D5, D8, D14, D15, D37, D43 and D46 are
  marked superseded, in whole or in part, in `docs/decisions.md`.

### For contributors
- A proposal for a redesign, built on a measured comparison of the council's review with plain
  reviewers: [`docs/design/redesign-2.0.md`](docs/design/redesign-2.0.md). Its stage 1 is this
  release; the rest is not decided.
- The redesign proposal records Claude Code's built-in `/code-review` on the same two changes: it
  found 4 of the 10 known defects against the reader's 8, so the proposal keeps its own reader.

## [1.2.0] — 2026-11-18

**In short:** an install holds only what runs (about 2 MB, not the whole repository), a review reads
less before it starts, and three commands the method did not need are gone.

### Before you update
- **The install source changed.** The plugin now installs from the repository's `release` branch.
  Run `claude plugin update small-council@small-council` and start a new session. If the update
  finds nothing, remove and add the marketplace again: `claude plugin marketplace remove
  small-council`, `claude plugin marketplace add GuyGIGU/small-council`, `claude plugin install
  small-council@small-council`.
- **Three commands are gone.** Each is refused with what to do instead, so a script or a habit that
  still calls one stops with a clear line.
- A run opened on 1.1.0 can be finished on 1.2.0.

### Removed
- **`council route recommend`** (supersedes D31 through D44). The Chair sizes a run from the size
  limits, the roster and the config's estimates: agents × the estimate for each, plus about 20k for
  itself. No command prints a cost figure. The agent cap still counts every agent.
- **`council ledger advice`.** `council ledger [N]` stays, and gains two columns, `judged` and
  `counted`: the two facts the roster bar needs (3 judged runs, 15 items, at most 5 from any one
  run). The table weighs nothing; the Chair does, and the user decides.
- **`council evidence show`.** `claims.jsonl` in the run folder is the index; read it.

### Changed
- **`council evidence check` builds the claim index itself** (D44), and so do `council memory
  propose` and the close of a complete run. No one runs `council evidence build` first to make
  another command work. When the index can't be saved, the check still gives its verdict and says in
  one line which file or folder to make writable.
- **What ships is the `release` branch** (D45): the skills, agents, hooks, references, helper and
  licence files, about 250 files and 2 MB. The tests, evals and docs stay in the repository. One
  script builds the tree, checks it stands alone and publishes it, and it refuses a version that is
  not newer than the one published.
- **A review loads less** (D46, superseding D13's figure only): the method a review reads before it
  touches the project went from 56,666 bytes to under 50,000. Nothing was dropped: rules for other
  modes, for resuming a run and for the quick setup moved to references the method names at the
  moment they are needed (`references/run/workflow.md`, `resume.md`, `quick-setup.md`). The three
  agent contracts are a little shorter too.
- **Session start names `references/run/resume.md`** wherever a run is to be carried on, so the
  rules for a paused or interrupted run are one step away.
- `council status` and the closing card name `council evidence check` when the claim index is out of
  date.
- `council doctor` on a bad `- estimates:` or `- estimate per worker:` line says what it costs: the
  Chair can't price a run from it.

### Fixed
- Re-closing a complete run that had no saved audit built the claim index after the audit, so the
  audit could call a current index out of date. Cause: the two steps ran in the wrong order.
- With the route gone, the Chair's own share of about 20k was left out of the estimate, so a run on
  budget read as over it. Cause: the route had added that share and nothing else did.

## [1.1.0] — 2026-11-18

**In short:** a first review needs no setup, the full setup is mostly one command, and seat cards are
written when a seat is first used.

### New
- **A first review with no setup (D43).** `/council-review` in a project with no council does a quick
  setup and starts: the catalog's 14 seats as it names them, no map, kept on your machine. It says
  once that no check was probed, so nothing in that review is checked by machine, and offers
  `/council-init` in one line at the end. Plan, build and research still ask for the full setup
  first, because they lean on the map and the probed checks.
- **`council init detect`** reads the project and prints its stack, the checks its own manifests and
  scripts show (each with a ready probe command and a broken twin), and the catalog's seats with the
  surface the file list shows. It writes nothing and invents no command.
- **`council init scaffold`** writes the config, the memory file, the map's skeleton and
  `.gitignore` from the templates, with the Gates table filled from the probes that ran in the setup
  run. It never overwrites a file that exists. `--quick` is the setup a first review uses. On a
  quick setup being made full, it fills only the Gates rows that still read `✗ not probed`.
- A check that runs and fails on real problems (a linter that finds a real error) is recorded as a
  working check that fails today, not as one that can't run.

### Changed
- **Seat cards on demand.** Setup writes no cards. A run writes the card of each selected seat that
  has none, before it briefs that seat. `council doctor` no longer warns about a seat with no card.
- `/council-init` runs on the two commands above, so the Chair writes only the judgment: the roster,
  the stack section and the map's prose.
- With no council in a project, `council run status`, `council run open` and `council doctor` name
  the right next step for each mode. On a quick setup, a missing map is no longer something to write
  by hand: the full setup builds it.

### Fixed
- `council sharing just-me` and `sharing team` name each file git tracks that they changed, say the
  change is uncommitted, and give the two next steps: commit it, or put it back.
- `council run audit` counts only council agents (worker, verifier, builder) as dispatches. A
  one-off general agent no longer fails "size and cost before the first dispatch" or the status
  card step.
- `council collect` finds a seat's card when it runs from a subfolder. A relative card path in a
  brief was read from the folder the command ran in; it is now read from the project's root.
- `council run export` keeps an agent's type only for the council's own agents, by the agent
  gate's list. It had a rule of its own.
- A very small project no longer reads as having no language. `council init detect` and a quick
  setup's Stack section name the languages seen with their file counts. The stored fingerprint
  line is unchanged, so no project reports a changed stack.
- The setup files no longer carry the template's placeholder lines under `## Hard rules` and
  `## Notes`: both are written empty, and the full setup lists Hard rules as left for the Chair.
- Making a quick setup full fills each check's row by the table's column names. A table with a
  column of the project's own, or columns in another order, was filled wrong; a table that lacks
  a needed column is now left as it is, and the command says which column to add.

### For contributors
- A new `setup` group in `evals/run_cli.py` (52 scenarios) and unit tests for the detection.

## [1.0.0] — 2026-11-17

**In short:** a build now hands each task to a fresh builder agent and checks its work against its
diff; the helper is Python, and Python 3.8 or newer is now required; five views nobody used, and
context packs, are gone.

### Before you update
- **Install Python 3.8 or newer first, on every machine.** Every `council` command and every hook
  now runs in Python. Without it each command refuses and says how to get it, and the hooks stay
  silent. Check `python --version` (or `python3 --version`); on Windows, in Git Bash, and not the
  Microsoft Store stub.
- **Then update the plugin, restart the session, and run `council doctor`.** It names the
  permission rules your project lacks.
- **Then run `/council-init` once in each project (a refresh).** It adds the map's new
  `## One way per job` table, proposes the decisions your project already wrote down, offers the
  new permission rules (`council context`, `council tree`, `council patch`) and brings your config
  up to date. Your config, memory, map and records are kept. Without it everything still works,
  but plans skip the owner check and each builder asks permission for its commands.
- **Config lines that changed.** `- context packs:` does nothing now: delete it. `- build tier:
  full` used to mean "a verifier per task"; now it means only "a before/after proof for every
  task", and a build gets one verifier at the end. To keep a verifier per task, add
  `- checking: per task`. Every new line below is optional: a missing line keeps the old behaviour,
  except checking.
- **A build left open in 0.23:** carry it on with `council run resume --run <folder>`, then
  `council state input=<the plan's path>`; the Chair builds it itself. Nothing on disk needs
  migrating.

### New
- **A builder agent per task.** `/council-implement` sends each task of a plan to a fresh
  `council-builder` agent with a clean window, one at a time. The builder reads its orders from
  `council context build task-<n>`, writes that task's code and a short report, and answers in one
  line. A small job (Solo) is still built by the main session.
- **Every round is checked against its diff.** `council patch save` refuses a round whose report
  doesn't name its cause, or that removes a test or assertion without saying so, and lists files
  outside the task and workaround signs (retries, sleeps, catch-alls, skipped tests, TODO, hack) for
  the verifier. `council patch show`, `apply` and `revert` show, re-apply or take off any saved round.
- **Revert check.** `council check` re-runs each "it failed before, passes after" proof with the
  change taken off, in a scratch copy; a check that still passes is marked `REVERT-PASSED` (broken).
- **The receipt's machine lines come from the helper.** `Checked by machine:`, `Not proved:` and
  `Your decisions:` are printed by `council check` and copied word for word.
- **Plans carry the request.** Each task quotes the part of your request it serves, names the
  existing way of doing the job it extends (or says it adds a new way, for your ruling), and lists
  the facts it rests on. `council tree` shows the request, its tasks, their proofs and stops.
- **A builder can stop and ask.** `NEEDS: <question>` and `NEEDS: fix <file:line>` are proper
  answers; the helper won't start that task, or one that depends on it, past an unresolved
  `NEEDS: fix` until you decide.
- **Decisions per task:** `council state decision="…" task=<n>`.
- **New settings,** all optional: `- checking: one per batch | per task`, `- open items: ask | fix
  now`, `- pushes: on | off | off until <date>` (a push freeze the Bash hook enforces), `- models:
  builder=, review=, verifier=` (a model per role; a verifier is never weaker than the builder it
  checks), `- estimates: review=, plan=, builder=, verifier=, converge=`, `- memory budget: <n> KB`,
  and an optional `Covers` column in the Gates table.
- **Gates aren't rerun for nothing:** a green gate on the same files, or on the same files under
  its `Covers` paths, is reused and reported as "not rerun".
- `council memory tidy`, `council map touch`, `council doctor hooks`, `council run export --anon`.
- **The council pane** (Claude Code 2.1.287 or later): a pane beside the chat shows each seat while
  a run is open, and a line above the prompt shows the stage and the spend. `/council-view` reopens
  it.
- `council run close` saves the run's audit as `<run>/audit.md`, flags an agent with no token
  figure, and records the method's size beside the Chair's tokens.
- `council doctor permissions` prints the permission rules to paste; `council doctor` names the ones
  a project lacks. `/council-init` offers that same list.
- `council patch hold <n>` sets a stopped builder's unsaved edits aside, and
  `council patch apply <n> --held` puts them back for the next builder.

### Changed
- **One verifier per build by default** (`- checking: one per batch`): a build is checked by its
  gates task by task and by one verifier at the end; a second verifier needs your go. Set
  `- checking: per task` for a verifier per task.
- The verifier judges each task's Done-when and nothing wider; what else it notices goes under
  `Noticed`.
- Rulings reach you as one question at the end; a build shows the PR text before asking about the
  PR, and checks first whether the base branch moved.
- The SessionStart banner says how stale the map is for each top-level folder.
- `council help`, a bare `council` and `-h` need Python too.
- Files the helper rewrites use LF line endings on every OS.

### Removed
- `council history`, `council tune`, `council outcomes`, `council tui` and `council pet` (unused).
  Token estimates are now set by hand in `council.config.md`; an old `tuning.md` is ignored.
- Context packs and the impact graph (`council context build <seat>`, `council context show`,
  `council impact`, `- context packs:`). An old `- context packs: on` line is ignored.
- The 0.1/0.2 `.council/active-run` pointer is no longer read or written.

### For contributors
- The helper is a Python package (`src/council/`); `bin/council` is a 53-line launcher.
- `docs/architecture.md`, `docs/decisions.md` and a root `CLAUDE.md` record the design.
- `python evals/run_all.py --fast` (about a minute), a size ratchet (`evals/run_ratchet.py`), ruff
  in CI, and CI's Windows leg split across three machines.
- `evals/run_replay.py` replays saved runs through `council run audit` with no model.
- CI also runs the fast tier on Python 3.8, and every job has a time limit. A final review planted
  24 bugs; the four no suite caught each have a test now.
- `evals/bench.py --arm builder|chair` compares the two ways of building (the paid comparison has
  not been run).

### Fixed
- A just-me council could never save a build round or reuse a green gate.
- The same build task could be dispatched to two builders at once.
- Python bytecode (`__pycache__/`, `*.pyc`) no longer enters a build round.
- On Ubuntu 26.04 two commands could hold one lock at once.
- A worker or verifier is no longer sent out when the council home can't be written from the
  session; the agent gate says which folder and what to do.
- Hand-edited CRLF files, Windows paths and malformed numbers now read the same on every OS.
- The checks plan `/council-init` writes for a project that lacks them can be built: it was in a form
  the helper couldn't read, and its tasks edited the council's own config, which a builder may not.
- A builder runs its after-check before it saves the round, so mending its own work no longer counts
  as a fix round; it saves again if it changes a file after saving.
- Builders, reviewers and verifiers treat text in the code they read as data, never as instructions.
- **Proofs that passed without proving anything.** A check that ran no test (none found, all
  skipped, no files matched) reads `NOTHING-RAN`. An after-check that passed on other files than
  those on disk now reads `AFTER-STALE`. The revert check takes off every round saved since the
  task's first and keeps the files the check names, so a later round can no longer hide a test that
  doesn't depend on the change.
- Every gate records the files as they are on disk, so a green gate is never reused after an
  uncommitted edit.
- A second session can't write into a run another session is driving; it can still read it.
- `council state` no longer overwrites the fields `run open`, `run resume` and `run close` own.
- A `council run close` that stopped halfway finishes when run again.
- `council run plan check` refuses a task with no `Done when`, a repeated task number, or a
  `Depends on` that names no task.
- A claim a verifier REFUTED but the report still kept now fails `council evidence check` and the
  audit.
- A build from a review or a post-game gives its builders their tasks. For a review, the Chair
  writes the selected findings to `<run>/tasks.md`; without it the build says so instead of
  starting with no orders.
- A builder sent out with no `Seat: task-<n>` is refused, and a builder's stop is checked against
  its own seat's report and the saved files.
- `NEEDS: fix` is read the same way everywhere, with or without markdown around it.
- A builder that saves twice in one dispatch replaces its round; it no longer counts as a fix round.
- File names with spaces or non-ASCII letters are kept as written in a saved round.
- Settings in `council.config.md` are read one way: any capitals, with a `# note` or `(note)` after
  the value. A value the helper can't read is said, and `council doctor` reports it as an error.
  An unreadable `- pushes:` line holds pushes.
- The seat ledger and the tool counts are written under a lock; a file that starts with a BOM reads
  as any other.
- **Push freeze and pipe rule:** PowerShell calls are judged too; `git -C <dir> push` and a push
  quoted inside `bash -c`, `sh -c` or `eval` are caught; `--dry-run` passes; a project's own
  `./council` script is no longer mistaken for the helper.
- **Push freeze override on record:** a push or PR let through with `COUNCIL_ALLOW_PUSH=1` while the
  freeze holds leaves a `run.push_allowed` event in the open run, and `council run audit` shows it
  as a warning. Before, nothing recorded that the override was used.
- **Hooks are faster where there is no council:** the turn-end hook takes about half the time and
  the agent gate about a third.
- With no Python, session start says so in one line instead of staying silent.
- The audit counts only the run's own open-to-close window, says "not checked" when the transcript
  doesn't hold the run, and warns when the agent cap was passed with no message from the user.
- `council run export --anon` no longer keeps unredacted status lines from tool results.
- `council memory accept`, `reject` and `propose` refusals exit 2 and name the next step.
- A post-game's status card reads its own verdict table.
- The SessionStart banner says when the map was built on another line of history.
- Closing an abandoned run again finishes what a stopped close left in the seat ledger.

## [0.23.0] — 2026-10-22

**TL;DR:** the Chair's own tokens are recorded at close, plus three fixes from real runs.

### Added
- The Chair's own tokens are recorded: `council run close` reads the session transcripts for how much the Chair's context grew while the run was open (the measure an agent's figure uses), says the figure, records it as an event, and the card shows it beside the agents' figures. A resume now records the session it came from.

### Fixed
- `council run open --code-root <relative>` stores the root as an absolute path, so a gate run once the Chair's cwd is a worktree still enters it (every gate used to exit 97); a folder that does not exist is refused.
- `council run audit` no longer fails the claim index for a cut claim a verifier CONFIRMED when synthesis.md says why it stays cut (`still-cut:`), the way `council evidence check` already reads it; and it counts a MISCITED verdict as true, as evidence check does.

### Changed
- council-implement's verifier brief lists the task's risk class as the plan marks it, so a risky task without its proof pair is refused under the light tier.

## [0.22.0] — 2026-10-18

**TL;DR:** a light build tier (the default) that pairs and verifies only the risky tasks, four
helper fixes a real run on the Mac asked for (slug task ids, the diagnosis role, `council gate
--wait`, refusals that name the next command), a stated fallback when the harness blocks a worker's
write, and a finish line for builds: a plan's last task plus one fix round.

### Fixed
- `council gate before-<id>` / `after-<id> --proof …` take a builder's slug as the task id, not only a number; `council check` already paired them by name.
- `council run plan check` accepts the role `diagnosis` that council-implement tells the Chair to plan for a stuck task; it counts as a worker's agent run.
- A repeated seat report with no agent id, and a slug closed by `council correct`, now say which command to run next instead of only refusing.

### Added
- `council gate --wait <name>` queues behind a running gate call (20 minutes, or `--wait=<seconds>`) instead of refusing; the refusal names the flag.
- A build tier: `- build tier: light` (the default) or `full` in the config. build-proof.md's Tiers section says what each requires — light pairs and verifies risky tasks one by one and batches the rest — council-implement reads it, and `council check` names the tier it read in its summary and in check.md. The implement loop also gains "rulings, not stalls" with a stop list, a `Ruling:` log line, and a finish line: a build ends at its plan's last task plus one fix round.
- Workers and verifiers the harness will not let write hand their file back under `UNWRITTEN <path>`, and the Chair saves it with `note="saved by the Chair"`.

## [0.21.0] — 2026-10-08

**TL;DR:** the rules a real run broke while they sat in prose are now enforced. A hook refuses
`council … | head/tail/grep`; a run can't open in a session whose hooks never ran; gates get a time
limit; council agents need an open run and a planned seat; a run can't close complete before Deliver,
skip a stage, or go Full without the user's recorded go. A build's receipt names what is left open, and
no commit or PR question comes while anything is.

### Added

- A Bash hook (`hooks/bash-gate.sh`) refuses a command that pipes the helper into head, tail or grep, because the pipe hides its exit status and refusals. Redirect the output to a file and read that. Quotes, heredocs, comments and anything it can't parse go through.
- `council run open` refuses in a session with no SessionStart mark, meaning the plugin was enabled or updated after the session started: restart the session. A session's first `council` command also marks it. `COUNCIL_ALLOW_NO_HOOKS=1` is the user's escape.
- SessionStart warns a session that sits in a linked worktree while an in-progress run's code is elsewhere.
- `council gate` has a time limit. It is the largest of 3× the gate's green baseline, the config's `- gate time limit:` and 120 s; a check given after `--` defaults to 9 minutes; `--timeout` overrides. A hang stops with exit 124, "TIMED OUT". `--invalid "<why>"` marks a red that proves nothing, and `council check` reads it as NO-PROOF-YET.
- The agent gate holds council-worker and council-verifier dispatches to the record. It refuses when no run is open, when the run is closed or paused, when the seat isn't planned, and on a build task's third check without a diagnosis or the user's go. Ordinary agents and Workflows are never judged.
- On a just-me council, `council check` in a build flags council ids in what the build added and in its PR body: `.council/`, run folders, `ruling n`, `verify-n`, AP/EC/D/F ids. It also notes a task proved only by run-folder scripts. council-implement drafts the PR body as `<run>/pr-body.md` before that check, and opens the PR from it.
- `council run close` prints every FAIL line of the run's audit.

### Changed

- `council run close --status complete` is refused before Deliver, and after a step back from Deliver until Deliver comes again. A run the user stops for the night closes `--status paused`. `council state status=complete` is refused: only the close sets it, so its checks and audit can't be stepped round.
- `council state phase=` refuses to pass over a stage the mode must enter unless `skip="<why>"` is given; the phase event records the reason.
- `council run plan check` refuses a Full plan until a decision of the user's since the run opened is on record.
- The first status card is owed once per run. The Stop hook sends the Chair back while it is due, and the audit judges the run's first dispatch.
- council-implement's receipt adds `Left open:`. No commit, push or PR question while anything is left open, and that question comes last, on its own.
- The run audit counts helper calls in loops, groups and `bash "$C" …`, and reads only each run's own part of a session that drove several.

### Fixed

- The marketplace manifest has a description, so `claude plugin validate . --strict` passes again; `scripts/quick_validate.py` checks for it.
- `council tui` and `council history` read a before-check that timed out, was marked invalid or never ran as no proof yet, as `council check` does, never as failed as planned.
- Stage 8 names `| grep` beside `| tail` and `| head` as a pipe that can swallow a refusal.

### Upgrade notes

- An open run at Full with no recorded decision is refused at its next seat or stage change: record the user's go with `council state decision="…"`.
- A run that never entered Deliver can't close complete. Walk it to Deliver, or close it `--status paused` or `--status abandoned`.

## [0.20.1] — 2026-10-05

**TL;DR:** a build's closing card now says how its final check went instead of "claim index out
of date", the request on the card is cut at a whole word, and the terminal view no longer draws
a build's deliberate first failures like real ones.

### Fixed

- A build run's closing card no longer says "Claim index out of date; verifier counts unknown": a build checks tasks, not claims. It reads the build log's final check instead ("Final check: 13 of 15 tasks met; 2 partly met") and lists each task left short under "Left for you".
- "What you asked" on the closing card ends on a whole word, then "…", instead of mid-word.
- `council tui` draws a build's before-check and a review fix's regress-check that failed first as "failed as planned", not with the failure mark.

### Changed

- Only review, plan and research runs (or a run with no recorded mode) expect a claim index, as the helper's close already ruled; a post-game's card now says "No claim verdicts recorded." instead of "out of date".

### Upgrade notes

- Nothing to do in your projects. The status JSON gains two keys (`claims.expected`, `closing.converge`); its schemas are unchanged.

## [0.20.0] — 2026-10-03

**TL;DR:** the council acts on the approval and instructions you already gave instead of asking
again, and a refactor can now be proved by showing the same checks pass before and after the change
(`--proof preserve`), while a fix still needs a check that fails first. Two new eval cases test these
judgment calls; they have not been run live yet.

### Changed

- Approval, current instructions and evidence-backed plan corrections have one shared contract in Convene; build-proof mode and semantic verification rules live in the build-proof reference rather than being repeated in each reader.
- Builders may correct a plan's approach when concrete evidence supports a local change within the approved outcome, scope, contracts and budget; the log keeps the evidence and affected tasks. Changes to explicit user choices or scope still need a ruling.
- Refactors can declare `--proof preserve` on their before/after gates: the same relevant check must pass on both versions. `council check` labels this `preserved`; fixes and new behaviour retain failing-before/passing-after proof. The verifier checks the invariants and test assertions.
- Planning, research and implementation carry forward existing authorization and ask only about consequential gaps. A user's mid-build addition authorizes that addition within the approved budget.
- Council skill descriptions focus on selection; simple questions no longer match broad research or completion-audit descriptions.

### Fixed

- The build-judgment authorization grader catches quoted helper paths, helper variables and Git working-directory options; a separate artifact grader detects deployment even when command matching misses it.
- Preservation proof rejects blank or whitespace-only saved output and zero-test reports even when warning metadata is missing.
- History keeps preservation checks separate from before-checks that fail intentionally; saved gate verdicts and snapshot readers retain the declared proof mode.

### Added

- Judgment-only build and blind-verifier fixtures cover stale paths, superseded preferences, separate refactor/fix proof, protected choices, weak assertions and wrong before-failures. Free regressions execute the fixtures and helper; live agent judgment remains unvalidated until those cases run.

### Upgrade notes

- Nothing to do in your projects: no re-init, and the config template changed only in a comment.
- `approve without asking` now also covers a plain "go ahead" or "proceed" message, not only a slash command; Full size still needs an explicit go with its size and cost.
- `--proof` is optional: a before/after gate without it keeps the failing-before, passing-after proof, as before.

## [0.19.0] — 2026-10-02

**TL;DR:** two things. The council fixed its own open items, as its second real run (a plan, then
a build of 15 tasks, each checked by a blind verifier): the phone alert and the build's three-failure
stop no longer depend on the Chair remembering a step, a closed run stays closed, a run in a
worktree is found from anywhere, and two linters check every change. And a "just me" setup keeps
the council on your machine in a shared project, so teammates never have to see or use it. Ten
smaller fixes found after run 2 are in too, from two closes at once to the paid repair drill.

### Added

- A turn-end hook: when the Chair stops for you with no agent working, the run records that it waits on you, and the Chair is sent back once to alert your phone (`- notifications: off` turns it off).
- `council state decision="<your words>"` records a ruling or go-ahead in your words; the status card shows the latest.
- `council run events repair` mends an event file whose last line was cut off, keeping a byte copy.
- `council seat … tools=<n>` measures each agent's tool calls against the plan's budget.
- The run plan can name the Chair's own share of the estimate (`budget/run/chair-tokens`); agents are then compared with their share.
- CI runs ShellCheck and ruff on the files a change touches, on every OS, proved on a planted fault.
- Setup asks whether the council is the team's or just yours. On **just me**, git ignores `.council/` through its own exclude list (never committed or pushed), CLAUDE.md gets no Small Council note, and the config records `- sharing: just me`.
- `council sharing` shows who sees the council and what's left to do; `council sharing just-me` and `council sharing team` switch it, and also work on a council that's already set up.
- `council doctor` warns when a just-me council still shows up for the team: council files in git, the note in CLAUDE.md, or `.council/` not ignored.
- On just me, sessions are told to keep council runs, finding ids and `.council/` paths out of commit messages, PR text and shared docs, and specs save to `.council/specs/`.

### Changed

- In a build, `council gate` records each failed attempt itself; the three-failure stop no longer needs a typed `repair record`.
- A seat can't be marked done without its file; the seat-check hook sends back an empty, multi-line or file-less reply once.
- A closed run takes only what its close asks for (the deliverable, the request, a correction, the Chair's own record).
- Every stage change records that stage's next step; a completed close says once what the record has to tell you.
- Reminders are the last line a command prints, so a cut output keeps them.
- The method the Chair reads is shorter than before 0.18: each rule the helper now says is one pointer.

### Fixed

- Commands find the run this session drives from any working tree (`run open --code-root`).
- A state, seat or close call does all of its writes or none; a damaged event file refuses before anything changes.
- `council run audit` judges this run's real close, not a refused one or another run's.
- The status card says "no agent ran" and "dry runs only, no check yet", and no longer counts skipped seats.
- Memory lines in deep headings or tables, and an id used twice, are named instead of misread.
- The cost line compares agents' tokens with the agents' share ("about 18% over the agents' 80k share").
- A gate whose tool is missing reads "could not run (exit 127)"; `council doctor` names a slow gate at grounding.
- The plan check says each problem once.
- A review fix's red proof (`regress-<n>`) no longer reads as a failing check on the card.
- Two closes of one run at once: one goes through; the others say it is already closed, or are refused.
- A `closed:` line in a run's notes no longer reads as the run's close: a run's state is read by its header only.
- `council index` refuses a closed run before it writes anything.
- A decision keeps its quote marks and backslashes, and reads back exactly; the card shows the words as said.
- A Python tool that isn't installed (`python -m ruff` without ruff) reads "could not run", not FAIL.
- `council check` names a test kept in a test folder (`python evals/run_cli.py --block …`) as the saved test.
- `council check` reads a review fix's `regress-<n>` then `after-<n>` as that fix's proof, not as a task with nothing before it.
- The close's follow-up line is said once, not again at every later close while the record says the same.
- On a closed run, an agent id holding ":" can no longer pass the seat guard.
- The card reminders say to give the text if the card fails to render; the wait reminder says how a wait is cleared.
- The paid repair drill and its trace checker expect the attempts `council gate` records itself; the checker's self-test runs in the suite.

### Upgrade notes

- The new Stop hook runs at the end of every turn; it is silent outside a council run.
- A verifier's seat is done only with its file: a Workflow's verifiers write `verify-<n>-<letter>.md` in the run folder.
- "Just me" needs nothing: a council with no `- sharing:` line stays a team council, as before.

## [0.18.0] — 2026-10-01

**TL;DR:** the fixes from the first real run and the 2026-09-30 bug hunt. After a compaction the council
picks its own run back up, the agent limit and the build's three-failure stop hold, the checks stop
reporting wrong passes, and `council run audit` checks each finished run against the method.

### Changed

- The permission rules council-init offers now cover nine more helper commands the council runs (status, evidence, context, repair, impact, route, history, outcomes, version), so they stop asking each time; `council gate`, `changed`, `cap`, `tune` and `correct` still ask. A council-init refresh offers the new rules to projects already set up.

### Fixed

Four problems the first real run showed:

- The status card was never shown: showing it is now a numbered step at the first dispatch and at the close, and the helper reminds the Chair at both moments.
- Two copies of the checks could run at once and leave a test failure on record that never happened: a run now takes one `council gate` at a time, and a second one is refused before it writes anything.
- The status text said "A check is failing. A check failed." and, at the last stage, "Next: size the run and ask for the go-ahead": a failing check is now said once, and that opening step is no longer shown once the run has moved on.
- The Chair reached the helper only through a full path, which no permission rule can match: the method and the session-start note now say to call it as a plain `council <command>`, and why.

### Added

- `council run audit` checks a finished run against the method, item by item (pass, warn or FAIL): stages in order, agents recorded while they ran, one set of checks at a time, the deliverable, the claim index, the agent limit — and, from the session transcript (found by the run's session id, or given with `--transcript`), both status cards, the plain `council` call and helper output not cut off. The Chair runs it after every close.
- `council home rule` prints the permission rule for the council's folder in the form Claude Code matches (the one setup wrote on Windows never matched).

### Fixed — from the 2026-09-30 bug hunt

Runs and the agent limit:
- After a compaction, a run whose code is in a worktree is recognised as the session's own: Claude is told to reload the method and carry on, not to leave it alone.
- The agent limit counts each agent the moment it starts, so agents started together or recorded late no longer slip past the stop. A Workflow counts as one start until its agent count is recorded, then as all of them; agents recorded before the first counted start (a run resumed from an older version) count too.
- After your go past the limit, the extra agents can be added to the run plan; runs opened before limits existed only warn, never stop; a usage report recorded twice counts once.
- Two state updates at the same moment no longer lose one; an empty or misspelled stage name is refused.

Checks:
- A "changed files" check looks at everything the run covers, including work already committed on the main branch, and says which starting point it used.
- A check that passes without running a test, or a test check that prints nothing, reads "pass — but nothing ran" (a run that did run tests elsewhere in its output, such as cargo's doc-tests line, still passes plainly).
- Running all checks warns like running one: a pipe (unless the command sets pipefail), a last step that always succeeds, or a check that passes when its tool is missing; a required check with an empty command is named, not dropped.
- In a build, a failing check prints the line to record the attempt (a second check failing in the same task gets its own id), and after three recorded failures it refuses to run until your go (`council repair allow`) — the "stops after three failures" promise holds once attempts are recorded; unrecorded failures still don't count.
- Closing a run as complete warns when it never reached Deliver, a required check is red, or there is no deliverable or no verdicts.

Findings and the closing card:
- The claim index reads ordinary verifier tables and names any row it can't read instead of dropping it; a verifier whose table it can't read is sent back to fix it.
- A cut finding the verifier confirmed fails `council evidence check` and the run audit, instead of staying on record as cut unnoticed; "## Cut (…)" headings are read; a summary table after the verdict table is left alone.
- Plan runs can build their claim index (several rows per recommendation, the worst verdict counts), and Solo runs can pass the evidence check with the Chair's own recorded verdicts, shown as self-checked.
- The closing card's "Verified" line counts only what shipped and names each verdict; it no longer says "not verified" about items the Chair cut.

Setup, agents and the method:
- Setup runs open with a plan that fits setup, and setup proves each required check can fail; the health check no longer judges finished runs' plans.
- Workers and checkers are told their 60-step limit and checkers save as they go; one that runs out is resumed, not re-dispatched. `council collect` checks every seat file in `seats/`, a Workflow's too.
- The steps every run needs (a Solo Chair's own record, the phone alert, the pet on request) are where every run reads them; recording that Claude is waiting for your answer reminds it to send the alert.
- The session-start note and README say the helper runs in the Bash tool, not PowerShell; a run resumed by its `.council/runs/<name>` path works from a worktree.

Tests:
- A suite that couldn't find bash or git no longer reports a pass after checking nothing, and the full run fails any suite that ran no checks.

### Upgrade notes

- Nothing to do for open runs. A run opened before agent limits existed is never stopped at the cap; it only warns.
- A council-init refresh offers the wider permission rules, and `council home rule` prints the rule for the council's own folder.
- Runs opened from now on record agent starts in `agent-starts.tsv`; tools that read a run folder may see that file.

## [0.17.0] — 2026-09-29

**TL;DR:** memory rules wrapped over several lines now reach seats whole; mapping and survey seats can
optionally run on a cheaper model.

### Changed

- Optional, disabled-by-default model requests let mapping and survey workers use `sonnet` or `haiku`;
  Chair and verifier seats continue to inherit the session model.
- `council history` groups recorded tokens by planned model (once a run asks for one) and labels
  inherited models as unknown; tokens are not a money measure. History JSON advances to
  `council.history/4`.

### Fixed

- A memory rule or origin wrapped over several lines reached seats cut off after its first line; `council memory` now reads it whole.

### Upgrade notes

- Nothing to do. Model requests stay off until `- seat models: on` is set in `council.config.md`.
- Tools that read `council history --json` should expect `council.history/4`.

## [0.16.1] — 2026-09-29

**TL;DR:** a rare lost record, when two council calls record at the same moment, is fixed.

### Fixed

- Two council calls recording at the same moment could lose one record: the one waiting its turn crashed
  if the other finished at that instant. It now waits quietly, and every record is kept.

## [0.16.0] — 2026-09-29

**TL;DR:** a pumpkin-ghost desktop pet shows how a run is going; the card says whether new agents are
stopped or allowed on your go; the impact graph finds scripts' neighbours; CI takes half as long.

### Added

- `council pet`: a small pumpkin-ghost on your desktop that shows how the council run is going; ask the Chair to show the pet.
- The impact graph lists each changed file it can't read (shell, hooks, Markdown, config) as "not inspected", and its summary counts them.

### Changed

- The status card, text, `--line` and JSON (`usage.limit`) say whether new agents are stopped at the limit or allowed on your go.
- CI runs the free suites side by side (`evals/run_all.py`, the helper suite in groups): Windows takes
  about 15 min instead of 32, and every check still runs.

### Fixed

- The impact graph now finds scripts that import a file sitting next to them (medium confidence).

### Upgrade notes

- Nothing to do. `council status --json` gains a `usage.limit` block and `impact.tsv` gains
  `not-inspected` rows; neither schema version changes.
- On an open run at its limit, the card now reads "Stopped at the limit — waiting for your go", or
  "Your go allows up to N agent runs" once the go is recorded.

## [0.15.0] — 2026-09-29

**TL;DR:** runs stop at their agent limit until you say go, show spend against the estimate, end
with a closing card and can alert your phone; small asks skip the council.

### Added

- Opening a run warns when the configured project memory exceeds about 25 KB; the status card flags it too.
- `council outcomes` compares finding citations with later committed changes in each run's code root;
  history includes a conservative summary.
- A run at its agent cap or past its token ceiling now stops new agents until the user says go (`council cap allow`).

### Changed

- The always-loaded core instructions are shorter; the full helper command table lives in `references/helper-commands.md`.
- `council status --line` gives one short owner notification at a blocking question, stopped build,
  agent/token limit or completion; `- notifications: off` suppresses it.
- Closed runs now have a final status card, text view and JSON block for the filed request,
  deliverable, verifier counts, checks, spend, agent runs and owner follow-ups.
- The card, status text and close line compare known token use with the run estimate and optional owner ceiling.
- The agent cap counts agent runs, not seats: a Workflow seat declares how many agents it starts
  (`budget/<seat>/agent-runs`), and the plan check counts them.
- Reaching the cap, `council seat` tells the Chair to ask before starting more; passing it records
  `run.cap_passed`, and the status card flags it. The card shows each run's limit.
- Convene first asks whether the council is needed: a small, fully specified request is done
  directly, with no run (never on a protected subject, and never for a review or post-game).
- Small, same-kind parts share an agent: each agent of a Workflow takes a group of them, and a build
  verifies up to five small tasks of one kind together.

### Fixed

- Every token display rounds half up; bash progress and close lines use the same M form as Python.
- `council outcomes` no longer counts a line-ending-only change as a change at the cited lines.
- `council outcomes` counts lines inserted inside or right next to a cited span as a change there.
- `council outcomes` reads diffs the same whatever the user's colour, hunk-context or text-conversion settings.
- `council outcomes` and `council history` no longer crash on a diff byte the Windows code page can't decode.
- `council history` diffs each cited file once per run; `council tune` skips the comparison it never reads.
- The close line gives the estimate in the same units as the total (`~1.5M`, not `~1500k`).
- A run passing its cap, estimate or ceiling is recorded once, even when two seats finish together.

### Upgrade notes

- An open run already at or past its agent cap stops at its next agent too; `council cap` shows
  where it stands, and `council cap allow` records the user's go.
- A small, fully specified request may now be done directly, with no run; ask for the council to get one.

## [0.14.0] — 2026-09-28

**TL;DR:** chat status cards and exact run accounting, with missing figures left unknown.

### Added

- `council status [--widget | --json]` shows run progress; card and text need optional Python 3.8+.
- The Chair shows one card at first dispatch; SessionStart explains how to request another.
- `council correct` saves evidenced corrections and missed agent runs without rewriting old seats.
- `usage.tsv` records dispatches and usage; `agents=N` counts Workflow agents and `agents=0` Chair work.
- `council state waiting="…"` records a question and its waiting-change event.
- `references/run-accounting.md` documents usage, corrections, display rounding and status JSON.

### Changed

- Token inputs must be exact plausible counts; repeated or resumed reports are counted once.
- All readers distinguish complete, partial, older and unknown usage.
- History and tuning cost only complete exact runs; five make a proposal eligible, not reliable.
- JSON schemas are now `council.run-snapshot/2` (a `usage` block) and `council.history/3`.
- GitHub Actions use current Node 24 majors; the behavioural runner installs Node 24.

### Fixed

- Progress counts seats; resuming a run clears the old cost line.
- Agent role names are refused as ids; the ledger retains rows with unknown costs.
- A note's line break cannot create a phantom seat in the terminal view.
- Identical copied verifier rows count once; genuinely different rows still conflict.
- Collection ignores planned verifiers; close warns about a missing or outdated claim index.
- Status and TUI label an outdated claim index instead of showing stale verdicts.
- SessionStart asks for widget instructions first; correction JSON avoids a bash 3.2 quoting risk.

### Upgrade notes

- Older ledger rows show `-` for ~k/run and are never priced.
- History and tune leave out pre-0.14 runs; tune needs five new complete exact runs.
- Continuing an older run preserves its old rows as "older" unless corrected from evidence.
- Without Python, use `council run status` for the phase and cost line.

Details: `docs/validation/status-widget.md`, `docs/design/status-widget-adr.md`, `docs/roadmap-status.md`.

## [0.13.0] — 2026-09-27

**TL;DR:** every run now leaves a checkable record, and the council learns from it only as far as
that record supports. Nothing to migrate. The new commands need optional Python 3.8+.

### Added

- `council evidence`: each run's claims and verifier verdicts, in `claims.jsonl`.
- `council repair`: a record of each failed build gate. A build stops once a gate fails three times.
- `council memory propose|accept|reject`: remembered failures, drafted from a run's record and filed
  only on the user's own words.
- `council ledger advice`: how far each seat's record can be trusted. It advises only past a stated
  bar.
- `council tui`: a read-only view of a run, which `--watch` keeps live.
- `council history`: counts across runs. It shows rates only once five runs have the data.
- `council tune`: one setting (the token estimate per worker). It changes only on the user's words,
  is logged and can be undone.
- `evals/bench.py`: Claude Code with and without the council, scored on hidden checks. Running it
  costs money, and it has not been run.

### Changed

- Context packs are opt-in: add `- context packs: on` under `## Run preferences`.
- `council ledger` shows `-` for a seat that no run has judged.

### Fixed

- Context packs now work when the project path passes through a link (macOS `/var`, Windows short
  names).
- macOS strips a byte-order mark at the start of a state file.
- CI: two Windows path checks pass, and every check now runs even after one fails.

Details: `docs/validation/`, `docs/design/` and `references/`.

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
