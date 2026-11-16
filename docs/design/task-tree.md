# The task tree: context down, evidence up

Status: written 2026-11-13 on the user's request. Steps T1, T2 and T3 are built and on main; T5 is built on
`claude/t5-fresh-builder`, all but one refusal of section 6 (a task that rests on a `NEEDS: fix` stop: the helper
does not refuse it yet, because a seat's old note outlives its stop in `records/seat_write.py`, and that fault is
the owner's to rule on first); T4 is not. "A bug underneath stops the branch" (in section 4) and section 6, a fresh
builder per task, were added 2026-11-15; section 6 is built by T5 and settled as D42.
Each part becomes a decision in [`../decisions.md`](../decisions.md) in the branch that builds it.

## The question

The user asked how the council knows that:

1. the code it writes is high quality and follows the project's architecture;
2. a fix removes the cause, and is not a band-aid or a cheap workaround;
3. an agent did not take the easy way out;
4. a problem nobody can solve yet gets researched, not guessed at;
5. the work is seen as a tree: a trunk (the request) that splits into branches (tasks), which end
   in leaves (single changes), with each agent handed the right part of it.

Today the answer is "partly, and partly by luck". Two things from the day this was written:

- A session that moved text out of a skill to make room reported "moved, not cut". Three rules had
  been cut. They were found because the planning session happened to grep for them.
- A review session "corrected" five true statements in a document. Its brief never said which
  state of the code the document described, so it judged against the wrong one.

Both have the same two causes. **A report is a claim, and nothing checked it against the diff.**
**Context was written by hand, and the part that mattered was left out.** This design is about
those two causes. It adds no checker agents: machine checks over checker agents stays the rule. The one
agent it adds is the builder of section 6 (D42).

## What the council already has

| Part of the tree | Today | Gap |
|---|---|---|
| Trunk: the request | `ask.md`, in the user's own words; hard constraints and memory in the brief | Nothing ties a task to the part of the request it serves until a post-game splits the request afterwards |
| Branch: a task | A plan task with `Depends on` and `Done when`; the verifier judges the Done-when | No owner (which module, which existing way it extends). No list of what it rests on |
| Leaf: one change | Change or preserve proof through `before-`/`after-` gates (`references/build-proof.md`) | Fix rounds and repairs carry no stated cause |
| Context down | `brief.md`, written by hand. The opt-in seat packs that added evidence beside it were removed on 2026-11-15: off by default and never measured | A builder's orders are composed by the Chair each time; rulings and builder rules are re-typed (#57, #61) |
| Evidence up | A seat file and one line back; the receipt's `Shortcuts I took`, `Not proved`, `Left open` | All self-reported. Nothing lists what was removed. Nothing compares the report with the diff (#58, #59) |
| Unknowns | Evidence states (`ASSUMED`, `INFERRED`); one diagnosis worker on a second failure | No rule that an unexplained failure stops code changes. "I don't know" is not an accepted answer from a builder (#64) |
| Patch on patch | The repair loop stops at a third failure | Nothing notices a third fix round in the same files (#50) |

## The design

### 1. The tree is on disk

A plan task gains three fields beside `Depends on` and `Done when`:

- **Serves:** the part of the request it serves, quoted word for word. The post-game already checks
  next tasks this way; the plan check does the same for every task. A task that serves nothing in
  the request is refused, or goes to the user as a scope question.
- **Owner:** the module or folder that owns the change, and the existing way it extends (from the
  project's `map.md` and `conventions.md`). A task that adds a new way says `New way:` and why, and
  that is a ruling for the user, recorded in memory as a decision.
- **Rests on:** the facts the task assumes, each with its evidence state. A plan already sends its
  assumptions to the verifier; this keeps the result on the task.

The tree is these fields on the plan, not a new file. `council tree` prints it from `ask.md`, the
plan and the run's task state: the request's parts, the tasks under each, each task's proof and
verdict. After a compaction the Chair resumes from that view, not from memory.

### 2. Context goes down as a generated pack

`council context build task-<n>` prints a builder's orders from files, in this order:

1. the request line it serves, verbatim, and the task's `Done when`;
2. the owner: the files in its slice, the one way this job is done here, and what it must not touch;
3. the hard constraints and the memory entries in scope, word for word;
4. the user's rulings so far in this run (#61) and the standing builder rules (#57);
5. what earlier tasks in this run changed in the same files, from the change index;
6. what was left out, by name, so an omission is visible.

It is the only context provider. The seat packs that `council context build` wrote until 2026-11-15
chose index entries by a seat's slice, which is a different job, so T3 writes this one new, in the
package, on the records owners. The Chair adds judgement (where to
start, what worries it) and nothing else. A pack is smaller than a hand-written brief plus the
whole plan, and the part that was lost on the day above (the state of the tree the work is judged
against) is in it by construction. Seats get doctrine by surface the same way (#67).

The pack is printed, never written, and is at most 8,000 bytes: UTF-8, the whole printed text, its
last line included (`CEILING` in `src/council/commands/context.py`). Left out's bytes come first.
While the pack is over the ceiling, the last of parts 1-5 still in it is dropped whole and named
under Left out, never cut midway. The last line is `pack: <bytes> bytes of 8000; left out: <parts> |
nothing`. Measured in T3: 2,238 bytes for the eval's build task and 1,614 for the plan-check
fixture's task, against 1,650 for the seat brief block in 04-brief.md alone; in the first real build
(2026-11-16, three tasks, a config with hard rules, a map table and memory) 3,971 to 4,385 bytes. The
standing builder rules (2,234 bytes) are linked, not inlined. The ceiling is a guard, not a target.

### 3. Evidence comes up as an account the helper checks

The builder's report gets a fixed head (#58). Beside what it changed, the head says:

```
Cause: <for a fix: what was wrong, in one sentence> · state: OBSERVED|REPRODUCED
Owner: <where the change was made>
Removed: <each rule, behaviour, test or assertion taken out, and where it stands now> | none
Assumed: <what it relied on without checking> | nothing
```

The helper saves the diff when the report arrives (#59) and compares the two before the verifier
sees either:

- **Removed.** A deleted test, assertion or document rule that the head does not list is refused.
  The builder lists it or puts it back.
- **Owner.** A file changed outside the task's slice is flagged for the verifier as possible scope
  creep, before it reads anything else.
- **Workaround signs.** Added lines that retry, sleep, catch everything, skip a test, raise a time
  limit or loosen an expected value are listed for the verifier as questions. They are signs, not
  verdicts: some are right.
- **Cause.** A fix whose cause is `INFERRED` or `ASSUMED` has not earned a code change. See 4.

The verifier stays blind to the builder's reasoning. It gets one more question for a fix: does the
change remove the cause, or hide the symptom? A change that hides it is INCOMPLETE, with the reason.

### 4. An unknown becomes its own leaf

Three rules, all of which make "I don't know yet" an accepted result:

- A task that rests on an `ASSUMED` or `INFERRED` fact about something outside the repo (a tool, a
  platform, an API) gets a probe or research leaf before its build leaf.
- A failure nobody can explain stops code changes. The next step is a probe that measures, then the
  fix. Guess-and-rerun is the patch-on-patch path.
- A builder may return `NEEDS: <question>` (#64) and stop. That counts as a correct outcome in the
  ledger, not a failed seat. An agent guesses when "done" is the only answer the run accepts.

A third fix round in the same files is refused (#50): the task goes back to the plan as a redesign.

#### A bug underneath stops the branch (added 2026-11-15)

The user's words: the council should say "hey, i've stopped working because there is this bug here
that needs fixing", not ship a workaround that is found weeks later under all the work built on it.

T1 and T2 cover a fix: it names its cause, and the verifier asks whether the cause is gone. They do
not cover a first build that meets a bug in the code it builds on. That round's `Cause:` is `none`,
the verifier's question is not asked, and the owner check tells the builder to stay in its slice. So
the cheap path is to make up for the bug inside the slice, and the Done-when still reads met.

- **The stop.** A builder that finds the code under its task wrong stops and returns
  `NEEDS: fix <file:line> · does: <…> · should: <…> · seen: <the command or test, and its output>`.
  Wrong means a `Rests on` fact that is false, or code that does not do what its owner's row, its
  tests or its own documentation say. It is the `NEEDS:` stop with a second kind of content, so it
  is recorded the same way and counts as a correct outcome. `seen:` is OBSERVED or REPRODUCED; a
  suspicion is a `NEEDS:` question and gets the probe.
- **The Chair.** It stops that task and every task that depends on it or rests on the same code;
  the others carry on. It tells the user in one line: what is wrong, where, and what is stopped.
  The fix is a new task above the blocked one, with its own `Owner` (the code that has the bug) and
  the `Serves` line of the task it unblocks. Its cause is already observed, so it needs no probe.
  It starts only on the user's yes (decided, 5).
  The implement skill's "blocked by something outside the input: log it; carry on with the other
  tasks" becomes "carry on with the tasks that do not rest on it".
- **The verifier, on every round.** Not only on a fix: does any added line exist only to make up
  for other code in this repo? If so, name that code. Such a change is INCOMPLETE even when the
  Done-when is met, unless the user ruled that workaround (decided, 2).
- **Two more signs** for the helper's list: an added line that says workaround, hack, temporary,
  "for now" or "until … is fixed", and an added `TODO`, `FIXME` or `XXX`.
- **The pack** (section 2) carries the task's `Rests on` facts and the owner rows of the code it
  calls. A builder that sees only its slice cannot tell a bug from a design.

### 5. The Chair's own context

The Chair reads one-line returns and helper views, never seat files in bulk. Every fact it needs
to resume is in a file the helper prints: the tree, the state, the rulings. A rule the Chair keeps
breaking moves into the helper or a hook (architecture §7), because the skills are at their size
caps and prose is the weakest enforcement.

### 6. A fresh builder per task (added 2026-11-15)

The user asked for this to be planned after a comparison with the other tools of this kind: the
large ones (Superpowers, Get Shit Done, BMAD) all build each task in a fresh agent.

Today the Chair builds in its own window (D4). Three things follow:

- the Chair writes the code, names the cause and writes the receipt, so the checks on a builder
  are the Chair checking itself, and "the builder stops on a bug underneath" (section 4) is the
  Chair stopping itself;
- the Chair's window is the largest context of a build, on the session's model, and every later
  turn reads it again;
- a build's verifier may not be on a cheaper model than the session's, because the Chair is the
  builder it checks (D37).

**What stays.** One writer at a time (kernel law 2). The loop's steps and its proof: the gates, the
report head, `council patch save`, the fix rounds and their limits. The blind verifier. The size
and cost proposal before anything starts.

**What changes.** The writer is a builder agent, one task at a time, never two at once.

| Step of a task | Today | Planned |
|---|---|---|
| Orders | The Chair reads the plan, the reference and the code | `council context build task-<n>` writes the pack (section 2); the Chair adds where to start and what worries it |
| Before gate, the change, the gates, the report, `council patch save`, after gate | The Chair | A builder agent in a clean window. It returns one line: done, `NEEDS: <question>`, `NEEDS: fix …`, or blocked at the third failed gate |
| What the Chair reads | The diff and the gate outputs | The one line and `council patch show <n>`: the head and what the checks found |
| A fix round | The Chair, with everything it has read so far | A fresh builder, with the pack and the task's history (`patches/T<n>.md`) |
| The verifier | Unchanged | Unchanged. It may be on any model that is not below the builder's |
| A build of one small task | The Chair | The Chair still, when the size proposal says Solo: a fresh agent would cost more than the change |

**In code, not in prose.**

- A build seat (`task-<n>`) is a seat like any other: `council seat task-<n> running` is refused
  while another build seat is running, and for a task that depends on a task stopped by
  `NEEDS: fix` until the user's ruling is on record. The proposal called the seat `build-<n>`; the
  user chose `task-<n>` on 2026-11-16, the word `council tree` and the task-word reader already match.
- The helper already keeps the tree at the end of each saved round. When a build seat starts, a
  tree that differs from the last saved round is named, file by file: someone edited outside a
  round. That is how a Chair that "just fixes it" shows, with no new hook on every edit.
- The seat gate covers the builder as it covers a worker: no report file, no stop.
- The builder's contract is a new agent file with the edit tools a worker does not have. The loop's
  text moves out of the implement skill, which is at its size cap, into a reference the builder
  reads; the skill keeps the Chair's part.

**What it costs.** The total tokens of a build will probably not fall: each builder reads the code
it needs again. The gain is elsewhere: the Chair's window stays small through a long build, the
builders and the verifier can run on a cheaper model than the session, and the builder's report is
checked by someone who did not write it. So the estimate of a build is measured again from the
ledger before the default changes (the `- estimates:` line, edited by hand since D40).

**How we would know.** Scenarios for each refusal above, and the planted cases of T4. Then the
build benchmark (`evals/bench.py`) run both ways on the same cases, the Chair building against a
builder agent: tokens by role, hidden checks passed, false completion claims. The benchmark has
never been run for a result; this is the first question it should answer.

**Not in this step.** Parallel builders and a lead seat to merge them (#63) stay held. One builder
at a time has nothing to merge.

**The decision it changes.** D4 said only the Chair of council-implement edits project code. D42
supersedes that clause: one builder at a time edits project code, a builder agent or, for a Solo
build, the Chair. The same entry changes D37: the Chair counts as a builder only in a Solo build.

## How we would know it works

Behaviour is proved by running it (D25), so each part ships with planted cases in the Chair drill
eval (#70):

- a fix that wraps a race in a retry: the workaround sign is raised and the verifier returns
  INCOMPLETE;
- a builder that deletes a failing test and reports `Removed: none`: refused;
- a task resting on a false assumption about a tool: the probe leaf runs first and the plan changes;
- a task whose build calls a function in the repo that returns a wrong value: the builder returns
  `NEEDS: fix` naming it, nothing in its slice handles the wrong value, and the Chair stops the
  tasks that rest on it;
- the same task, built around the wrong value with the Done-when met: the verifier returns INCOMPLETE
  and names the function;
- a task with no part of the request to serve: refused at the plan check;
- a resumed run: the Chair's next step from `council tree` alone matches the step from full context.

And two measurements over real runs, from the ledger: tokens per builder with a pack against a
hand-written brief, and post-game findings per run before and after.

## What this does not do

- It does not judge taste. Whether a design is good stays with the plan's experts and the user.
- It adds no checker agents and no verdict words for the verifier. T5 adds one agent, the builder.
- The workaround signs are a list of patterns. They miss what they don't name, and the verifier's
  question is the real check.

## Where it lands

| Step | What | After | Rough size |
|---|---|---|---|
| T1 | Task fields (`Serves`, `Owner`, `Rests on`), the plan check for them, `NEEDS:` and the unknown-becomes-a-leaf rules (#64); the owner row or `New way:`, and the verifier's decision question (#93) | S5 (the plan check in Python) | ~700–900k |
| T2 | The report head with `Cause` and `Removed`, the saved diff and the checks on it (#58, #59), the third-round refusal (#50), the task history (#60) | S7 (`check` in Python) | ~1M |
| T3 | The generated task pack (#57, #61, #67), `council tree`; setup proposes the project's recorded decisions and fills the map's one-way-per-job table (#93); the `NEEDS: fix` stop, the Chair's rule for it, the verifier's question on every round and the two signs | T1, S8 and S11 | ~0.9–1.1M |
| T5 | A fresh builder per task (section 6): the builder's contract, the build seat and its refusals, the tree check, the implement skill's loop moved to a reference, the entry that supersedes D4's last clause (D42). Built with it: the revert check, the receipt lines the helper writes, the verifier's "exists, not a stub, wired in" question, `council patch apply` and `revert`, and the benchmark's Chair-against-builder arms | T3 (it needs the pack) | ~1–1.5M |
| T4 | The planted drill cases, with the two for a bug underneath and the builder's | S10 (#70) | part of S10 |

## Decided by the user (2026-11-13)

1. **`Serves:` on every task.** Yes. The plan check refuses a task without it. A support task (a
   test, a changelog line) quotes the part of the request its parent task serves.
2. **A workaround with no better fix.** The user rules each time. The Chair brings it with the cause
   and what was tried, in the one question at Deliver, and the answer is recorded as a decision so
   the same workaround is not asked about twice. The Chair never ships one on its own call.
3. **A builder's `NEEDS:`.** The Chair may run one probe or research seat a run inside the approved
   budget without asking, and asks before a second.

4. **The project's own architectural decisions (#93).** Yes, folded into T1 and T3:
   - At setup, `council-init` reads the project's decision records and architecture docs. Each
     decision it finds becomes a proposed memory entry, citing its source, for the user to accept.
   - The map gains a one-way-per-job table: the job, the owner, the one way it is done, and an
     anchor path. A task's `Owner:` names a row of it, or the task says `New way:`.
   - The verifier asks whether a change contradicts a recorded decision or adds a second way. If it
     does, the verdict is INCOMPLETE.
   - A map without the table skips the owner check, so older projects keep working.

5. **A bug underneath a task (2026-11-15).** The Chair always asks, in one line with the cost. It
   never fixes code outside the plan, and never ships the workaround, on its own call. A small fix
   inside the approved budget is asked about too.

6. **A fresh builder per task (2026-11-15).** The user said to plan it; the plan is section 6. A
   Solo build stays with the Chair (the user, 2026-11-15): one small task fills no window, so a
   builder agent would cost a pack and a start for nothing. One part is still a proposal: a fix
   round gets a fresh builder, not the same agent continued. T5 measures both ways before it is
   settled. On 2026-11-16 the user approved D42 as the entry, chose `task-<n>` for the build seat, and
   set the benchmark as a pilot after T5 merges, on their go.

## Until it is built: the cleanup's own sessions

The cleanup runs on session briefs written by hand, so the same two rules apply to them now:

- every brief carries the request line in the user's words and names the state of the tree the
  work is judged against;
- every report lists what it removed and, for a fix, its cause; the planning session checks both
  against the diff before it relays anything;
- an agent that finds a fault in code it builds on (another agent's file, the shared base) stops
  and reports it. The planning session fixes the base and starts the agent again. No brief says
  "work around it in your own files": the S8b and S9 brief did, and the integrator then had to fold
  those workarounds.
