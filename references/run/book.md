# The project's book

Agents do not remember, and the owner does not read code. The book is the project's memory that every
agent starts from (D52). It has four pages. `council book` prints where each one is and whether it is
there yet; the config's `## Book` section names them.

| Page | What it holds | Adopt the project's own | Else, under the council home | At most |
|---|---|---|---|---|
| design | The parts and which way they call, who owns each folder, the one way each job is done, where new code goes, and the project's rules | `ARCHITECTURE.md`, `docs/architecture*`, `docs/design.md` | `design.md`, from `references/templates/design.md` | 2 pages, ~120 lines |
| stack | Each language, framework, library, tool and service, with the reason it was chosen | `docs/stack.md`, `STACK.md`, `TECH_STACK.md` | `stack.md`, from `references/templates/stack.md` | 1 page, ~60 lines |
| decisions | Each decision in the owner's words, its reason and what was rejected | A decisions log or ADR folder (`references/roster/decision-records.md`, Where to read) | the memory file's `## Decisions (D)` (`- decisions: memory`) | — |
| known problems | True things found and not fixed; the kinds of item the owner said not to raise again | `KNOWN_ISSUES.md`, `docs/known-issues*` | `known-problems.md`, made by the first `council book note` | — |

**One of each, never two.** Where the project keeps such a file, setup names its path under
`## Book` (`- design: docs/architecture.md`) and writes nothing beside it. A page that is both (an
architecture doc that holds the stack) is named for both.

## Writing it at setup (council-init, Phase E)

- **The design page** comes from the map: its Shape and Where things live give the parts and the
  owners; its `## One way per job` table stays in `map.md`, where the plan check reads it, and the
  design page points at it (D35). Add only what an agent would otherwise get wrong.
- **The stack page** lists what `council init detect` and the manifests show, each row with its
  reason. A reason comes from a record (cite its `file:line`) or from the owner: ask once, listing the
  rows with no reason, at Phase E. One the owner doesn't give is `not recorded`. Never invent one.
- **Each stack row names its watch lists** (D73): the checklist pages of
  `references/watch-lists.md` whose "applies when" fits that part, or a project's own page under
  `.council/refs/`, or `—`. Propose them with the reasons; the owner adds or drops any.
- **The decisions log** adopted from the project is read in place: its entries are not copied into
  memory. With none, decisions are memory's D entries, filed only on the owner's words (D28, D53).
- **Known problems** starts empty.
- Propose the pages with the rest of Phase E and write them on the owner's yes, as every Phase E item is.

## After a build: the Chair keeps the design page true

A build that adds a part, gives a folder a new owner, brings in a new way for a job (on the owner's
ruling) or changes where new code goes leaves the design page untrue, and a health pass would then
call the page's own staleness drift. So at a build's Deliver, before the report (council-implement,
section 6, step 2), the Chair edits the page:

- **Only the lines the build made untrue or left out**, and only for what the build actually changed,
  as the diff since the restore point or the reader's file shows it. Nothing the build did not touch
  is edited, and the rest of the page is never tidied or rewritten.
- **A part, an owner, where new code goes:** the page's line, in its section. **A new way for a job:**
  a row of the map's `## One way per job` table, the page pointing at it (D35). **A rule** changes
  only on the owner's word, never as a side effect of a build.
- **Within its size** (at most two pages): a line that would push it past is proposed to the owner as
  a numbered cut by the rules of What earns a line, never squeezed in.
- **Where the page is the project's own file** (named under `## Book`, such as
  `docs/architecture.md`), the same edit goes into that file in the working tree, as part of the
  change the owner reviews: it is in the log's Ready for review, and the restore point takes it back
  with the rest. Under the council home, the page is edited in place.
- **The report names it** in one line under Works now: *"The design page now says <what changed>."*
  Nothing made untrue: no edit and no line.

## What earns a line

- **A line enters only if removing it would change what an agent does.** A line that restates the
  code stays out.
- **Every rule carries its reason and its date**: `- <rule> — why: <the bug or decision it came
  from> (<YYYY-MM-DD>)`. With neither known, `why: not recorded`. A rule whose reason is gone is
  retired, on the owner's word.
- Past its size, a page is cut by these two rules, proposed as numbered lines, never rewritten whole.

## Who reads it

- **Every agent reads the design page, the stack page and the decisions log before anything else.**
  A review's brief lists them (`council run open council-review` fills its `## The book`), a build
  task's orders name them on their first line (`council context build`), and any other brief has a
  `## The book` section with the lines `council book` prints.
- **A brief names the watch lists** of the stack rows the work touches, two at most for one agent,
  on its `watch lists:` line: reference, never a list to fill. The worth bar is unchanged, and nothing
  is reported because a list mentions it.
- **The reader checks the change against the book**: a broken rule or decision, a second way beside
  a job's one way, and anything brought in that the stack page does not list.
- **A review reads known problems.** An item it already lists, or of a kind under Not to raise again,
  is cut (`why: known problem`, `why: waived`), never shown to the owner again.

## The stack is the owner's decision

Adding a language, framework, library, tool or service, or swapping one, is a decision, never a side
effect of a task (D54).

- A builder that needs one stops with `NEEDS: <what it would add, what it gives and costs>`
  (`builder-rules.md`, When you stop instead), as it stops when the design does not fit.
- A verifier finds a change that adds one with no decision of the owner's on record INCOMPLETE
  (`references/build-proof.md`, Checking); a review's reader reports it.
- On the owner's yes: a new entry in the decisions log in their words, then the stack page's row.

## A new project's stack (council-init, D63)

A project with no code yet (`council init detect` finds no manifest, and `git ls-files` lists only
documents) starts with its stack, before anything else setup proposes: it is the owner's decision, and
hard to undo.

1. Ask once what they want to build, for whom, and anything already fixed (a host, a language they
   know); save it in the setup run's `ask.md` under `## In your words`.
2. Make the setup run a squad: `size` squad, the `designer` and `designer-2` rows at the foot of its
   `run-plan.tsv` uncommented, their tokens added to `estimated-tokens`; `council run plan check`.
3. Write `<run>/brief.md` from `${CLAUDE_PLUGIN_ROOT}/references/templates/design-brief.md`, every
   `{{…}}` filled (the run, its folder, the code root, the home, `council-init`, the book's lines as
   `council book` prints them), the role text word for word. Request: the owner's words. `answer:`
   propose a stack: each language, framework, library, tool and service, what it gives, what it
   costs, and what would make you choose otherwise. `reading: none`.
4. Both in ONE message, `subagent_type: small-council:council-worker`, no `name`, no `model`:
   `Seat: <designer|designer-2> — <its line in the brief> · council-init run`, `Brief: <abs run>/brief.md`,
   `Reference: none — your role is in your brief block`, `Fork: the stack of this new project`,
   `Write <abs run>/seats/<slug>.md`; then `council seat <slug> running agent=<id>`, and `done` on
   each return. Neither sees the other's file.
5. Show both proposals side by side in the owner's terms: what each choice gives and costs, what
   happens if nothing is chosen, and whether it can be changed later and what that would take; then
   your recommendation. Where the two agree, say so.
6. On the owner's choice: a new entry in the decisions log in their words, then the stack page from
   `references/templates/stack.md`, one row per choice, its reason the owner's, dated. Setup goes on
   from the chosen stack (Phase B, its watch lists).

## Known problems (D55)

- At a review's Deliver, each item below the worth bar (Noted for later) goes in with
  `council book note "<what happens, in the project's terms> — <path:line> (review <date>)"`.
- When the owner waves off a kind of item ("stop raising X"), `council book waive "<their words>"`,
  in their words only, never the Chair's.
- The same words are written once. A problem that is fixed has its line deleted by hand.
