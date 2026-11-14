# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- A design proposal, `docs/design/task-tree.md`: the request, its tasks and their changes kept as one tree on disk; a builder's orders generated from it; a builder's report checked against its diff (what it removed, the cause of a fix, workaround signs); an unknown made its own research step. Nothing in it is built yet; its three open questions are decided and recorded in it (`Serves:` is required on every task, the user rules on every workaround, the Chair may run one research seat a run without asking). The cleanup plan places its four steps and adds a ninth rule for cleanup sessions: account for what you removed and name the cause of a fix.
- The task tree's plan now covers a project's own architectural decisions (#93). At setup, the council will propose each decision the project already wrote down as a memory entry. The map will gain a table of the one way each job is done. A task will name its row there or say it adds a new way. The verifier will ask whether a change contradicts a recorded decision. Planned for steps T1 and T3; nothing is built yet.
- The council pane: while a run is open, a pane beside the chat shows each seat as a pixel-art critter at its desk (role gear, a mood per state, a squad list under it), and a line above the prompt shows the stage, who is working and the spend; `/council-view` reopens the pane. A Claude Code mod in the plugin (`hooks/council-view.tsx`), tested with `claude plugin test .`.
- The architecture record, for anyone (or any agent) changing the plugin: `docs/architecture.md` (the parts, dependency direction, folder ownership, the run folder's files and who writes and reads each, where new code belongs, the one way each recurring job is done, naming, and the contract names a cleanup never renames), `docs/decisions.md` (32 settled decisions by id, with where each was decided and what holds it), and a root `CLAUDE.md`. Structural checks keep the record true to the code: every helper command, JSON schema and `COUNCIL_` variable must be listed, and every cited decision id must exist.
- The records library, `src/council/records` (with `council.git` and `council.clock`): one module per run file. The scripts now read session-state, run-plan, events, seats, usage, gates, the ledger and the config through it instead of each keeping its own parser, with unit tests in `tests/py/`. Nothing a user sees changes.
- A checking setting: `- checking: one per batch` (the default) or `per task` in the config. Under one per batch a build checks each task with its gates (and a risky task's pair) and dispatches a single verifier, at converge; `council seat` and the agent gate refuse a second verifier in the same build until the user's go is recorded after the last one (one go for each extra verifier), including a Workflow whose script (inline or from its file) starts council verifiers. build-proof.md's new Checking section says what each requires. (#56)
- An open-items setting: `- open items: ask` (the default, today's behaviour) or `fix now` in the config. Under fix now a build's receipt gives each open item one line (what, rough time, rough tokens) and fixes it without a per-item question; commit, push and PR stay questions, and a data-loss hazard still gets its own line the moment it is found. (#45)
- A push freeze: `- pushes: on` (the default), `off` or `off until <date>` in the config. While it is off, a build commits as authorized, records the commit and stops, and the receipt's `Built:` line says "push and PR held by the freeze". (#49)
- `council check` in a post-game reads the deliverable's next tasks once it is recorded: each one's Done-when must quote a part of the request word for word, or it is refused (NOT-IN-THE-REQUEST, NO-QUOTE, NO-DONE-WHEN). Everything else goes under a new "Noticed, not tasked" section with its reach today. (#66)
- A fast test tier and a ratchet, for anyone changing the plugin: `python evals/run_all.py --fast` runs validation, the structural evals, the ratchet, the unit tests in `tests/py/` and the quickest scenario suites in about a minute; `evals/run_ratchet.py` holds each file's size and longest function, ShellCheck warnings, and the counts of council-file parsers, config readers and helper call-backs to `evals/ratchet.json`, where a number may only go down (`--update` keeps a gain and refuses a rise), and holds new Python to the cleanup plan's size limits and the standard library; `ruff.toml` sets the lint rules, stricter for `src/council/`. CI runs ruff on the whole tree, the ratchet and the fast tier before the full suite, with both linters pinned.
- The helper's first commands run in Python (D24): `council home`, `council sharing` and `council run status` now live in `src/council/commands/`, and `bin/council` hands them to `src/council/__main__.py` with their words as typed. Arguments, output and exit codes are unchanged. Each starts one Python and no version probe (`python` first under Git Bash, where `python3` is often the Microsoft Store's stand-in), and loads only its own command module, so it takes about as long as the bash did. Without Python 3.8 or newer on PATH these commands refuse and say how to get it. The library gains `records/home.py`, `records/runs.py` and `records/sharing.py`.
- The agent stop runs in Python: `council cap` (where a run stands) and `council cap check` (the agent gate's decision, with its dispatch record, the hunt words and the one-checker rule) live in `src/council/commands/`, with output and exit codes unchanged. Without Python 3.8 or newer `council cap` refuses and says how to get it, and the agent gate lets agents through, as it does on any fault of its own. The per-seat usage rule the status card and the cockpit read moved from `scripts/cockpit.py` to `records/usage.py`, beside the stop's standing; `bin/council` is about 255 lines shorter. `council seat`, `council correct` and `council cap allow` stay bash until the plan check, the ledger, redaction and the state writer they call are ported.
- The run plan check and the advisory route run in Python: `council run plan check`, `council run plan show` and `council route recommend` live in `src/council/commands/`, with output and exit codes unchanged. `council state`, `council seat`, `council context build` and `council doctor`, still bash, run that same check instead of a bash copy of it. Without Python 3.8 or newer these commands, and the steps of those that check the plan, refuse and say how to get it. `bin/council` is about 480 lines shorter.

### Changed
- `council gate` (one gate, `--all`, `--invalid`), `council gates` and `council changed` run in Python now (S6), with the same output, exit codes and gate files. A gate past its time limit is still stopped with every process it started, on Windows and POSIX. `gates.lock` names the Python process that holds it (D33); on Windows a gate call stopped by TERM from Git Bash ends outright, so its lock is cleared by the next call, which says so.
- Contributors: CI's full suite on Ubuntu, Windows and macOS is the gate before merge; locally, the fast tier and the groups a change touches come before a push (`CLAUDE.md`, `CONTRIBUTING.md`, the cleanup plan's rule 8). A local full run took 35–48 minutes on Windows and two can't run at once on one machine.
- The ratchet's "files that parse a council file" count now names every council file, not seven: the files `docs/architecture.md` §4 lists (read from the doc) and six it doesn't name yet (`claims.jsonl`, `corrections.jsonl`, `cap-allowances.tsv`, `repair-allowances.tsv`, `tools.tsv`, `tuning.md`). The count goes from 3 to 12 (new: `scripts/audit.py`, `cockpit.py`, `context.py`, `evidence.py`, `memory.py`, `outcomes.py`, `repair.py`, `status.py`, `tune.py`). That is a measurement correction, not a regression: those scripts already parsed those files; the baseline was set by hand for that one count and every other number is unchanged or lower.
- `references/` is laid out by who reads each file: the run's contracts, records and procedures are in `references/run/`, the spec-writer's documents in `references/spec-writer/` and the test-architect's in `references/test-architect/`. The seat docs, `guardrails.md` and `build-proof.md` keep their paths at the root, because project files carry them. `references/README.md` is the map, and a structural check keeps the layout true.
- One rule, one place (first pass): each rule the skills, the stage doctrine and the run references stated twice is now stated once, in its owner (a kernel law in context-core, a stage rule in its doctrine, a file's shape in its reference), and the other places point at it by section and step. The protected subjects are one kernel line. A seat's brief block links only that seat's card and doc, never another seat's. A structural check fails if a folded rule's wording appears outside its owner. Copies that disagreed now say one thing: every mode's rulings are one question (Deliver, step 6), every mode files the request first (Deliver, step 1), Convene counts verifiers as Challenge batches them (one per 8 of the rest), a build's converge drafts pr-body.md and the PR is opened from it only at Deliver after the user's OK, the agent gate's blind spot is the Agent call's `model` parameter (not the dispatch), and law 9 records every decision in the user's own words. A review run's method load is 56,970 bytes (it was 59,387). (#67)
- The verifier judges each Done-when and nothing wider: it tries hard to show a Done-when is not met, and anything it notices beyond one is a line under `## Noticed`, never a verdict or a task. The agent gate refuses a build verifier's brief that sends it hunting ("however narrow", "any route", "find anything else"). (#46)
- The build tier now says only how much proof a build records; how many verifiers check it is the checking setting.
- Rulings reach the user as one question (Deliver, step 6): the harmless items together under one plain sentence ("nothing here can break the app or lose work"), the recommended option first, each option saying what happens next and what it costs, a real hazard as its own question with fix now as the default, and the detailed notes in the log. The kernel, the build receipt and the post-game point at it. (#52)
- Before the PR question a build fetches (`git fetch`, `gh pr list --state all`), says whether the base moved or a related PR merged, and prints `<run>/pr-body.md` for the user's edit or OK; the PR question comes only after that OK. To make room, the diagnosis worker's brief moved into `references/run/repair-loop.md` and the deliverable's evidence-trail rules into `references/run/evidence-model.md`. (#48)

### Fixed
- Contributors: the "close without Python" scenario in `evals/run_cli.py` (`runs_close_keeps_audit`) now moves its run to Deliver with Python and closes it without, as the tuning close scenario does. Since S5 a phase change runs the Python plan check, so on a machine with no Python beside bash and git the run never reached Deliver and the check failed. CI never ran it, because Python sits on its PATH.
- `council run close` keeps the audit it ran: the whole report (every FAIL, warn and pass line, and the transcript window it read) is saved as `<run>/audit.md`, written atomically; a run closed again (paused, resumed, closed complete) rewrites it. The close line, the closing card (`Audit:`, in the text and the widget) and `council run status` name the path, and a card for a run with none says so and names `council run audit`. Without Python there is still no audit. `council run audit` alone still writes nothing. (#53)
- A seat that ran as an agent but has no token figure is no longer silent. The close's audit has a new item, "Token figures", graded FAIL like the audit's other gaps in a run's own record (a seat never recorded, an agent recorded only when it finished): it names each such seat and says why when the record shows it (no agent id recorded, a finished agent with no usage report, one of several without, a figure under 1,000), with the `council correct` that puts it right. It reads the one per-seat usage rule (`records/usage.py`) the ledger and the cockpit use; the Chair's own seat and a seat declared `agents=0` are no gaps. `council tune` (and `tune --json`, `budget.unfigured`) says in one line how many seats in how many completed runs it left out of its measurement and why, instead of leaving them out without a word. (#54)
- The agent gate refuses a council-worker or council-verifier while the council home (`.council/`) or the run folder the dispatch names can't be written from the session, and says which folder and what to do next (open the session in the main checkout, or fix the folder's permissions). A session opened in an app worktree that could not write `.council/` used to send a seat out with no brief, about 31k tokens wasted; the gate now tries to make a file in the folder, so it is right on Windows and under a sandbox, and an ordinary agent, or a probe that fails for another reason, is let through. A linked worktree already finds the main checkout's `.council/` (`council_home`), so no pointer file was added. (#51)
- Three readers that kept their own rule now use the helper's (#73, #74, the rest of #75). `council memory propose` and the claim ledger read a run's `mode:` and `deliverable:` from the session-state header only, as the helper's `state_field` does; a decision or note below a heading that began `mode:` was read as the mode. `council tune` reads `- estimate per worker:` by the route's rule: `1,50k` is unreadable to both, so tune says the route budgets the 80k default instead of showing 150k while the run was sized with 80k. `council status --line` finds `- notifications: off` in a config of any size (it read only the first 64 KB). `state.values`, `state.first_value` and `state.first_word`, which read below the header, are gone. The repair loop's build-run test (`state.is_build_run`) and the plan-schema test the status card uses (`state.planned`) read the header only too: a `mode: council-implement` note below a heading no longer makes a review a build run, and `mode: council-implement  # note` in the header now counts, as the helper reads it.
- A hand-edited CRLF council file reads as the helper reads it (part of #75; on Windows its awk and sed drop each line's carriage return): `- estimate per worker: 150000` and `150,000` read as unset, a CRLF `agent-starts.tsv`, `usage.tsv` or `cap-allowances.tsv` whose last cell is the figure counted differently (the agent stop and the status card could disagree), `- notifications: off` was not seen as off, and `state.values` returned a value with a trailing carriage return. All now go through `cells.lines_of`; `checking` no longer strips a carriage return of its own.
- `council tune` no longer stops with a traceback when the config's estimate per worker is hundreds of digits long: the library now reads an over-long token figure as unreadable, as the helper does, and an over-long `- agent cap:` as the default.
- The repair trail no longer refuses a sound event stream as malformed when a free-text cell (a skip reason, say) holds U+2028 or U+0085: the stream, like the run plan's keyed rows, is now split on newlines only, as the helper reads it.
- The status widget no longer shows a seat figure from a hand-written correction whose `to` is a string (`"to": "2"`), which the helper's ledger never counts; only a bare number is a correction, in both.
- On Windows, `council status` and `council tui` no longer refuse a run folder as "a link to one" when its path is typed in a different case from the folder's name.
- The outcomes eval's "close commit comparison writes nothing" check failed once on macOS and passed minutes later on the same commit. Its scratch repo no longer lets a commit start git's background maintenance, and a failure now names the files that differ.
- A bash and a Python writer of one run file now exclude each other on Windows (D33). A lock's owner file names its holder by the Windows process id whichever language wrote it, and bash checks one with `ps -W`; before, each read the other's live holder as gone and could take its lock. A waiter that gives up now names the process holding the lock, how long it has held it and what to do, and a bash waiter gives up at 20 s as Python's does (it took 28.5 s on Windows). On Windows Python also stops trusting a live process made after the owner file was written: its id was reused. An owner file that names no possible process (0, or an id past the system's range) is read as no owner by both languages, where Python crashed on it and bash and Python disagreed.
- On Ubuntu 26.04 two calls could hold one lock at once (the events, state, seat, close and gate locks), so events got the same sequence number and a seat change ended with "its lock could not be released". Its `mkdir` (uutils 0.10.0) can exit 0 for a directory another process made at the same moment. A call now holds a lock only once it has made the lock's owner file itself (noclobber, so the create is exclusive), and a call that finds another's owner file there waits, as before.

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
