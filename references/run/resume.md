# Resuming a run

Read this when a run carries on after a break: after a compaction, in a new session, after `/clear`,
when the user says to go on with a paused run, or when you hand the work on to another session
(each mode's page points here).

- `session-state.md` is a status board (`council state` keeps it); history goes to `log.md`,
  workers' states to `seats.tsv` (`council seat`).
- After a compaction or in a new session, the SessionStart hook names the open runs and what to do
  with each. Re-invoke the skill named by the run's `mode:`, read `session-state.md` and `ask.md`,
  re-read the method for its phase, and continue: every mode's method is its own page, the step for
  that phase. A plan or build run whose `ask.md` source line ends `(/council)` is a step of the
  whole loop: re-invoke council, whose Resume names the step.
  No hook message? Run `council run status`.
- **A run from before 2.0** (it entered Assign, Brief or Collect, its mode is `context-core`, or it
  has no `brief.md`) can't be carried on: `council run resume` and `council state phase=` refuse
  it. Tell the user, close it paused (`council run close --run <folder> --status paused`) and
  start the work again; its record stays readable (`council status`, `council run export`).
- **Carrying a run on in a new session, after `/clear`, or on the user's "go on":** first
  `council run resume --run <folder>`, which makes this session its driver. A run another session
  updated recently may still be live there: leave it — no re-dispatch, no close — until the user
  says that session has ended.
- **Seats marked running:** after a compaction they are still working — wait for their
  notifications; never re-dispatch them. In a new session they are gone: look in `<run>/seats/`
  for the files that exist; mark the rest `council seat <slug> failed note="interrupted"` and
  re-dispatch each once.
- **Handing work on:** the note lists open hazards under "Ask fix-now/later before
  any commit or PR" and says: the main checkout, never an app-made worktree.
