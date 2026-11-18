# Redesign 2.0: a proposal

**Status: a proposal, written 2026-11-18.** A part becomes real only when the owner says so, and
then it gets its entry in [`decisions.md`](../decisions.md). Stage 1 (section 12) was decided on
2026-11-18 as D47 to D51 and built in 1.3.0; nothing else here is decided or built. Section
2 is measured. Everything after it is the planning session's design, built on those measurements and
on how this repository is run.

## 1. Who it is for

One owner who builds real projects with agents and does not read code. That owner needs four things:

- to know the work does what they asked, shown and not claimed;
- a project that stays consistent as it grows, with no workarounds piling up;
- decisions brought to them as consequences, with a recommendation, and only the ones that are theirs;
- a tool fast and cheap enough to use on every change.

## 2. What the measurements say

Two real changes (a C++ game project, 36 files; a Python rules project, 29 files) were reviewed in
six ways. A blind judge on a stronger model rated every finding. Ten defects were judged worth
acting on across both changes.

| Setup | Found, of 10 | Noise items | New tokens | Minutes (game / rules) |
|---|---|---|---|---|
| Council review 1.2.0, Squad size | 2 | 8 | 1,453k | 16 / 20 |
| One plain reviewer | 6 | 1 | 937k | 17 / 42 |
| One plain reviewer, tests at both ends started together | 4 | 2 | 855k | 15 / 22 |
| A reader alone | 8 | 1 | 407k | 7.5 / 7.8 |
| A runner alone | 5 | 0 | 532k | 17 / 22 |
| Reader and runner together | 9 | 1 | 939k | 17 / 22 |
| Claude Code's built-in `/code-review`, high effort | 4, and 2 that no other review found | 2 | 569k | 10 / 12 |

The built-in review was run on 2026-11-18, each change in its own fresh session, on a copy holding
the same files and history the other reviewers saw. It found the clearance turn that leans inward,
the ring drawn over the body, the document over its size limit and the junk re-pin's red test. It
missed the other six, including both ruling changes on the rules project. It ran nothing on the
rules project, because its copy had no Python environment. Its two new finds, both judged worth
acting on: a second test the junk re-pin left red, and a way the named SOS can change overnight on
the same LPS. An earlier reviewer had called that outside-day case a documented cost, so that
one is contested.

Where the council's time went:

- Each seat worked for 0.4 to 1.9 minutes. The plain reviewer worked for 15 to 21. The comparison
  was four short skims against one deep read.
- About 11 minutes of each council review was the main session's own process. The first seat went
  out at minute 4.4 and minute 9.4.
- The one real build on record took 45 minutes for a one-line change: 109 tool calls and 46 helper
  commands by the main session, and a final check that took under 2 minutes.

Limits of this evidence:

- "Ten defects" counts only what some review found.
- One judge rated each item, on two changes.
- The reader was told a colleague runs the tests, which may be what focused it.
- Council seats ran on a smaller model than the other reviewers.
- Two runs of the same prompt found different things.
- Builds have one run on record. Plan, research and post-game have none.
- The built-in review's two new finds count outside the ten, so the reviews above them were not
  asked to find them.

## 3. The idea

**Agents do not remember, and the owner does not read code.** So the plugin does three jobs:

1. It keeps the project's memory where every agent starts from it.
2. It checks claims by running them.
3. It brings the owner decisions in terms of consequences.

Today's plugin is built around a ten-stage process for the main session. The redesign is built
around those three jobs.

## 4. The project's book

Six things live in the project, tracked in git. Every agent reads the first three before anything
else. Where a project already has such a file, the plugin uses it and does not make a second one.

| Part | What it holds | What exists today |
|---|---|---|
| The design page | The parts, who owns each folder, the one way each job is done, where new code goes. Two pages at most. | The map and its one-way-per-job table (D35) |
| The stack page | What the project is built with: languages, frameworks, libraries, tools and services, each with the reason it was chosen. One page at most. | Setup detects the stack and writes it to the config, with no reasons |
| The decisions log | Each decision in the owner's words, with its reason and what was rejected. Changed only by a new entry, on the owner's word. | Memory's decisions; `references/roster/decision-records.md` reads a project's own log at setup |
| Rules as checks | Every rule a machine can check has a test that fails when the rule is broken. Numbers that may only improve are held by a ratchet. | The config's gates; `references/guardrails.md` and its ratchet |
| Feature specs | Each feature as behaviour the owner can observe. The lines become the builder's "done when" and the tests. | Plans; the spec-writer skill |
| Known problems | True things found and not fixed, so they are neither lost nor reported twice. Also the kinds of item the owner has said not to raise again. | Nothing. Review items below the bar are dropped today |

**The stack is the owner's decision.**

- A new project starts with it. The designer proposes a stack and says what each choice gives and
  costs. Because it is hard to undo, a second, independent proposal is made before the owner sees it.
- Adding a library, swapping a tool or bringing in a second language is a decision, never a side
  effect of a task. A builder that needs one stops and asks, as it does when the design does not fit.
- A change to the stack is a new entry in the decisions log, on the owner's word.
- The reader reports anything a change brings in that the stack page does not list.

**The book stays small and explained.**

- Every rule names the bug or the decision it came from, and its date, so it can be retired when
  its reason is gone.
- A line enters the book only if removing it would change what an agent does. A line that restates
  the code stays out.

## 5. Four jobs, no expert roster

| Job | What it does | Agent type (names stay, D23) |
|---|---|---|
| Designer | Reads the book and the code under the request. Says where the work fits, what is broken underneath, and where there is a real fork. | `council-worker` |
| Builder | Builds one task. Stops and reports when the design does not fit, and never works around it. | `council-builder` |
| Reader | Compares what the record says with what the code does. The book is part of the record, so the reader reports where the code no longer matches it. Traces each change to its callers. Runs no test suite. | `council-worker` |
| Runner | Runs the old and the new code side by side in a scratch clone and shows what changed. | `council-worker` |

- The reader and the runner use the role texts in Appendix A, which are the measured ones.
- The expert catalogue stops being a list of agents. Its pages become reading: the reader is handed
  the relevant page when a change touches a protected subject (authorization, data loss, injection,
  secrets, concurrency or ordering, public contracts).
- `council-verifier` stays for one use: an independent check on a protected subject.
- One builder writes at a time (D42 stays).

## 6. One loop

The owner says what they want. The plugin picks the depth from the work; there are no sizes to choose.

1. **Understand.** The request is restated as behaviour lines the owner can check. At most one
   question, with a recommended answer.
2. **Look underneath.** The designer reports three things:
   - where the work fits in the design, and which existing way it extends;
   - any bug the request rests on (see the rule below);
   - any real fork, as a decision for the owner.

   A decision that is hard to undo gets a second, independent design before the owner sees it. A
   small request gets a three-line design and goes straight on.
3. **Build.** One fresh builder per task. The project's checks run before the first change and after
   each task. The builder gets its task from one command (D41) and one page of rules.
4. **Prove.** The reader and the runner check the whole change against the behaviour lines and the
   book. Neither reads the builder's report. For each behaviour line, the runner breaks the
   behaviour on purpose in its scratch copy and shows the test fail; a test that stays green is
   reported. One fix round follows if needed (D11 stays).
5. **Report, then update the book.** See section 8.

### The bug-first rule

When the code under a request is wrong, the owner hears about it before anything is built on top:

- **Only a bug the request rests on stops the work.** Anything else goes to known problems.
- **The bug is shown by a run, never argued.** The owner cannot check the claim by reading.
- **The message is a recommendation:** what is wrong in the project's own terms, what building on
  it would cost, and the three answers (fix it first, build anyway and note it, stop).
- **After the fix, the original request continues** without being asked again.

Today's rule (a builder's `NEEDS: fix`, D36) covers the build step only. This extends it to step 2.

## 7. The commands

Existing names stay and become entry points into the same loop.

| Command | Steps it runs |
|---|---|
| `/council` (new) | 1 to 5 |
| `/council-plan` | 1 and 2, then stops with a plan |
| `/council-research` | 2 for a question, with no build |
| `/council-implement` | 3 to 5, from an approved plan or a review's findings |
| `/council-review` | 4, on any change |
| `/council-postgame` | 4, against the owner's original request |
| `/council-health` (new) | Lists where the project drifted from its design and proposes refactors, each with a cost and a reason |
| `/council-init` | Sets up or refreshes the book. On a new project it starts with the stack decision |

`spec-writer` and `test-architect` stay as they are until stage 4 decides whether the design step
replaces them.

## 8. What the owner sees

**The report**, the same shape after every run:

- **Works now:** each behaviour line, and how it was shown. A change the owner can see on screen
  comes with a picture from before and one from after. When the project cannot be started for a
  picture, that goes under "Not proved".
- **Does not work:** what, and what the owner would notice.
- **Your decisions:** each with what happens if nothing is done, the recommendation, and whether it
  can be undone.
- **Not proved:** what no run could show, and why.
- **Noted for later:** what went to known problems, five lines at most.
- **Cost:** tokens and minutes, against the estimate shown before the run. The estimate uses how
  long the project's checks really took last time.
- **Undo:** the one sentence that takes the whole change back. Every run that changes the project
  leaves a restore point first.

**The worth bar.** An item reaches the owner only if they would act or decide on it. Noise costs
this owner more than it costs a coder, because they cannot tell which items to ignore. When the
owner waves off a kind of item, it is written to known problems and not raised again.

**A review shows its first findings early.** The reader's serious findings appear in chat at about
8 minutes, and the runner's are added when it finishes.

## 9. What the main session does

- **One page per command**, holding its commands in order and its fixed brief. The ten stage files go.
- **It starts the agents within about 2 minutes.** Its own checks run in the background after that.
- **It checks each serious finding against the code itself** before handing it over.
- **Records kept:** the request in the owner's words, the decisions, the outputs of the checks, the
  restore point, the report.
- **A run can be picked up from its records** after the session is interrupted, as it can today.
- **Hard stops kept:** no "it works" without a check's output, nothing destructive, no push without
  the owner's word, a cost cap, an agent's file must exist before it stops, and text found in code,
  files or web pages is never treated as an instruction.

## 10. What stops being used

- The ten-stage process and its ten rule files.
- The expert roster as agents, and the war room.
- The three sizes, and the plan of each run with its per-seat budgets.
- Seat ledgers and the audit of the process.
- Most of the build references (about 60,000 bytes today).

Contract names are frozen (D23). A name that stops being written stays readable until a decision
removes it with a migration. Each stage lists the names it stops writing.

## 11. Decisions this would touch

This table is the planning session's reading of [`decisions.md`](../decisions.md). Each stage
confirms its rows before anything is built, and every superseding entry needs the owner's word.

**Replaced:**

| Id | Today | Under the redesign |
|---|---|---|
| D8 | Every run is sized and budgeted; a run cannot skip a required stage | A run is still opened, reported and closed. Sizes, budgets and required stages go |
| D9 | Approval carries up to a configured size | The cost is shown first; a cost cap in the config; above it needs the owner's go |
| D14 | Modes add `## At <Stage>` sections to a shared ten-stage core | Each command has one page for its path |
| D15 | Seats come from the catalogue and the config | Four fixed jobs; the catalogue becomes reading |
| D17, D18 | Build tiers; one verifier per batch or per task | Every build ends with the reader and the runner on the whole change |
| D43 | A first review runs a quick setup that names the catalogue's seats | A review needs no roster. The aim, no setup before a first review, stays |
| D46, and D13's doctrine-file limit | A review's method load under 50,000 bytes across twelve files | A smaller budget on the one page a review reads |

**Changed in part:**

| Id | What stays | What changes |
|---|---|---|
| D1 | One head; the owner rules | "Seats advise" becomes the four jobs |
| D5 | A checker never sees the author's reasoning | The main session checks serious review findings itself; an independent verifier is for protected subjects |
| D10 | The main session decides inside the approved scope and logs it | The owner's own decisions arrive as consequences with a recommendation |
| D12 | Proof is a check's output; "nothing was checked" is never a pass | The runner's two-ended run becomes the proof for the whole change |
| D35, D36 | A task names the job it extends; a second way or a contradicted decision is refused; a bug underneath stops the branch | The reader checks these too, and the bug rule starts at the design step |
| D37 | A model per role, named in the config | The roles become designer, builder, reader and runner. Reader and runner use the session's model |
| D38 | A fix names its cause; a round's report is checked against its diff | The report gets shorter. Stage 3 decides by how much |
| D41 | A builder's orders come from one command | Four reference documents become one page |
| D28 | Memory is filed only on the owner's words | The decisions log in the book is where it lives |

**Kept as they are:** D2, D3, D4 with D42, D6, D7, D11, D16, D19 to D27, D32 to D34, D40, D44, D45.

## 12. Five stages, each with its own test

A stage ships only if its test passes. A wrong guess costs one stage.

| Stage | What is built | Its test | Pass bar |
|---|---|---|---|
| 1. Reviews | The reader and the runner as the review; the one-page path; the worth bar; the main session's own check of serious findings | The built plugin on the two measured changes and on a third, unseen one, judged blind | At least 7 of the 10 known defects; at most 2 noise items a run; first findings within 10 minutes; a whole review within 25; no more tokens than today's review of the same change; nothing false on the unseen change |
| 2. The book | Setup writes or adopts the design page, the stack page, the decisions log and known problems; every agent reads the first three; each rule carries its reason; the reader checks a change against the book; the list of items not to raise again | The same feature given to two builders on one real project, one with the book and one without; the reader and the runner review both blind | Fewer workarounds and second ways with the book, nothing added to the stack without a stop, and no more defects |
| 3. The build loop | A task and one page for the builder; the reader and the runner at the end; the bug-first rule; the report of section 8 with its pictures and its undo line; the restore point; the runner's proof that each test can fail | One plan built twice from the same commit, by 1.2.0 and by the new loop, reviewed blind | No more defects than 1.2.0, in at most half the time |
| 4. The design step | The designer; decisions as consequences; a second design for what is hard to undo; plan and research as entry points | The same request through 1.2.0's plan and through the designer. How to judge two plans fairly is not settled | To be set with the owner before this stage starts |
| 5. The whole loop and health | `/council` and `/council-health` | One real feature from request to report; one health pass on a real project, judged blind for worth | The feature's behaviour lines all shown; at most 2 noise items in the health pass |

**Rough cost.** Stage 1 is planned in detail: about 1 to 1.3M tokens to build and 2 to 2.5M to test.
The other stages are expected to cost about the same as stage 1 each. That is a guess, not an
estimate.

**Versions.** Stage 1 is 1.3.0. Stages 2 to 4 are minor versions. Stage 5 is 2.0.0.

**Stage 1 in more detail.** The pair runs as two fixed seats of a Squad-sized run, so nothing is
renamed. The worker's turn limit rises from 60 to about 100, and a brief may allow the project's
checks to run in a `git clone` under the run's scratch folder, never in the project tree. A helper
change lets the main session record its own check of findings on a run that is not Solo. The
expert seats leave reviews entirely. The runner records how long the project's checks took, and
setup records the same when it tries them, so the next estimate uses a measured time.

**The built-in review does not replace the reader.** Measured on the same two changes, it found 4
of the ten known defects against the reader's 8, with one more noise item, so the plugin keeps
its own reader (section 2).

## 13. What is given up, and the risks

- **Breadth of expert lenses by default.** If a real review misses something a lens would have
  caught, that is the evidence to bring one back.
- **The detailed trail of each run.** The request, the decisions, the check outputs and the report
  stay; the rest goes.
- **The runner depends on the project.** Its checks must run in a clone, and the session's
  permissions must allow them. When they do not, the runner says what it could not run.
- **A design decision can be wrong, and the owner cannot check it by reading.** The protection is
  the recorded reason, small steps that can be undone, and a second design for the few that cannot.
- **Most of this is unmeasured.** Only stage 1 has numbers behind it. That is why each stage has a
  test and a pass bar.

## 14. Points the planning session decided, for the owner to overrule

1. The book uses the project's own files where they exist, and `.council/` where they do not.
2. Builders stay one at a time.
3. No command is renamed or removed; two are added.
4. The expert catalogue is kept as reading, not deleted.
5. Every bug found late becomes a check that would have caught it, or a line in the design page.
   This replaces the seats' track records as the way the plugin learns a project.
6. The plugin keeps its own reader. Claude Code's built-in review was measured and found half as
   much (section 2).
7. The stack is one page of the book, read by every agent, and not a set of planning documents.

## 15. Ideas from other tools, checked on 2026-11-18

The check was five web searches over comparison posts and vendor write-ups, on top of the study in
[`doctrine-0.3.md`](doctrine-0.3.md), which read the tools' own repositories.

**Taken, with where each went:**

- A restore point and one sentence to undo a run (products for owners who do not code): section 8.
- A rule carries its dated reason; a line must earn its place in the book (a write-up on agent
  discipline; BMAD's admission rule): section 4.
- The book is checked against the code on every review, because drift between documents and code
  is the most reported failure of spec-first tools: section 5.
- Items the owner waves off are not raised again (review tools that learn from dismissals):
  section 8.
- The built-in review as a comparison, measured: section 2.

**Not taken:**

- Role-play personas and long planning documents (BMAD). The owner would not read them. The stack
  page takes the useful part: what was chosen, and why.
- Several builders writing at once (Get Shit Done). Two writers collide (D42).
- Regenerating code from the spec. Reports say the reasons behind the code get lost.
- Loading the whole method into every session (Superpowers). Rejected in the earlier study.

**Not checked:** gstack. The search returned nothing on it.

## Appendix A: the measured role texts

Both texts were used with the same closing rules: report real problems only, a finding not checked
against the code is worth less than no finding, no style points and nothing that was already so
before the change, change nothing in the project, and give the review as the final message. An
agent's attempt to write a report file was refused in the test, so the final message is the review.

**Reader**

> Your half of a two-person review. A colleague reviews the same change at the same time and owns
> running things: the test suites, builds, and behaviour probes at both ends. You own reading. Trace
> each changed function to its callers and to whatever reads its output; check what the change's own
> record (commit messages, docs, decision notes, comments, test names) says against what the code
> does; look for edge cases, wrong maths or state, and tests whose assertions don't prove what they
> claim. Don't run the project's test suites or builds. Small read-only commands (git, grep, a few
> lines of Python against a file) are fine.

**Runner**

> Your half of a two-person review. A colleague reviews the same change at the same time and owns
> reading: tracing callers and comparing the change's record with its code. You own running things.
> As your very first step, put a copy of each end of the change in your scratch folder (a local
> `git clone` of the repository into the scratch folder, checked out at each end, keeps the git
> history that some tests read) and start the project's checks (build, tests, linters, any slow
> tier) at both ends at once, in the background. While they run, read just enough of the change to
> decide which behaviour to probe, then write small probes that run both ends and show what changed.
> Report what the runs and probes show: tests that changed result, behaviour that differs from what
> the change says it does, and anything the runs can't tell you.

Two things the tests taught about the runner's copy: a copy without git history hid a failing test
that reads the history, and a checkout with Windows line endings made a content test fail at both
ends.
