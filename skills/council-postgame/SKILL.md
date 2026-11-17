---
name: council-postgame
description: Check finished work against the user's original request and report gaps, drift and next tasks, including work built without the council. Use for "did we build what I asked?", a requested completion audit or /council-postgame. Propose its size and cost first.
---

# Council Post-game (mode)

A mode on the council's engine. **Invoke `context-core` and run its stages**: Convene and Prepare, then
Judge, Challenge, Deliver and Learn. Stages 3–6 are skipped — you do the desk work, and only verifiers
are dispatched, at Challenge.

**What it's for:** did we build what the user asked for — all of it, and nothing they didn't ask for?
It lines up the request, the plan and what was built, says where they drifted apart, and ends with one
clear next move.

**Not for:** code quality or bugs (that's council-review), re-arguing a decision the user made, or
fixing anything. It never edits code.

**Chair:** John Carmack. The filter: *did we build what was asked, at this scale — or something else?*

**It never grades its own homework.** The session that built the work often runs its post-game, so
every "built" claim goes to a blind verifier that sees the request — never the plan, the log or your
opinion of the work.

## When it runs

council-implement offers it at Deliver when its signals say the work needs one; it runs only on a yes.
/council-postgame starts it directly. When the user just asks "did we build what I asked?", "are we
done?" or "what's left?", propose it in one line — what it checks, about 100–180k tokens, 1 checker,
and in a repo with no council, that a small `.council/` folder will hold the result — and start on a
yes. It works on any work, council or not.

## Size

- No seats. You do the desk work; **1–3 blind verifiers** check the code — always at least 1, even for
  a tiny request.
- 2–3 verifiers, split by area, when the request has more than 12 parts or the range more than 40
  changed files.
- At most 3 agents, so it's within Squad: /council-postgame starts without asking, and a yes to the
  offer is the go-ahead.

## At Convene

1. **Open the run** — after /council-postgame or a yes, never before: `council run open council-postgame`.
   In a repo with no `.council/` it creates one; tell the user, in one plain sentence, that a small
   `.council/` folder will hold the result and can be deleted afterwards. No `council.config.md` is
   fine: a post-game needs no roster.
2. **Find the request.**
   - **Council work:** continue the request the plan's, log's or review's "Your request" line names
     (Convene, step 8).
   - **Work done without the council:** at most 3 questions, one at a time, each skipped when you
     already have the answer:
     1. "What did you ask for? Paste your original words if you have them, or point me at the issue,
        PR or spec." Offer any PR body or issue you found.
     2. "I'll check this branch since it left <default branch>: <n> commits, <m> files. Is that the
        work — and what command runs its tests?" (Leave out the test part when there's a config.)
     3. "Was there a plan or spec I should compare against?"

     Save the answer in ask.md with `source: recalled after the work` (or `from <PR, issue or spec>`).
     With no request at all, rebuild one from the PR body and commit messages, marked
     `source: reconstructed from …`; the verdict then says fit with the request can't be judged with
     confidence.
   - **Council work from before 0.6** (no request file): put the plan's Scope and Out of scope lines
     to the user — "Is this what you asked for? Add anything I've missed." — and save it
     with `source: restated from <plan>, confirmed by you <date>`.
3. **The range.** Council work: from the first log's `Start:` sha to HEAD. Otherwise — or for a log
   from before 0.6, which has no `Start:` — the merge-base with the default branch, confirmed by the
   user. A range that pulls in merges of unrelated work →
   ask the user to narrow it to paths or a commit range.

- Deliverable: `<home>/postgames/<YYYY-MM-DD>-<slug>.md`.
- Cap: no cap on the request's parts; at most 8 next tasks.

## At Prepare

- `council index --base <start>`. In a post-game it leaves out the earlier council work, because the
  verifier reads index.md; `council prior` below gives you that list.
- `council gate --all --at verify`. With no config, run the test command the user gave:
  `council gate tests -- '<command>'`.
- `council prior <the request's path>` lists the chain: plan, logs, reviews, earlier post-games.
  `council prior <changed paths>` finds review P1/P2 findings still open.
- Read the plan (tasks, Done-when, Out of scope) and the logs (notes, deviations, blocked tasks,
  follow-ups, `## Converge`). Skip `council memory select` when there's no memory file.
- Then `council state phase=judge`, not `assign`: stages 3–6 are skipped.

## At Judge — desk work, written to synthesis.md

You don't trace code here; the verifiers do.

**Split the request into numbered parts**, one requirement each, under `## Kept`:

Index line: `<n> · must|should · ask · <area or path> · <plain title> · quote: "<the request's exact words>"`

The quote is checked against the request mechanically at Challenge, so copy it exactly —
and never a secret: where the request holds a key or a password, quote the words around it, or the
filed copy's `[redacted]`.

**Then `## Drift on paper`**, as `-` bullets — never numbered lines:
- plan tasks tied to no part;
- parts no task covered;
- Out of scope items, with the user's dated words (ruled out) or without them (dropped);
- the logs' deviations, blocked tasks and follow-ups;
- the converge counts.

## At Challenge — the request check

1. `council check`: every quote must appear in the request word for word. `NOT-IN-THE-REQUEST` is a
   paraphrase: fix it first. `NOT-EXACT` differs only in capitals, `**` or backtick marks: copy the
   words exactly. `SECRET`: quote the redacted words instead.
2. Write a short brief.md. Top: the deliverable; the question "does the code do what these words
   ask?"; the code root and the range. Bottom: the hard rules, and "Not a finding: code quality,
   style, anything outside the range unless a part needs it."
3. Dispatch `small-council:council-verifier`, tracked with `council seat verify-<n> running agent=<id>`.
   Each gets the request file, the numbered parts (id and quote only), index.md, `gates/`, the brief's
   path, the code root and the range — **never the plan, the log, synthesis.md, earlier verdicts or
   your opinion** (its contract keeps it out of the rest of `.council/`). A verifier at its turn
   limit: context-core, Limits.

The verifier answers MET / PARTLY MET / NOT MET / CAN'T TELL for each part, plus M rows (asked, but no
part covers it) and U rows (built, but serving no part). **You may lower a verdict, citing the evidence in
the Result cell, but never raise one.** When you think a verdict is too low, ship it as given, with "the
Chair disagrees: <evidence>".
In the result, distinguish direct observation from inference or assumption using
`references/run/evidence-model.md`; a plan saying a part was built is not evidence that it was.

## At Deliver — `<home>/postgames/<YYYY-MM-DD>-<slug>.md`

File the request first (Deliver, step 1), then write: the post-game from
`${CLAUDE_PLUGIN_ROOT}/references/templates/postgame.md`, read now. It holds the header (Your
request, Verdict, Next move, Checked) and the sections in order:
`## What you asked → what we planned → what we built`, `## Did it go to plan?`,
`## Built but not asked`, `## Gaps`, `## Next move` with its `### Next tasks`,
`## Noticed, not tasked`, `## Ideas you didn't ask for` and `## Lessons`; then the summary in chat
and the next-move table. A next task's Done-when starts `part <#>: "<that part's quote, word for
word>"`.

**A next task closes a gap against the request, nothing else.** Only a part (or M row) that is
partly met or not met becomes a next task, and its Done-when quotes that part. A checker's note, a
latent gap in a helper or test scaffold, a nice-to-have: one line under "Noticed, not tasked" with its
reach today, never a task. A real post-game tasked check helpers instead of the request, and chained
post-games ate the day without touching the core files. After writing the file,
`council state deliverable=<path>`, then `council check` again: it refuses a next task whose Done-when
quotes no part of the request.

**Where the results come from:** Met, Partly met, Not met and Can't tell come from the verifiers. Ruled
out comes from you, and only with the user's dated words. M rows become parts; U rows go under "Built
but not asked".

Then the rulings as one question (Deliver, step 6), and the memory proposals.

## At Learn

- At most 3 lessons, as ordinary memory proposals under the admission rule. With no memory file, list
  them in the post-game only — don't create one.
- A lesson about the council's own process is scoped to its mode (Learn) — for example
  "plans that touch migrations include a rollback task".
- A part the user ruled out is proposed as a Decision, in their words.
- Then close the run (Learn, Close).

## Notes

- No code in the post-game, and it never fixes anything: council-implement is the one writer.
- Plain words to the user — "7 of 9 things you asked for are built" — never bare verdict labels.
- An "idea you didn't ask for" is never a gap, and never a next task unless the user names it.
