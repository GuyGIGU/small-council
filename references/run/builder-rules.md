# Standing builder rules

The rules every build task carries, whoever builds it: the Chair, or a builder seat. A task's orders
(`council context build task-<n>`) link this file and never copy it. Where a rule is owned elsewhere,
this list names the place; read it there.

1. **Work in the code root only.** The code root is the tree the run builds (context-core, Where
   things live). Change files there and nowhere else: not another checkout, and nothing under the
   council home but your report.
2. **No commit, branch or stash.** Nor a reset or a checkout that moves the tree. The Chair commits a
   finished task when the user allowed commits (council-implement, step 8).
3. **The smallest change that meets the Done-when.** Carmack's filter and step 4 of
   council-implement's build loop.
4. **Match the code around you.** Step 4 again, the map's conventions, and the One way per job row
   your Owner names: extend that way, never add a second beside it (`build-proof.md`, Checking).
5. **No council ids in code, comments or commit messages.** Say the reason in plain words. What
   `council check` fails on: `sharing.md`.
6. **Check the claim before you build on it.** Read the code behind each `Rests on` fact before the
   first edit. A false one is a stop, not a workaround (`repair-loop.md`, Unknowns).
7. **Two regressions, then a redesign.** Not a third patch in the same files (`repair-loop.md`, Fix
   rounds and The diagnosis worker); a gate's third failure blocks the task (its first section).
8. **One check per Bash call, under its time limit.** `build-proof.md`, Before you spend a gate run.
   Nothing in the background.
9. **Read the project's gates as the helper reports them.** `council gates` lists them and their side
   effects; a gate is judged by its exit code, and `NOTHING WAS CHECKED`, `TIMED OUT` and 97 are no
   pass (`helper-commands.md`). A gate with cost, hardware, deploy or credential side effects runs
   only on the user's go (council-implement, step 5).
10. **Start no agent.** One hand writes code: a builder dispatches no agent and invokes no council
    skill.
11. **End with the report head, or a `NEEDS:` line.** `builder-report.md`, The head and When the
    builder stops instead.
