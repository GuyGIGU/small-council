# Repair loop — Phase 7

This is a bounded aid for `council-implement`, not an automatic coding agent. One builder at a time
writes code: a builder agent per task, or the Chair in a Solo build (D42). `council repair` reads a
gate that **already ran**; it never runs a command, dispatches a worker, changes code, or claims that
the current edit caused a failure.

## One task, one gate, at most three failed attempts

In a build, `council gate <name>` records each failure itself as an attempt on the task whose build seat `task-<n>` is running, else the task `next:` names
(`task <n>: …` — `phase=build` sets task 1, the Chair the next one after each receipt); with no task id
it says the attempt was not counted, and why. A pass closes the trail. `council repair record
<task-id> <gate-name>` is for a result recorded any other way; for one the gate recorded it says so
and changes nothing. Inspect the saved output and the baseline before acting.
After a repair, run the **same** gate again: its result is recorded the same way.
The intentionally red `before-<n>` proof is never an attempt, nor is `regress-<n>` — a review fix's new
check run on the version the verifier saw, red by design (the card treats both as proofs, never failing
checks). `gate --all` records no attempts: it skips
a stopped gate and closes an open trail when the gate passes. `council repair show [task-id]` displays the trail; `council repair check [task-id]`
checks that saved snapshots still match it.

| Failed execution | Next step |
|---|---|
| First | Original builder investigates the output and the governing reference. |
| Second | The builder investigates again, from the saved output and the baseline; it starts no agent. In a Solo build the Chair may dispatch one diagnosis worker (below) first, unless the task already used it for verifier trouble. |
| Third | Stop product-code mutation and report the blocker and remaining uncertainty. No fourth automatic attempt. |

Once a trail records its third failure, `council gate <that gate>` refuses to run it and says what to
do: tell the user what failed and what is left, and ask how to go on. Only on their go, in their own
words, `council repair allow <gate> --user-said "<their words>"` records it (`repair-allowances.tsv`,
and a `repair.allowed` event); the gate then runs again. The stopped trail stays closed, so a new
failure goes under the new task id the gate names (`T2-2`). `gate --all` skips it, named and counted.

The third failure stops the build, not just this gate. Do not start later tasks or continue to the
after-evidence step, a verifier's fix path, another gate-repair trail, or a success commit for the
same task. A read-only review may describe the stopped state; it cannot reopen repair or authorize another fix.
The Chair may still write the run log, check the saved repair trail, and give the receipt. Mark the
task **blocked**, even if some requested behavior was implemented. A mandatory gate that remains
red cannot support a "built" claim. Preserve the attempted diff and the gate output for the user;
never silently revert unrelated work, nor discard task changes to manufacture a green tree. If a known
regression remains, name it and leave the result unmerged for a user decision about repair or
rollback.

A successful, nonempty rerun closes the task's repair trail. A passing gate with zero files matched,
or one whose output says no test ran, does not close it. A gate run can only be recorded once, using its `gate.finished` event sequence;
repeat the actual gate after a change rather than re-recording old output. The helper refuses to
record a different gate under the same task or to reopen a stopped/resolved trail. If several gates
fail, address them deliberately as distinct task/gate trails or explain the dependency in the log.

## The log

The ledger is `<run>/repairs.jsonl`; each attempt has immutable-by-convention gate verdict and
output snapshots under `<run>/repairs/`. `check` detects changed snapshots. These are local run
artifacts, not a substitute for the tracked implementation log. Add the classification, route,
attempt count, actual cause found, and any human ruling to the log. Include each failed gate
attempt's category, suggested lens, actual cause (or uncertainty), snapshot paths and next action.
`council repair check T<n>` checks saved snapshots when used. At converge, a broken saved repair
trail is reported, never folded into a green receipt.

Never infer that a baseline-red failure was introduced by the task; the record says `baseline: red`,
`empty`, or `unknown`, not “regression.” An exit-zero baseline that checked zero files is `empty`, not
green. For a gate red at baseline and waved through, `council gate <name>` names the tests failing
now that `gates/baseline/<name>.txt` didn't name. When it can't compare, read both outputs side by
side. The helper accepts artifacts up to 4 MB; if a gate writes more, keep its original output and
record the failure and retry limit manually in the log instead of claiming the helper captured it.

## Unknowns

"I don't know yet" is an accepted answer; a guess is not.

- **A failure nobody can explain stops code changes.** The next step is a probe that measures it
  (a gate, a script, a query whose output settles the question), then the fix. Guess-and-rerun is
  how a fix lands on a fix.
- **A builder may return `NEEDS: <question>` and stop.** That is a correct outcome, not a failed
  seat: record it `council seat <slug> done note="NEEDS: <question>"`, never `failed` or `blocked`.
  The Chair building a task in a Solo build stops the same way: the question, not a guess. It records
  the stop on the task's seat with `agents=0` (`council seat task-<n> done agents=0 note="NEEDS: …"`), as for its own
  seat: no agent ran, so the audit asks no token figure of it.
- **A bug underneath stops the task.** A builder that finds the code under its task wrong stops and
  returns `NEEDS: fix <file:line> · does: <…> · should: <…> · seen: <the command or test, and its output>`.
  Wrong means a `Rests on` fact that is false, or code that does not do what its owner's row, its
  tests or its own documentation say. It is the `NEEDS:` stop with a second kind of content, recorded
  the same way (`note="NEEDS: fix …"`), and a correct outcome. `seen:` is OBSERVED or REPRODUCED; a
  suspicion is a `NEEDS: <question>` and gets the probe. Never make up for the bug inside the task's
  slice: the verifier names such a line (`build-proof.md`, Checking). The Chair building a task in a
  Solo build stops the same way; what it stops and asks: council-implement, Edge cases. The stop is
  released when a decision of the user's is on record from its minute on: until then the helper refuses
  to start the stopped task and every task that depends on it. It is resolved when the stopped task's
  own `after-<n>` gate passes after the stop (an older pass, from before a fix round, does not count);
  `council tree` then shows its note as `was stopped: NEEDS: …`. The note
  ends when the seat has run again and is recorded `done` with no `note=`.
- **The answer.** The Chair may run one probe or research seat a run for it inside the approved budget,
  without asking; before a second, it asks the user. A question only the user can answer joins the
  rulings. A plan does the same ahead of time: a task resting on an unchecked fact outside the repo
  has a probe or research task before it (`references/run/run-plan.md`, Plan tasks).

## Fix rounds

The same stop, by files rather than by gate: patching one place over and over is how each fix
regresses another case. A task's rounds are its saved reports and diffs (`council patch save`,
`references/run/builder-report.md`): round 1 builds, each later round is a fix. A third fix round that
touches a file the two fix rounds before it both touched is refused, and the task goes back to the
plan as a redesign. Ask the user once, with what the patches tried and what each regressed
(`council patch show <n>`); only on their go, recorded with `council state decision="…"`, does a
round whose head carries `Redesign: <what the design changes, and why the patches failed>` save. The
redesign starts the count again, and the receipt names it.

## Classification and routing

The helper uses explicit text patterns, then a gate-name hint, to suggest a category and governing
reference lens. Possible categories include test, type, lint, build, runtime, data, schema,
concurrency, configuration, environment, performance, timeout (a gate the helper stopped at its time
limit) and `UNKNOWN`. The signal line is saved with
the suggestion. It is **advisory**: output may mention a symptom rather than the cause. The Chair
checks the code and baseline, chooses an existing project seat or the task's governing expert, and
may override the suggestion in the log. A suggestion does not license a new dispatch.
Test/lint suggest the testing lens; data/schema the data-integrity lens; concurrency and timeout
(a hang is most often a wait that never ends) the concurrency lens;
environment/configuration/build the operability lens; type/runtime the backend lens; performance
its own lens. `UNKNOWN` falls back to the task's governing reference. These are starting points,
not automatic seat selection—for example, a frontend type error may belong with the frontend seat.
An environment or credential failure does not justify changing product code. A side-effectful gate:
`builder-rules.md`, 9.

Verifier `INCOMPLETE` and `REGRESSION` verdicts keep the build loop's own protocol (council-implement,
step 7). Do not
count verifier rows as gate executions or make a machine category from their prose. Both trails
belong in the implementation log and final receipt.

## The diagnosis worker

A task gets one diagnosis worker, after a second failed verification (or, in a Solo build, a second
gate failure), whichever comes first. It is read-only, and its dispatch message is its whole brief: the task and its Done-when, the two failed
attempts (both saved gate outputs, or both verdict files), the baseline, the diff's path, and
`ref: none`. It writes `<run>/seats/diagnose-<n>.md`, an index of root-cause candidates
(`<n> · likely|possible · root cause · <path:line> · <title>`). Plan it as role `diagnosis`
(`council run plan check`), then `council seat diagnose-<n> …`. The Chair chooses the fix.
A third check is refused (by `council seat` and the agent gate) until a `diagnose-…` seat is on
record after the second verdict, or the user's go is (`council state decision="…"`).
