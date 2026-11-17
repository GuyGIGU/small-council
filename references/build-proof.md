# Build proof

Choose the proof mode before editing product code. It describes what the task must establish,
not which result is easiest to obtain. The verifier checks that choice against the Done-when.

## Choose the mode

- **Change** (default): a bug fix or new behaviour. A relevant check must fail on the original
  code for the intended reason and pass after the change. Inspect the failure: a missing tool,
  syntax error in the test or unrelated red baseline does not reproduce the problem.
- **Preserve**: a refactor whose Done-when requires the same externally observable behaviour.
  Record the invariants, the affected path and why no behaviour change is intended before editing.
  An adequate existing test may prove those invariants by passing on both versions. Do not weaken
  assertions, remove cases or change expected behaviour to obtain the second pass.

A task that mixes a refactor with a fix or new behaviour needs change proof for the changed
behaviour. Split its evidence when that helps; a passing preservation check cannot prove a fix.
Guardrails tasks retain their deliberate-violation proof from `references/guardrails.md`.

Use a test in the project's own suite, named by its file path in the command. Add a test only when
existing coverage cannot exercise the relevant path. With no test runner, use a repeatable command
or query and disclose that no permanent test was kept. When no permanent test is possible, record
`no permanent test possible - <why>` and what was inspected or run; disclose the remaining gap.

**Prove it through the entry point that ships.** A proof that runs only scripts kept in the run
folder (`.council/runs/…`) never ran what a person runs: a real build proved a time bound through its
own helper script and never through the project's check, and a review found what it missed. At least
one proof of each task runs the command a person would run — the project's own test, check or
script — and the log names that command. A run-folder harness may add evidence beside it, never
replace it. `council check` notes a task whose proofs ran only run-folder scripts.

## Before you spend a gate run

Read a new check, probe or harness edit back, then compile it with the cheapest check that parses it
(`bash -n`, `python -m py_compile`, the compiler's type check) before a full gate run. A real build
lost three before-runs to compile errors in its own new check, and one probe comment cut a line short
and deleted a folder. Run one gate per Bash call: each has a time limit, and a gate past it is
stopped and recorded as `TIMED OUT` (`council gate <name> --timeout <time>` when it truly needs
longer).

## Record the pair

Change proof keeps the existing commands and default behaviour:

```bash
council gate before-1 -- 'pytest tests/test_expiry.py::test_expired_token'
# Implement the change.
council gate after-1 -- 'pytest tests/test_expiry.py::test_expired_token'
```

For preservation, declare the mode on both gates:

```bash
council gate before-2 --proof preserve -- 'pytest tests/test_export.py'
# Refactor without changing the tested behaviour.
council gate after-2 --proof preserve -- 'pytest tests/test_export.py'
```

`--proof change` makes the default explicit. The flag takes a `before-<id>` or `after-<id>` gate in
a council-implement run, where the id is the task's number (`before-3`); it does not apply to
configured gate sets or `regress-<n>` fixes.
The helper writes the mode in each gate's JSON verdict. Old verdicts without it remain change proof.
Always quote the whole command after `--`, so pipes, `&&` and nested quotes reach the gate intact.
The command must be identical in both records. Keep both output files and cite them in the task log.
For preservation both outputs must contain an observation, not just whitespace; a normally silent
assertion or query should print its checked result after succeeding. No tests selected is not proof.
Before/after checks are proof records, excluded from automatic gate-repair attempts.

**A red that proves nothing is no proof yet.** When a before-check failed for the wrong reason — the
new test didn't compile, the probe was broken — mark it rather than let it count:
`council gate before-1 --invalid "the new test didn't compile"`. Nothing runs; its record says why.
Fix the check, compile it, and run `before-1` again; the fresh record replaces the marked one. A
before-check stopped at its time limit, or whose command was never found (exit 127), is read the
same way without marking.

## Tiers

The config's run preferences say how much proof a build records: `- build tier: light` or
`- build tier: full`. A missing line reads as light.

- **Light** (the default): a before/after pair is required for a **risky** task — a P1 fix, a data
  write, security, core logic, a public contract, or a task the plan marks risky — and for any task
  that adds a test anyway. An ordinary task proves itself by its gates passing after the change and
  by the converge check; its Converge Proof reads `light: gates only`.
- **Full**: every task records a pair.

How many verifiers check those proofs is the next section's setting, not the tier's.

`council check` prints the tier it read at the end of its proof summary line and writes it into
`check.md`, so the receipt carries it.
The tier changes how much is proved, never what counts as proof: under light, a risky task without
its pair is still NO PROOF, and the verifier's brief names the task's risk class, read from the plan,
so a builder cannot call a risky task ordinary.

## Checking

The config's run preferences say how many checker agents a build dispatches:
`- checking: one per batch` or `- checking: per task`. A missing line reads as one per batch. A batch
is one council-implement run.

- **One per batch** (the default): builders build every task, and the machine gates (and, for a
  risky task, its before/after pair) prove each one as it lands. A single verifier runs once, at the
  end: the converge check of every Done-when against the final tree. No verifier per task. The agent
  gate refuses a second verifier in the same run until the user's go is on record
  (`council state decision="…"`) after the last one; resuming a verifier stopped at its turn limit
  (SendMessage) is not a second one. A Workflow whose script starts council verifiers counts as one
  more; a saved workflow called by name can't be read, so the Chair holds it to the rule by hand.
- **Per task**: a verifier for every P1 fix and every risky task on its own, and one per batch of
  ordinary tasks — up to five under light, two or three under full, up to five of one kind (renames,
  copy edits) — plus the converge check.

Either way the checker judges the Done-when and nothing wider: it tries hard to show each Done-when
is not met, and anything it notices beyond one is a line with its reach today, never a verdict or a
new task. It never hunts past it for a narrower gap (a test helper, a check script, a route the task
never named). A brief that sends it hunting ("however narrow", "any route", "find anything else") is
refused at dispatch. Real runs show why: a verifier told to name any route that still gets through
found a narrower gap every round, and one batch's checks ran about ten hours and 1.7M tokens.

**The cause, not the symptom.** On a fix the checker also asks whether the change removes the cause or
hides the symptom: a retry around a race, a sleep, a caught-and-dropped error, a skipped test, a
longer time limit or a looser expected value can make the failure stop showing while its cause stays.
A change that hides it is INCOMPLETE, with the reason, even when the Done-when reads met. The round's
saved history (`patches/T<n>.md`, `references/run/builder-report.md`) lists the lines that look like a
workaround, and the files changed outside the task's slice: each is a question to settle by reading
the code, never a verdict on its own, since some are right.

**Decisions and one way.** On a build or a fix the checker also asks whether the change contradicts a
recorded decision (the memory D and EC entries in scope, quoted in the brief) or adds a second way of
doing a job beside a row of the `## One way per job` table in the council home's `map.md`: a second
error type, config reader or data-access path beside the row's. If it does, the verdict is INCOMPLETE,
citing the entry id or the table row, even when the Done-when is met. A new way the user ruled on is a
recorded decision itself, so it is no second way.

**Making up for other code.** On every round, a first build too, the checker also asks whether any
added line exists only to make up for other code in this repo: a guard, a conversion, a retry or a
special case that answers a bug in the code the task builds on instead of doing the task. If so, it
names that code (`path:line`) and the verdict is INCOMPLETE, even when the Done-when is met, unless
the user ruled that workaround (a recorded decision, quoted in the brief). The builder's way out is
the stop, `NEEDS: fix …` (`references/run/repair-loop.md`, Unknowns). The history's
`workaround words` and `todo` signs point at such lines; like every sign, they are questions, not
verdicts.

**Exists, not a stub, wired in.** For each thing the Done-when names (a function, a command, a
route, a setting), the checker also asks three things: it is in the tree; its body does the work (no
placeholder return, no empty or TODO body, no answer hard-coded to fit the test); and a path from an
entry point that ships reaches it, the chain cited (`path:line` to `path:line`). Missing or a stub is
INCOMPLETE; present but called by nothing is INCOMPLETE, naming where it should be wired in. Like the
other questions it asks only of what the Done-when names, never wider.

## Read the result

`council check` checks the saved before/after gates against their declared proof mode and names the
saved test when it can. It writes each task's verdict and note to `check.md`. Copy both into the log's Converge
Proof cell; a saved test note establishes its file exists, not that its assertions are adequate.

| Verdict | Meaning |
|---|---|
| `ok` | The change check failed before and passed after, with the same command. |
| `preserved` | The explicitly declared preservation check passed on both versions. |
| `BEFORE-PASSED` | Change proof never demonstrated the problem or missing behaviour. |
| `BEFORE-FAILED` | Preservation proof was already red before the refactor. |
| `AFTER-FAILED` | The after-check did not pass. |
| `DIFFERENT-COMMAND` | The pair used different commands, or preservation lacks a command. |
| `DIFFERENT-PROOF` | The pair declares different modes; an after-only declaration cannot relabel the before-check. |
| `INVALID-PROOF` | The recorded mode is unsupported or a regression fix was labelled preservation. |
| `MISSING-OUTPUT` | Preservation has no saved output for one side of the pair. |
| `NOTHING-RAN` | Preservation output is blank or says no tests ran or no files matched. |
| `NO-BEFORE` / `NO-AFTER` | One side of the pair is missing. |
| `NO-PROOF-YET` | The before-check's red proves nothing: marked invalid, stopped at its time limit, or never ran (exit 127). Run it again. |
| `REVERT-PASSED` | The change check still passes with the task's saved rounds taken off: it does not show the change. Make it fail without the change, then run the pair and `council check` again. |

**The revert check.** For each change proof that reads `ok`, of a task with saved rounds
(`council patch save`), `council check` runs the check once more without the change. It writes the
files on disk (what `git` tracks or could, as git holds them; `.council/` and ignored files left out)
to a scratch folder outside the project and the run folder, and runs the after-check's recorded
command there under the gate time limit, first with the change still on: the control. It must pass
there; if it doesn't, the check needs files the copy leaves out, and nothing more is tried. Then the
task's rounds come off, newest first, with the same reverse-apply as `council patch revert`, and the
command runs again. The task's test files stay as they are when its rounds come off: the round that
added or extended the test is the same round as the fix, and taking the test off with it would run an
older test, or none, instead of the one that proved the change. The scratch folder is removed
afterwards; the project's files never change. The outputs are kept as
`gates/reverted/after-<n>-with-change.txt` (the control) and `gates/reverted/after-<n>.txt`.

- It fails with the rounds off: the proof stands, and the row says so.
- It still passes: `REVERT-PASSED`, a broken proof, and `council check` exits 1.
- It can't be made: the control doesn't pass in the copy, a round doesn't come off the files on disk
  cleanly, the files can't be copied, the command runs files under `.council/`, or a run timed out,
  never ran or ran no test. The row says why, and it is neither a pass nor a problem: it goes under
  `Not proved:`.

A preservation proof, a proof that is not `ok` and a task with no saved round are not rerun.

The verifier never takes a helper verdict or a saved test path as semantic proof: it traces the named
invariants through the changed path, inspects test assertion changes and reads the actual
before-failure. Preservation alone never earns OK for a fix or new behaviour.
For preservation the verifier also traces the affected path, checks that the tests cover the named
invariants and inspects assertion changes. A passing pair establishes only those checked invariants;
it is not proof that every possible behaviour was preserved. Report any uncovered requirement.
The helper compares recorded modes, commands, exits and outputs, and the revert check shows whether
a change check needs the task's change to pass: one that still passes without it is `REVERT-PASSED`.
It still cannot tell whether a red failed for the intended reason, whether the test exercises the path
the Done-when names, or whether assertions were weakened; a revert check not made shows nothing. The
independent verifier must inspect those facts before a task counts as built. Missing-tool,
collection or test-syntax failures earn CANNOT VERIFY, not proof of changed product behaviour.
Missing proof earns CANNOT VERIFY; code that establishes an unmet Done-when earns INCOMPLETE.

## The receipt lines

On a build, `council check` prints three lines just before its closing `check:` line and writes them into
`check.md`, composed only from the records: the gate records (`gates/`, and the baseline under
`gates/baseline/`), the proofs, the revert checks and the user's decisions in the run's state. The
Chair copies them into the receipt as they are; it writes none of them.

```
Checked by machine: <each gate: its baseline result → its result now> | <the helper's NOTHING WAS CHECKED words>
Not proved: <what the records show nobody checked> | nothing
Your decisions: <each `council state decision=` entry, oldest first, a task's after `task <n>: `> | none
```

`Checked by machine:` names each gate that checks the work (the proof pairs and probes are not gates
here): `unit: FAIL → pass · lint: no baseline → pass`. With no gate on record it quotes the helper's
NOTHING WAS CHECKED words. `Not proved:` lists a task of the plan with no proof pair, or a pair missing a
side or reading `NO-PROOF-YET`; a configured gate never run; a gate that timed out, never ran, was marked
invalid or passed with nothing run; a gate whose recorded tree is not the files on disk now; and a revert
check that could not be made. `Your decisions:` is the user's words on record, never the Chair's
`Ruling:` lines. Same records, same lines. A run that is not a build prints none of them.
A gate `gate --all` did not run because nothing under its `Covers` paths changed since its green is
never a fresh pass: it reads `pass → pass (not rerun)`, and `Not proved:` gives the reason. A PR body
drafted for the run carries that `Not proved:` line as it is.
