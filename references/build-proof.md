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

`--proof change` makes the default explicit. The flag takes a numeric `before-<n>` or `after-<n>`
gate in a council-implement run; it does not apply to configured gate sets or `regress-<n>` fixes.
The helper writes the mode in each gate's JSON verdict. Old verdicts without it remain change proof.
Always quote the whole command after `--`, so pipes, `&&` and nested quotes reach the gate intact.
The command must be identical in both records. Keep both output files and cite them in the task log.
For preservation both outputs must contain an observation, not just whitespace; a normally silent
assertion or query should print its checked result after succeeding. No tests selected is not proof.
Before/after checks are proof records, excluded from automatic gate-repair attempts.

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

For preservation the verifier also traces the affected path, checks that the tests cover the named
invariants and inspects assertion changes. A passing pair establishes only those checked invariants;
it is not proof that every possible behaviour was preserved. Report any uncovered requirement.
The helper compares recorded modes, commands, exits and outputs; it cannot tell whether a red
change check failed for the intended reason, a test exercises the path, or assertions were weakened.
The independent verifier must inspect those facts before a task counts as built. Missing-tool,
collection or test-syntax failures earn CANNOT VERIFY, not proof of changed product behaviour.
