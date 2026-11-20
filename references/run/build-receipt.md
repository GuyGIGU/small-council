# What follows a build's report

council-implement's Chair reads this file at Deliver, once the report is written
(`skills/council-implement/SKILL.md`, section 6): how open items close, the order of the commit,
push and PR questions, and when to offer a post-game or a review. Nothing here applies before
Deliver. Since 2026-11-19 the report of the redesign's section 8 (Works now, Does not work, Your
decisions, Not proved, Noted for later, Cost, Undo) replaces the eight-line receipt this file used
to hold (D58); its rules stand where the report keeps them:

- A task that is partly met or blocked is never counted as working: it goes under Does not work,
  with what the owner would notice. A task stopped by the repair limit is blocked.
- A red mandatory gate or a known regression is never hidden behind a clean Works now.
- `council check`'s three lines (Checked by machine, Your decisions, Not proved) are copied word for
  word: add to them, never cut. A standing red start adds exactly one clause.
- Cost labels helper-only usage as such; never imply it includes the Chair or the whole session
  when those figures are unavailable.
- A shortcut is one of these, not a vibe: a hardcoded value, a skipped case, a swallowed error, a
  loosened or disabled check, a test that asserts less than the behaviour, a TODO left behind, or a
  fix whose only proof was a throwaway command. Each is one of Your decisions, and goes in the log's
  `## Shortcuts and concessions`. A guardrails task's both-ways proof
  (`${CLAUDE_PLUGIN_ROOT}/references/guardrails.md`) is evidence, not a shortcut.

## What follows the report

### Open items

**No commit, push or PR question while anything is left open.** How items close is the config's
`- open items:` line (missing or unreadable: `ask`, and say so):
- **`ask`:** offer each item under Does not work or Noted for later as *fix now* or *later* in the rulings question
  — a data-loss hazard defaults to fix now — and wait: "later" is the user's ruling, never yours.
- **`fix now`:** no per-item question. Each item is one line under Does not work — `<what> — ~<time> —
  ~<k>k tokens` — and you fix it like the fix round: gates prove it; a re-check or spend past the
  budget still needs the user's go; one you can't fix goes to the rulings question. A data-loss
  hazard still gets its own line to the user the moment you find it.

### Commit, push and PR

Commit, push and PR stay questions under either setting: ask them last, on their own, once the reader and the
runner (a post-game's verifier too) are back, never beside a fix question, and in this order:
1. **The freeze:** `council pushes` reads the config's `- pushes:` line (missing means `on`). Under
   `off`, or `off until <date>` before that date, the freeze holds push and PR only: commit as
   authorized, record the commit in the log, and stop; the report's Works now ends with the
   words it prints after the dash, the date included. The bash gate refuses the push meanwhile.
   From the date on, or for a word it can't read, it is `on`, and it says which.
2. **Fetch first:** `git fetch`, then `gh pr list --state all`. Say whether the base moved since
   the restore point and whether a related PR merged; no remote or no `gh`, say that instead.
3. **The PR text:** write it from the report (Works now, Does not work, Not proved, the Undo
   line), in the owner's terms; print `<run>/pr-body.md` for the user's edit or OK. The PR question comes only
   after that OK.

### The post-game and review offers

Then **offer a post-game when the log shows one is worthwhile**
— at least one of:
1. the check at the end found a behaviour line partly met or not met, or the log has a follow-up;
2. the build hit trouble: a blocked task, a clean-context diagnosis, a fix round, or a
   mandatory gate red at the end that was green at baseline;
3. the build left the plan: a material change of approach, plan-named code that no longer exists,
   or a task merged, split or skipped;
4. the request moved: the request file gained words after the plan, or the user ruled on scope
   mid-build;
5. it was big or long: 8 or more tasks, a war-room plan, or resumed after a compaction or in a new
   session;
6. it's the second fix pass on the same request.

Never after a fix pass that met every finding with no follow-ups, when the user already declined one
for this request (a log's `Post-game:` line), or when a post-game for this request is newer than this
log. The offer is one line, and it runs only on a yes: *"Want a post-game? It checks what we built
against your original request, word for word, and lists anything left to do — about ~<k>k tokens, 1
checker."* Record the answer as the log's last line. On a yes, finish Learn and close this run first
(`council run open` refuses a second run on the tree), then start council-postgame.

Then offer a council review of the "Ready for review" files — after the post-game, when both are
offered; a Squad is usually right.
