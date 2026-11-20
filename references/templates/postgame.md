# The post-game — `<home>/postgames/<YYYY-MM-DD>-<slug>.md`

council-postgame's Chair reads this file at Deliver, after filing the request: the post-game's form,
its summary in chat, and the next move. The rules for next tasks and verdicts stay in the skill.

## The file

```
---
(the frontmatter, kind: postgame)
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
| **Done when** | part <#>: "<that part's quote, word for word>" — <observable check> |

## Noticed, not tasked
- <what> — <path or area> — reach today: current | latent      ← or `none`
## Ideas you didn't ask for   (at most 3; never handed off unless you name them)
## Lessons
- <gap> — fix this one: <…> · prevent the next: <proposed memory entry, or none>
```

## In chat

```
## Post-game — <verdict>
<n> of <m> things you asked for are built · <k> partly · <j> missing (<i> never planned)
Biggest gap: <one line>
Next move: <one line> — <a yes/no question>
Full post-game: <path> · Cost: ~<k>k tokens across <n> checker(s)
```

## The next move — the first row that fits, handed off only on a yes

| Next move | When | Hand-off |
|---|---|---|
| Decide first | a gap needs a ruling before anyone can build it | the rulings question |
| Re-plan | a structural gap, more than 8 tasks, or a new fork | "Plan the rest with council-plan?" — it reads the post-game as its spec: what was built goes under Already decided |
| Finish | 1–8 next tasks, no design choice | "Build these <n> with council-implement?" — it takes the post-game as input, each next task a task, its Done-when the request's words |
| Review first | review P1/P2 findings still unfixed | offer council-review on the range |
| Nothing needed | every part is met or ruled out | none |

No review since the build? Add one line under the chosen move: "then a council review of <files>".
With no `council.config.md`, the Finish and Re-plan offers say council-init runs first (about <k>k
tokens), and the Domain and Ref cells stay "—". Every hand-off closes this run first, and continues the
same request file.
