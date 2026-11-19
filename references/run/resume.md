# Resuming a run

Read this when a run carries on after a break: after a compaction, in a new session, after `/clear`,
when the user says to go on with a paused run, or when you hand the work on to another session
(context-core's Resume and council-review's page point here).

- `session-state.md` is a status board (`council state` keeps it); history goes to `log.md`,
  workers' states to `seats.tsv` (`council seat`).
- After a compaction or in a new session, the SessionStart hook names the open runs and what to do
  with each. Re-invoke the skill named by the run's `mode:`, read `session-state.md` and `ask.md`,
  re-read the method for its phase, and continue: a review's is its own page (council-review), the
  step for that phase, and so is a build's, a plan's and a research run's (council-implement,
  council-plan, council-research, council-health); a post-game loads context-core and the doctrine for the
  phase. A plan or build run whose `ask.md` source line ends `(/council)` is a step of the whole loop:
  re-invoke council, whose Resume names the step.
  No hook message? Run `council run status`.
- **Carrying a run on in a new session, after `/clear`, or on the user's "go on":** first
  `council run resume --run <folder>`, which makes this session its driver. A run another session
  updated recently may still be live there: leave it — no re-dispatch, no close — until the user
  says that session has ended.
- **Seats marked running:** after a compaction they are still working — wait for their
  notifications; never re-dispatch them. In a new session they are gone: `council collect` shows
  which files exist; mark the rest `council seat <slug> failed note="interrupted"` and re-dispatch
  each once. A seat noted `round 2`: war-room.md, Limits.
- **Handing work on:** the note lists open hazards under "Ask fix-now/later before
  any commit or PR" and says: the main checkout, never an app-made worktree.
