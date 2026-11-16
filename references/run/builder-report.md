# The builder's report and its saved round

A report is a claim; nothing used to check it against the diff. Each round of a build task (the first
build, then each fix) ends with a report whose head the helper reads, and with that round's diff saved
beside it. `council patch save <n>` checks one against the other before the verifier sees either
(`docs/design/task-tree.md`, section 3; D38). The builder is a builder agent on seat `task-<n>`, or the Chair in a Solo build (D42).

## The head

`<run>/report-<n>.md` (or the file named after the task number), rewritten each round. Its first lines,
after an optional `# ` title, are the head; prose below it is the builder's own and the helper never
reads it:

```
Cause: <for a fix: what was wrong, in one sentence> · state: OBSERVED|REPRODUCED
Owner: <where the change was made>
Removed: <each rule, behaviour, test or assertion taken out, and where it stands now> | none
Assumed: <what it relied on without checking> | nothing
Redesign: <what the design changes, and why the patches failed>      (a third fix round only)
```

- **Cause** is `none` only on a task's first build. Every later round is a fix and names its cause,
  with its evidence state (`references/run/evidence-model.md`). A review fix names the finding's cause.
- **Removed** names each removal by its file (a test by its name too) and says where it stands now:
  moved, replaced, or gone and why. `none` means none.
- A head that is missing, out of order, or gives a cause no state it can read is refused.

## When the builder stops instead

A builder that cannot finish a round with a true report returns one line and writes no round:
`NEEDS: <question>`, or, when the code under its task is wrong,
`NEEDS: fix <file:line> · does: <…> · should: <…> · seen: <the command or test, and its output>`
(repair-loop.md, Unknowns, says when each applies and how it is recorded). It never makes up for that
code inside its slice to reach a met Done-when: on every round the verifier asks whether an added
line exists only to do that.

## What `council patch save` checks

It takes the round's diff: from the run's last saved round (the first: the commit the run opened on,
or `--base <rev>`) to the files on disk now, `.council/` and what git ignores left out. Then:

| Check | Found | Result |
|---|---|---|
| Cause | a fix with `Cause: none`; a cause `INFERRED`, `ASSUMED` or `UNVERIFIED` with code changed | refused: measure it first (repair-loop.md, Unknowns), or return `NEEDS:` |
| Removed | a deleted test file; a removed test, assertion or document rule (a line with never, always, must, only …) whose words were not added back anywhere in the round; the head's Removed line doesn't name it | refused: name it, or put it back |
| Third fix round | repair-loop.md, Fix rounds | refused until the redesign is ruled |
| Owner | a changed file outside the task's slice: the paths in its plan task's Owner and Touches, and the map row its Owner names (the plan is the run's `input=`) | flagged for the verifier as possible scope creep; skipped, in one line, with no plan or no path |
| Workaround signs | an added line of code that retries, sleeps, catches everything, skips a test, sets a time limit or loosens an expected value; says workaround, hack, temporary, "for now" or "until … is fixed"; or adds a `TODO`, `FIXME` or `XXX`; or an assertion changed in place | listed for the verifier as questions, never verdicts: some are right |

A refused round saves nothing, so it keeps its number. The signs are patterns: they miss what they
don't name, and the verifier's question below is the real check.

## What it saves

Under `<run>/patches/`: `T<n>-<r>.patch` (the round's diff), `T<n>-<r>.json` (its record: the head,
the two trees, the files, what the checks found) and `T<n>.md`, the task's history across its rounds,
rewritten at each save.
`council patch show <n>` prints it. `council patch revert <n> [--round <r>]` takes a saved round off the
code root's files and `council patch apply <n> [--round <r>]` puts it back (the task's last round unless
`--round` names one): all or nothing, refused with nothing changed when it won't go cleanly. They change
files only; no record goes, and the next `council patch save` diffs from the last saved round as before.

- **The verifier** gets the round's patch and the history, never the report's prose: they hold the
  head and the checks, not the reasoning. For a fix it asks one more question (`build-proof.md`,
  Checking).
- **A fix round's brief** links the history, so the builder knows what was tried, what each round
  changed and where the same files came back.
