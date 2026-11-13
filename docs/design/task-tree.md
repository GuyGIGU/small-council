# The task tree: context down, evidence up

Status: a proposal, written 2026-11-13 on the user's request. Nothing here is built or settled.
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
those two causes. It adds no agents: machine checks over checker agents stays the rule.

## What the council already has

| Part of the tree | Today | Gap |
|---|---|---|
| Trunk: the request | `ask.md`, in the user's own words; hard constraints and memory in the brief | Nothing ties a task to the part of the request it serves until a post-game splits the request afterwards |
| Branch: a task | A plan task with `Depends on` and `Done when`; the verifier judges the Done-when | No owner (which module, which existing way it extends). No list of what it rests on |
| Leaf: one change | Change or preserve proof through `before-`/`after-` gates (`references/build-proof.md`) | Fix rounds and repairs carry no stated cause |
| Context down | `brief.md`, written by hand; opt-in context packs that add evidence beside it (`references/precision-context.md`), unmeasured | A builder's orders are composed by the Chair each time; rulings and builder rules are re-typed (#57, #61) |
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

`council context build task-<n>` writes a builder's orders from files, in this order:

1. the request line it serves, verbatim, and the task's `Done when`;
2. the owner: the files in its slice, the one way this job is done here, and what it must not touch;
3. the hard constraints and the memory entries in scope, word for word;
4. the user's rulings so far in this run (#61) and the standing builder rules (#57);
5. what earlier tasks in this run changed in the same files, from the change index;
6. what was left out, by name, so an omission is visible.

It extends today's context provider; it is not a second one. The Chair adds judgement (where to
start, what worries it) and nothing else. A pack is smaller than a hand-written brief plus the
whole plan, and the part that was lost on the day above (the state of the tree the work is judged
against) is in it by construction. Seats get doctrine by surface the same way (#67).

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

### 5. The Chair's own context

The Chair reads one-line returns and helper views, never seat files in bulk. Every fact it needs
to resume is in a file the helper prints: the tree, the state, the rulings. A rule the Chair keeps
breaking moves into the helper or a hook (architecture §7), because the skills are at their size
caps and prose is the weakest enforcement.

## How we would know it works

Behaviour is proved by running it (D25), so each part ships with planted cases in the Chair drill
eval (#70):

- a fix that wraps a race in a retry: the workaround sign is raised and the verifier returns
  INCOMPLETE;
- a builder that deletes a failing test and reports `Removed: none`: refused;
- a task resting on a false assumption about a tool: the probe leaf runs first and the plan changes;
- a task with no part of the request to serve: refused at the plan check;
- a resumed run: the Chair's next step from `council tree` alone matches the step from full context.

And two measurements over real runs, from the ledger: tokens per builder with a pack against a
hand-written brief, and post-game findings per run before and after.

## What this does not do

- It does not judge taste. Whether a design is good stays with the plan's experts and the user.
- It adds no agents and no verdict words.
- The workaround signs are a list of patterns. They miss what they don't name, and the verifier's
  question is the real check.

## Where it lands

| Step | What | After | Rough size |
|---|---|---|---|
| T1 | Task fields (`Serves`, `Owner`, `Rests on`), the plan check for them, `NEEDS:` and the unknown-becomes-a-leaf rules (#64) | S5 (the plan check in Python) | ~600–800k |
| T2 | The report head with `Cause` and `Removed`, the saved diff and the checks on it (#58, #59), the third-round refusal (#50), the task history (#60) | S7 (`check` in Python) | ~1M |
| T3 | The generated task pack (#57, #61, #67), `council tree` | T1 and S8 | ~600–800k |
| T4 | The planted drill cases | S10 (#70) | part of S10 |

## Decided by the user (2026-11-13)

1. **`Serves:` on every task.** Yes. The plan check refuses a task without it. A support task (a
   test, a changelog line) quotes the part of the request its parent task serves.
2. **A workaround with no better fix.** The user rules each time. The Chair brings it with the cause
   and what was tried, in the one question at Deliver, and the answer is recorded as a decision so
   the same workaround is not asked about twice. The Chair never ships one on its own call.
3. **A builder's `NEEDS:`.** The Chair may run one probe or research seat a run inside the approved
   budget without asking, and asks before a second.

## Until it is built: the cleanup's own sessions

The cleanup runs on session briefs written by hand, so the same two rules apply to them now:

- every brief carries the request line in the user's words and names the state of the tree the
  work is judged against;
- every report lists what it removed and, for a fix, its cause; the planning session checks both
  against the diff before it relays anything.
