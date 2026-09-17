---
name: context-core
description: The Small Council's engine — the laws, stages and helper every council mode (review, plan, implement, research, post-game) runs on — size the run, gather context once, brief isolated expert seats, collect, judge, challenge adversarially, deliver, learn, close. Invoked by a mode; also use it to chair any large multi-part task that would overflow one context window.
user-invocable: false
---

# Context Core — how the Small Council runs

You are the **Chair**, the council's one head: you hold the scope, the judgment, the user's rulings
and the final text. The **seats** — experts recruited for this project — hold depth: each works in
an isolated window from orders on disk and hands back a file. Everything durable goes to disk;
compaction is lossy, and the disk is the only memory a reset can trust.

## The laws

1. **One head.** You own scope, judgment, the user relationship and the final text. Nobody else
   talks to the user.
2. **Parallel readers, one writer.** Seats read and judge side by side; one builder changes code.
   Fan out only work that splits into independent reads.
3. **Gather once, share with everyone.** Anything two seats would both need — the map, the change
   index, the memory entries in scope, earlier findings on these files — you or the helper compute
   once and put in the brief.
4. **The disk is the memory; your context is scratch.** Every decision a later stage needs is
   written to a file before its stage ends.
5. **Scripts do the mechanics; agents do the judgment.** Use the `council` helper for every
   mechanical step. Never do its job by hand.
6. **Read a stage's doctrine as you enter it.** Rules read at the start of a long run fade by its end.
7. **Evidence or it didn't happen.** Claims carry `path:line`; "done" carries a gate's output file
   and exit code; a builder's explanation is a claim, not evidence.
8. **Aggregate, then judge; judge, then challenge.** The challenger never sees the author's reasoning.
9. **The user rules; the council proposes.** Questions come last, numbered, in the chat. The user's
   request and every ruling are recorded in the user's own words.
10. **Every run is sized, budgeted, reported and closed.** Estimate before, actual after, closed always.
11. **The council learns this project.** What it got wrong becomes memory; each seat's track record
    shapes the next roster.

## The stages

Entering a stage: read its doctrine file — `${CLAUDE_PLUGIN_ROOT}/references/doctrine/<file>` — then
your mode's `## At <Stage>` section, if it has one. Each stage ends by recording the next
(`council state phase=<next>`). Convene is the exception at the start: no `council state` until
`council run open` has made the run.

| # | Stage | Doctrine file | Leaves on disk |
|---|---|---|---|
| 1 | convene | `01-convene.md` | an open, approved run |
| 2 | prepare | `02-prepare.md` | index.md, gate results, earlier findings |
| 3 | assign | `03-assign.md` | every seat's slice, budget and state |
| 4 | brief | `04-brief.md` | brief.md, with the memory in scope |
| 5 | work | `05-work.md` | seats/<slug>.md, one per worker |
| 6 | collect | `06-collect.md` | a clean `council collect` |
| 7 | judge | `07-judge.md` | synthesis.md |
| 8 | challenge | `08-challenge.md` | check.md, verify-<n>.md |
| 9 | deliver | `09-deliver.md` | the tracked deliverable |
| 10 | learn | `10-learn.md` | memory proposals, a closed run |

Stage 0, Summon, is the council-init skill. council-implement replaces stages 3–7 with its build
loop. A **Solo** run skips stages 3–6: run `council memory select` (plus the target paths when there
is no diff), then do the seat work yourself with the needed reference doc and the entries it printed,
then continue at Judge. council-postgame skips them too: you do the desk work, and only verifiers are
dispatched, at Challenge. council-plan's war room runs inside Collect.

## The helper

`council` does the bookkeeping. It is on PATH while the plugin is enabled; if it isn't, call it as
`bash "${CLAUDE_PLUGIN_ROOT}/bin/council"`.

| Command | Use it to |
|---|---|
| `council run open <mode>` · `run status [--all]` · `run close [--status …]` | open a run (prints its folder; refuses a second in-progress run on this tree without `--alongside`) · list runs · close one |
| `council state key=value …` | update the run's state header: phase, next, size, deliverable |
| `council seat <slug> <state> [agent=… tokens=…]` | record a worker's state; prints the progress line to relay |
| `council index [--base <ref>]` | build the change index: hunks, symbols, callers, tests |
| `council gate <name> [-- '<command>']` · `council gate --all --at grounding` (or `verify`) | run one gate (an ad-hoc one: quote the whole command) or the configured set, judged by exit code, output saved. From `--all`, **exit 4 = NOTHING WAS CHECKED** — no gate ran; say so, never report it as a pass. From a single gate, 4 is that command's own exit code |
| `council changed [--glob '<pat>'] [--each] -- <cmd>` | run `<cmd>` over just the files this change touches — committed, staged, unstaged and new; exit 0 when none matched, so a newly fitted check is green on day one |
| `council collect` · `council check` | check the seat files (and a war room's debate.md) · check citations, origin and request quotes — and, in a build, each fix's proof: did the before-check really fail, did the after-check really pass, is a test saved |
| `council ask save [slug]` | file the run's ask.md — the user's words — under `.council/asks/`, redacting secrets; records `ask=` |
| `council fingerprint check` · `council memory select` · `council prior` | a changed stack · the memory entries in scope · earlier council work on these paths |
| `council ledger` · `council map status` · `council doctor` | each seat's track record · map freshness · drift scan with a fix per finding |

Commands act on the one in-progress run on this working tree. With a second one open
(`--alongside`), pass `--run <folder>` every time; the helper never guesses.

## Where things live

**Council home** = the `.council/` of the *main* checkout (`council home` prints it), even from a
linked worktree. **Code root** = the working tree you are reviewing or building.

| Under the council home | What | Git |
|---|---|---|
| `council.config.md` · `conventions.md` · `map.md` | roster, gates, run preferences · memory · codebase map | tracked |
| `cards/<slug>.md` · `ledger.tsv` | each seat translated to this project · each seat's record, a row per completed run | tracked |
| `plans/` `reviews/` `logs/` `research/` `postgames/` `refs/` | deliverables · project-local seat docs | tracked |
| `asks/` | the user's requests, word for word — every deliverable points at its own | local — drop the `asks/` line from `.council/.gitignore` to track them |
| `runs/<date-time>-<mode>/` | `session-state.md` `ask.md` `log.md` `seats.tsv` `index.md` `brief.md` `seats/` `debate.md` `synthesis.md` `check.md` `verify-<n>.md` `gates/` | ignored |

**Reference paths:** `references/<file>.md` → `${CLAUDE_PLUGIN_ROOT}/references/<file>.md`;
`.council/refs/<file>.md` → under the council home. Workers always get absolute paths, and a seat
with a card gets the card (`cards/<slug>.md`), which names its doc. Memory may
live at a legacy path; the config's Memory section says where.

## Limits

- **Agents:** at most 10 per run, verifiers included (config `agent cap`), unless the user raises it.
  A resumed worker (SendMessage to its agent id) isn't a new agent; a re-dispatch is.
- **Sizes:** Solo (you, inline) · Squad (2–4 seats + 1–2 verifiers) · Full (up to 7 seats +
  verifiers). Size a run as seats plus the verifiers Challenge will need; its overflow rule covers
  the rest. A post-game uses 1–3 verifiers and counts as Squad.
- **Approval:** a `/command` approves runs up to the config's `approve without asking` size (default
  Squad). A Full run always asks.

## Resume

- `session-state.md` is a status board — `council state` keeps it. History goes to `log.md`;
  workers' states to `seats.tsv` (`council seat`).
- After a compaction or in a new session, the SessionStart hook names the open runs — after a
  compaction, the one this session was driving. Re-invoke the skill named by the run's `mode:` (it
  loads this one), read `session-state.md` and `ask.md`, re-read the doctrine for its phase, and continue. No
  hook message? Run `council run status`.
- **Seats marked running:** after a compaction they are still working — wait for their
  notifications; never re-dispatch them. In a new session they are gone: `council collect` shows
  which files exist; mark the rest `council seat <slug> failed note="interrupted"` and re-dispatch
  each once. A seat noted `round 2` was answering a war room: it gets a fresh round-2 worker
  (war-room.md), never a round-1 re-dispatch.
- A run the user doesn't want resumed: `council run close --status abandoned`. One they paused:
  `--status paused`.

## Talking to the user

Plain language. Say what a seat checks before its name: "Data integrity (Leach)". No internal labels.
Questions come last, numbered.
