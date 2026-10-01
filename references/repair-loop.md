# Repair loop — Phase 7

This is a bounded aid for `council-implement`, not an automatic coding agent. The Chair remains the
only code writer. `council repair` reads a gate that **already ran**; it never runs a command,
dispatches a worker, changes code, or claims that the current edit caused a failure.

## One task, one gate, at most three failed attempts

In a build, `council gate <name>` records each failure itself as an attempt on the task `next:` names
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
| Second | One independent, read-only diagnosis worker gets the task, both saved attempts, baseline and diff. The Chair chooses the fix. If this task already used its one diagnosis worker for verifier trouble, stop instead. |
| Third | Stop product-code mutation and report the blocker and remaining uncertainty. No fourth automatic attempt. |

Once a trail records its third failure, `council gate <that gate>` refuses to run it and says what to
do: tell the user what failed and what is left, and ask how to go on. Only on their go, in their own
words, `council repair allow <gate> --user-said "<their words>"` records it (`repair-allowances.tsv`,
and a `repair.allowed` event); the gate then runs again. The stopped trail stays closed, so a new
failure goes under the new task id the gate names (`T2-2`). `gate --all` skips it, named and counted.

The third failure stops the build, not just this gate. Do not start later tasks or continue to the
after-evidence step, a verifier's fix path, another gate-repair trail, or a success commit for the
same task. A read-only review may describe the stopped state; it must not authorize another fix.
The Chair may still write the run log, check the saved repair trail, and give the receipt. Mark the
task **blocked**, even if some requested behavior was implemented. A mandatory gate that remains
red cannot support a "built" claim. Preserve the attempted diff and evidence for the user; do not
automatically discard task changes or unrelated work to manufacture a green tree. If a known
regression remains, name it and leave the result unmerged for a user decision about repair or
rollback.

A successful, nonempty rerun closes the task's repair trail. A passing gate with zero files matched,
or one whose output says no test ran, does not close it. A gate run can only be recorded once, using its `gate.finished` event sequence;
repeat the actual gate after a change rather than re-recording old output. The helper refuses to
record a different gate under the same task or to reopen a stopped/resolved trail. If several gates
fail, address them deliberately as distinct task/gate trails or explain the dependency in the log.

The ledger is `<run>/repairs.jsonl`; each attempt has immutable-by-convention gate verdict and
output snapshots under `<run>/repairs/`. `check` detects changed snapshots. These are local run
artifacts, not a substitute for the tracked implementation log. Add the classification, route,
attempt count, actual cause found, and any human ruling to the log. Never infer that a baseline-red
failure was introduced by the task; the record says `baseline: red`, `empty`, or `unknown`, not
“regression.” An exit-zero baseline that checked zero files is `empty`, not green.
The helper accepts artifacts up to 4 MB; if a gate writes more, keep its original output and record
the failure and retry limit manually in the log instead of claiming the helper captured it.

## Classification and routing

The helper uses explicit text patterns, then a gate-name hint, to suggest a category and governing
reference lens. Possible categories include test, type, lint, build, runtime, data, schema,
concurrency, configuration, environment, performance and `UNKNOWN`. The signal line is saved with
the suggestion. It is **advisory**: output may mention a symptom rather than the cause. The Chair
checks the code and baseline, chooses an existing project seat or the task's governing expert, and
may override the suggestion in the log. A missing roster seat does not license a new dispatch.
Test/lint suggest the testing lens; data/schema the data-integrity lens; concurrency its own lens;
environment/configuration/build the operability lens; type/runtime the backend lens; performance
its own lens. `UNKNOWN` falls back to the task's governing reference. These are starting points,
not automatic seat selection—for example, a frontend type error may belong with the frontend seat.
An environment or credential failure does not justify changing product code. A side-effectful gate
still requires the project's existing approval before it is run by name.

Verifier `INCOMPLETE` and `REGRESSION` verdicts keep the build mode's existing separate three-try
protocol: two failed verifications trigger independent diagnosis; one more failure stops. Do not
count verifier rows as gate executions or make a machine category from their prose. Both trails
belong in the implementation log and final receipt.

Python 3.8+ is optional. Without it, keep the same three-attempt bound and save the gate paths and
diagnosis in the implementation log manually. Existing runs need no migration.
