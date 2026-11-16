# The build loop: one task, one round

The steps that build one task, for whoever builds it: a builder agent
(`small-council:council-builder`), one task in a clean window, or the Chair itself in a Solo build
(D42). One builder at a time. The Chair's part around these steps (the dispatch, the verifier, the
log, the state and the commit) is council-implement's build loop. The rules every task carries are
`builder-rules.md`; the round's report and what `council patch save` checks of it, `builder-report.md`.

Where a step says *log*, a builder agent writes it in its report, below the head, and the Chair
carries it into the run log. In a Solo build, write it in the log yourself.

1. **Load the task's orders and its governing reference doc first.** Your first command is
   `council context build task-<n> --run <run folder>`. It prints the orders, the doc's path among them.
   The Chair adds only judgement: where to start, what worries it (the dispatch's `Start:` line).
   Plugin references live under `${CLAUDE_PLUGIN_ROOT}`; project-local `.council/refs/…` under the
   council home.
2. **Before-evidence — choose proof for the task before editing.** Read
   `${CLAUDE_PLUGIN_ROOT}/references/build-proof.md`, the authoritative mode, coverage and pair
   contract — which tasks need a pair under the light tier (the default), compiling a new check
   first, `council gate before-<n>` and `--invalid` — and follow it. Log the mode and invariants.
   Label support with `references/run/evidence-model.md`; cite saved outputs for `REPRODUCED`.
3. **Plan the change:** files, minimal diff, governing principle, effects on later tasks, watchpoints.
4. **Implement.**
   - Match existing patterns.
   - Build what the task says, nothing more — no "while we're here".
   - Honour memory.
   - *The function least likely to cause a problem is the one that doesn't exist.*
5. **Gates for what you touched:** `council gate <name>`, judged by exit code.
   - **Never run a gate whose side effects involve cost, hardware, deploys or credentials** without
     asking the user first (`council gates` lists them). A builder agent asks with a `NEEDS:` return.
   - **Your change broke it** → fix it before moving on.
   - **A mandatory gate is red that was green at baseline** → hard stop until you understand why.
   - **Red at baseline and waved through** → carry on: check only that your change added no new
     failure (repair-loop.md, The log). The Chair keeps the standing clause on the receipt.
   - **It can't run** → config drift (02-prepare, Rules); log it too.
   - **It fails during this task** → the bounded loop in `references/run/repair-loop.md` (a failure
     nobody can explain, or a `NEEDS:`: its Unknowns): `council gate` records it
     (no `council repair record`); inspect its saved output and baseline, repair, and rerun the
     **same** gate. The third
     failed execution blocks the task: stop, do not go on to step 6 or any other fix, and return the
     `BLOCKED:` line below. The Chair logs the blocked task and gives the receipt.
6. **After-evidence — only if the task is not blocked.** First the report: `<run>/report-<n>.md`,
   its head first, then `council patch save <n>` (`references/run/builder-report.md`); fix what a
   refusal names. Then run the same check again,
   `council gate after-<n> -- '<same command>'`, keeping `--proof preserve` if selected before editing.
   It must pass under the build-proof contract.

## The return

End with exactly one line, nothing before or after it, one of:

```
Wrote <absolute run folder>/report-<n>.md — task <n>, round <r> saved
NEEDS: <question>
NEEDS: fix <file:line> · does: <…> · should: <…> · seen: <…>
BLOCKED: <reason>
```

- `Wrote …` only after step 6: the report written and its round saved.
- `NEEDS:` writes no round (`builder-report.md`, When the builder stops instead; `repair-loop.md`,
  Unknowns, says which form applies).
- At the third failed gate, the reason is `task <n> — <gate> failed three times: <what>`.

In a Solo build the line is yours: act on it as council-implement's build loop says.
