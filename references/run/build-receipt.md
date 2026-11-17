# The build's receipt and what follows it

council-implement's Chair reads this file at Deliver, before it writes the receipt: the receipt's
eight lines and the rule for each, how open items close, the order of the commit, push and PR
questions, and when to offer a post-game. Nothing here applies before Deliver.

## The receipt

The same eight lines after every build, in this order, whatever happened, so after three builds the
user reads it at a glance and notices the moment a line changes:

```
Built: <fully verified n> of <total n> tasks — <what you can do now that you couldn't before, or "no verified result"> [· <n> partly met or blocked: <one clause each>] [· push and PR held by the freeze[ until <date>]]
Works?: <what proved it — "ran <command> and <what happened>", or honestly "nobody ran it; proved by the tests and by reading the code">
Checked by machine: <council check's line, word for word: the gates' verdict line, baseline → now | the helper's own NOTHING WAS CHECKED line> [· <the standing red-baseline clause>]
Your decisions: <council check's line, word for word>
Shortcuts I took: <one line each> | none
Not proved: <council check's line, word for word>[ · <what else nobody actually checked>] | nothing
Left open: <each pre-existing hazard, follow-up, verifier note not taken, known hazard from a handoff> | nothing
Cost: helpers ~<k>k tokens across <n> agents; Chair usage <actual total or "unavailable"> · <the proof line from council check> · log: <path>
```

`Checked by machine:`, `Your decisions:` and `Not proved:` are the three lines `council check` prints on
a build, copied word for word: add to `Not proved:`, never cut from any. The standing red-baseline
clause is yours to append. Its revert check (build-proof.md) shows in those lines and in its `check:`
line.

The first `Built:` number counts only fully met tasks with required proof, passing mandatory gates,
and no unresolved verifier regression. A partly met or blocked task is named after the count but
is not counted as built: "5 of 6 tasks · 1 partly met: exports stop at 5,000 rows". A task stopped
by the repair limit is **blocked**, not merely partly met, even if some code works. A red mandatory
gate or known regression cannot be hidden behind a clean count. `Cost:` labels helper-only usage
as such; never imply it includes the Chair or the whole session when those figures are unavailable.
**Never omit the last four.** "none" and "nothing" are answers; silence isn't. A shortcut is one of
these — not a vibe: a hardcoded value, a skipped case, a swallowed error, a loosened or disabled
check, a test that asserts less than the behaviour, a TODO left behind, or a fix whose only proof was
a throwaway command. Every one also goes in the log's `## Shortcuts and concessions`.

A **guardrails task**'s both-ways proof (`${CLAUDE_PLUGIN_ROOT}/references/guardrails.md`) is
evidence, not a shortcut.

## Open items

**No commit, push or PR question while anything is left open.** How items close is the config's
`- open items:` line (missing or unreadable: `ask`, and say so):
- **`ask`:** offer each `Left open:` item as *fix now* or *later* in the rulings question
  — a data-loss hazard defaults to fix now — and wait: "later" is the user's ruling, never yours.
- **`fix now`:** no per-item question. Each item is one `Left open:` line — `<what> — ~<time> —
  ~<k>k tokens` — and you fix it like the fix round: gates prove it; a re-check or spend past the
  budget still needs the user's go; one you can't fix goes to the rulings question. A data-loss
  hazard still gets its own line to the user the moment you find it.

## Commit, push and PR

Commit, push and PR stay questions under either setting: ask them last, on their own, once the last
verifier (a post-game's too) is back, never beside a fix question, and in this order:
1. **The freeze:** `council pushes` reads the config's `- pushes:` line (missing means `on`). Under
   `off`, or `off until <date>` before that date, the freeze holds push and PR only: commit as
   authorized, record the commit in the log, and stop; the receipt's `Built:` line ends with the
   words it prints after the dash, the date included. The bash gate refuses the push meanwhile.
   From the date on, or for a word it can't read, it is `on`, and it says which.
2. **Fetch first:** `git fetch`, then `gh pr list --state all`. Say whether the base moved since
   `Start:` and whether a related PR merged; no remote or no `gh`, say that instead.
3. **The PR text:** print `<run>/pr-body.md` for the user's edit or OK. The PR question comes only
   after that OK.

## The post-game and review offers

Then **offer a post-game when the log shows one is worthwhile**
— at least one of:
1. converge found a Done-when partly met or not met, or the log has a follow-up;
2. the build hit trouble: a blocked task, a clean-context diagnosis, a SCOPE-CREEP revert, or a
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
