# Design note — the war room and the post-game (0.6)

**What the user asked for** (2026-09-15): "the experts talking with each other about how to implement
a big feature", and a "post-game" that checks whether "the execution matches the original prompt" and
what to do next.

**The user's rulings:**
- The war room lives inside council-plan. It switches on for big or tough features, or on "debate it".
- The post-game is its own mode. The Chair offers it only when a build's log says it's worthwhile.
- Every run keeps the user's request word for word.
- Keep it simple, with at most 10 agents per run.

**How it was designed:** three independent designs (simplicity-first, evidence-first, failure-first),
then a judge scored them and merged the best of each. The decisions below are the ones to know before
changing anything.

## The war room

- **Round 1 stays blind.** Independent first positions are the main guard against groupthink, and
  debate only helps after them.
- **One exchange, through the Chair.** At most 6 neutral points go in debate.md, each naming both
  sides, and only the seats a point names answer. There is never a broadcast of every file to every
  seat: that anchors seats on each other, bloats their context, and rewards whoever writes most.
- **Resume, don't re-dispatch.** SendMessage to the same worker keeps its context and adds tokens, not
  agents. A fresh worker is the fallback, and it counts against the cap.
- **Round-2 files keep the seat-file shape,** so the seat check and `council collect` need no new
  format. Collect reads debate.md's own `## Seats`.
- **Four endings:**
  - agreed on evidence;
  - settled by the code;
  - moved without new evidence, which counts as not moved (conformity isn't persuasion);
  - a fork the user rules on, written as Two stances.

  Evidence counts, not heads.
- **Two rounds, never a third.** Facts go to the verifier, and values go to the user.
- **`from:` lines cite round-1 ids only,** so the seat ledger needed no change.

## The post-game

- **No seats.** The Chair does the desk work: the request split into quoted parts, and the drift on
  paper. Blind verifiers check the code. Seats would grade their own advice, and code quality is
  council-review's job.
- **The verifier never sees the plan or the log,** only the request and its parts. Otherwise it would
  check "done as planned" rather than "done as asked", and a part lost in planning would stay invisible.
- **The Chair may lower a verdict with evidence, never raise one.** The session that built the work
  often runs its own post-game.
- **Quotes are checked mechanically** (`council check`), so the Chair can't paraphrase the request into
  something easier to meet.
- **Offered, not automatic.** council-implement's Deliver lists six signals for offering it, and it is
  never offered again for the same request after a "no".
- **One next move:** nothing needed, finish, re-plan, decide first, or review first. It is handed off
  only on a yes.

## The request, word for word

- **`<run>/ask.md` is written right after `council run open`,** before any conversation, because a
  compaction can't paraphrase what's already on disk. That's why council-plan opens its run before the
  discovery questions.
- **`council ask save` files it under `.council/asks/`,** which is gitignored by default — the words
  stay on the user's machine — and redacts anything that looks like a secret. A hand-off continues
  the same file.
- **Every deliverable points at its request in its body,** because `council prior` reads bodies, not
  frontmatter. That way the chain survives deleting `runs/`.
- **On Git Bash, sed, awk and `$(…)` all drop carriage returns.** The helper copies with head, tail and
  `sed -b`, and never passes the user's words through a variable.

## Left out on purpose

- a separate debate command;
- live chat between seats, or agent teams;
- votes, scores, or ledger credit for debate "wins";
- a devil's-advocate seat;
- a third round;
- tracer workers or seats in the post-game;
- automatic post-games;
- a hook that logs every prompt;
- new config settings.

## Open questions

- **Resuming finished workers:** drill D18 should confirm that it works after a long Judge stage,
  whether a resumed worker's token figure is cumulative, and whether its turn limit resets.
- **Round-2 cost** (~40% more seat tokens) is an estimate. If a war room rarely changes a plan after
  about 5 runs, make it on-request only.
- **Tracking requests in git** is the user's call. The default is local only — `asks/` is in
  `.council/.gitignore`; writing `!asks/` in place of that line shares them with the team (since 0.7.1,
  `run open` puts a missing `asks/` line back), at the cost of putting whatever they typed into the history.
