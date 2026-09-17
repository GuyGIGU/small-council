---
name: council-postgame
description: Check finished work against what the user originally asked for — the request word for word, the plan, what was built and the gates — and report what matches, what drifted, what's missing, and the next move. Works on council builds and on work done without the council. Use when the user asks "did we build what I asked?", "are we done?", "what's left?", or invokes /council-postgame; the Chair also offers it after some builds. Propose it with its size and cost first.
---

# Council Post-game (mode)

A mode on the council's engine. **Invoke `context-core` and run its stages**: Convene and Prepare, then
Judge, Challenge, Deliver and Learn. Stages 3–6 are skipped — you do the desk work, and only verifiers
are dispatched, at Challenge. At each stage, read the stage's doctrine, then this file's
`## At <Stage>` section.

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
  offer is the go-ahead. About 100–180k tokens with 1 verifier.

## At Convene

1. **Open the run** — after /council-postgame or a yes, never before: `council run open council-postgame`.
   In a repo with no `.council/` it creates one; tell the user, in one plain sentence, that a small
   `.council/` folder will hold the result and can be deleted afterwards. No `council.config.md` is
   fine: a post-game needs no roster.
2. **Find the request.**
   - **Council work:** the plan's, log's or review's "Your request" line gives the path.
     `council state ask=<path>`, then write ask.md with `continues: <path>` and `(no new words)` under
     "In your words" — unless the user adds words now.
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
   paraphrase: fix it first. `NOT-EXACT` differs only in capitals or `**` marks: copy the words
   exactly. `SECRET`: quote the redacted words instead.
2. Write a short brief.md. Top: the deliverable; the question "does the code do what these words
   ask?"; the code root and the range. Bottom: the hard rules, and "Not a finding: code quality,
   style, anything outside the range unless a part needs it."
3. Dispatch `small-council:council-verifier`, tracked with `council seat verify-<n> running agent=<id>`.
   Each gets the request file, the numbered parts (id and quote only), index.md, `gates/`, the brief's
   path, the code root and the range — **never the plan, the log, synthesis.md, earlier verdicts or
   your opinion** — and this line, as written: "Leave .council/ out of your reading, apart from the
   request file."

The verifier answers MET / PARTLY MET / NOT MET / CAN'T TELL for each part, plus M rows (asked, but no
part covers it) and U rows (built, but serving no part). **You may lower a verdict, citing the evidence in
the Result cell, but never raise one.** When you think a verdict is too low, ship it as given, with "the
Chair disagrees: <evidence>".

## At Deliver — `<home>/postgames/<YYYY-MM-DD>-<slug>.md`

File the request first — `council ask save` — then write:

```
---
(the doctrine's frontmatter, kind: postgame)
---
# Post-game: <feature>
**Your request:** `.council/asks/<file>` — "<first ~12 words>…" (<source>)
**Verdict:** Done | Done with gaps | Not done | Can't judge — <one sentence, e.g. "7 of 9 things you asked for are built; 1 was never planned.">
**Next move:** <one line>
**Checked:** plan `<path>` · built `<base>..<head>` (<n> files) · logs <paths> · gates at baseline → now: <…>

## What you asked → what we planned → what we built
| # | You asked (your words) | Planned | Built (evidence) | Result |
|---|---|---|---|---|
| 1 | "…" | Task 2 | `src/x.ts:40`, reached from `routes.ts:12` · tested: `tests/x.test.ts` | Met |
| 2 | "…" | not planned | — | Not met · lost in planning |
| 3 | "…" | Out of scope — you, <date>: "<their words>" | — | Ruled out |

## Did it go to plan?
- Tasks <N of N> · changed along the way: <merged / split / skipped, with the log line> · blocked: <…>
- Converge: <met / partly / not met> · Gates: <baseline → now>
- Still open: <follow-ups from the logs> · <unfixed review P1/P2>

## Built but not asked
- <path or area> — <what it does> — keep, remove, or your call

## Gaps
### G1. <plain title> — part <#> · lost in planning | lost in building | unclear request
- What's missing: <1–2 sentences, with evidence> · Size: small (one task) | big (needs design)

## Next move
<Nothing needed | Finish | Re-plan | Decide first | Review first> — <why>
### Next tasks            ← Finish only; at most 8, in the plan's task format
#### 1. <title>
| | |
|---|---|
| **Domain** | <what it checks> (<Seat>) × Carmack — <principle> |
| **Ref** | `references/<file>.md` → Principle N |
| **Depends on** | — |
| **Touches** | <files or areas> |
| **Constraints** | "<the rule or ruling, quoted>" — <config hard rule, memory id, Already decided, or your dated words>; or — |
| **Done when** | "<the request's words>" — <observable check> |

## Ideas you didn't ask for   (at most 3; never handed off unless you name them)
## Lessons
- <gap> — fix this one: <…> · prevent the next: <proposed memory entry, or none>
```

**Where the results come from:** Met, Partly met, Not met and Can't tell come from the verifiers. Ruled
out comes from you, and only with the user's dated words. M rows become parts; U rows go under "Built
but not asked".

In chat:

```
## Post-game — <verdict>
<n> of <m> things you asked for are built · <k> partly · <j> missing (<i> never planned)
Biggest gap: <one line>
Next move: <one line> — <a yes/no question>
Full post-game: <path> · Cost: ~<k>k tokens across <n> checker(s)
```

Then the numbered rulings and memory proposals.

**The next move — the first row that fits, handed off only on a yes:**

| Next move | When | Hand-off |
|---|---|---|
| Decide first | a gap needs a ruling before anyone can build it | the numbered rulings |
| Re-plan | a structural gap, more than 8 tasks, or a new fork | "Plan the rest with council-plan?" — it reads the post-game as its spec: what was built goes under Already decided |
| Finish | 1–8 next tasks, no design choice | "Build these <n> with council-implement?" — it takes the post-game as input, each next task a task, its Done-when the request's words |
| Review first | review P1/P2 findings still unfixed | offer council-review on the range |
| Nothing needed | every part is met or ruled out | none |

No review since the build? Add one line under the chosen move: "then a council review of <files>".
With no `council.config.md`, the Finish and Re-plan offers say council-init runs first (about <k>k
tokens), and the Domain and Ref cells stay "—". Every hand-off closes this run first, and continues the
same request file.

## At Learn

- At most 3 lessons, as ordinary memory proposals under the admission rule. With no memory file, list
  them in the post-game only — don't create one.
- A lesson about the council's own process is scoped to a mode — `Scope: council-plan`, for example
  "plans that touch migrations include a rollback task" — so only that mode's runs read it.
- A part the user ruled out is proposed as a Decision, in their words.
- Then close the run: `council run close`.

## Notes

- No code in the post-game, and it never fixes anything: council-implement is the one writer.
- Plain words to the user — "7 of 9 things you asked for are built" — never bare verdict labels.
- An "idea you didn't ask for" is never a gap, and never a next task unless the user names it.
