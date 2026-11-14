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
a council-implement run, where the id is the task's number or a slug of letters, digits, dashes and
underscores (a builder's name, such as `before-b7-flip`); it does not apply to configured gate sets
or `regress-<n>` fixes.
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
new task. A brief that sends it hunting ("however narrow", "any route", "find anything else") is
refused at dispatch. Real runs show why: a verifier told to name any route that still gets through
found a narrower gap every round, and one batch's checks ran about ten hours and 1.7M tokens.

**Decisions and one way.** On a build or a fix the checker also asks whether the change contradicts a
recorded decision (the memory D and EC entries in scope, quoted in the brief) or adds a second way of
doing a job beside a row of the `## One way per job` table in the council home's `map.md`: a second
error type, config reader or data-access path beside the row's. If it does, the verdict is INCOMPLETE,
citing the entry id or the table row, even when the Done-when is met. A new way the user ruled on is a
recorded decision itself, so it is no second way.

## Read the result

`council check` writes each task's verdict and note to `check.md`. Copy both into the log's Converge
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

The verifier never takes a helper verdict or a saved test path as semantic proof: it traces the named
invariants through the changed path, inspects test assertion changes and reads the actual
before-failure. Preservation alone never earns OK for a fix or new behaviour.
For preservation the verifier also traces the affected path, checks that the tests cover the named
invariants and inspects assertion changes. A passing pair establishes only those checked invariants;
it is not proof that every possible behaviour was preserved. Report any uncovered requirement.
The helper compares recorded modes, commands, exits and outputs; it cannot tell whether a red
change check failed for the intended reason, a test exercises the path, or assertions were weakened.
The independent verifier must inspect those facts before a task counts as built. Missing-tool,
collection or test-syntax failures earn CANNOT VERIFY, not proof of changed product behaviour.
