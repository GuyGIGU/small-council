# The war room — council-plan's debate round

Read this at Collect when the war room is on. Round 1 stays blind, as always: each seat writes its file
alone, so you get genuinely different approaches. The war room adds one exchange: the seats read each
other's proposals and answer them, with evidence. Facts then go to the verifier, and real forks go to
the user.

## When it's on

- The user says "debate it", "war room" or "argue it out".
- Or you judge it worthwhile: at least 3 seats are going, and at least one of these holds:
  - a structural choice from the discovery conversation is still open;
  - the feature touches 3 or more map areas;
  - it touches auth, schema or migrations, concurrency, or a public contract;
  - the plan will likely go past 8 tasks;
  - the user called it hard.
- Off with fewer than 3 seats (say so; Two stances still apply), never on a Solo run, and whenever the
  user says "no debate".

Show it on the Scope Summary's Council line: `War room: on — <why> · adds about <k>k tokens, no extra
agents`, where k is about 40% of the seats' round-1 estimate. The discovery gate's go approves it. Put
`War room: on — end your file with ## Approach` in the brief's top block, and keep round-1 budgets at
about 40 tool calls, so a resumed worker still has turns left.

## Round 1 — blind, plus an Approach

Each seat's file ends with:

```
## Approach
<at most 3 sentences: the overall shape I'd build, and the choice it rests on>
I'd change my mind if: <an observation, and where to look>
```

## Points — debate.md

After a clean `council collect`, read the raw ledger (Judge's first step): the index lines, the Assumes
lines and the Approach sections. Write **at most 6 points**. A point is a neutral question that names
both sides' ids and the seats that must answer. Never show your leaning or a tally, and name each seat
in at most 3 points.

Where points come from:
1. Assumes lines that contradict each other.
2. Two seats shaping one area differently: overlapping Touches, or rival Approaches.
3. One lens's must-have that another lens makes costly.
4. A part of the request (ask.md, and the filed request it continues) that no item covers — name the
   closest lanes.
5. The assumption most items rest on. Always write this one when 1–4 find nothing, so a war room is
   never silent.

`<run>/debate.md`:

```
# War room — <feature> · round 2
Question for every seat: answer each point that names you, through your lens, with evidence. You may
also answer up to 3 other items.
Ask: <abs run>/ask.md, and the filed request it continues

## Points
### P1. <neutral question, one sentence>
- Sides: leach#2 — Data integrity · fowler#4 — Structure
- Answer: leach, fowler

## Seats
### leach-r2 — Data integrity (Leach), round 2
- ref: <the same card path as leach's block in brief.md>
- out: seats/leach-r2.md
- cap: 6 · budget: ~10 tool calls
```

`council collect` reads debate.md's `## Seats` as well as the brief's, so round-2 files are checked like
any seat file.

## Round 2 — the seats answer each other

Resume every seat a point names, all in one message: SendMessage to each one's agent id (from
seats.tsv), so they work in parallel with their round-1 context intact:

> "Round 2. Read <abs>/debate.md (your points: P1, P3), then the other seats' `## Index` and
> `## Approach` in <abs>/seats/. Write <abs>/seats/<slug>-r2.md in the round-2 format from your
> contract, then return one line."

Seats named by no point stay idle.

**Bookkeeping.**
- `council seat <slug> running agent=<same id> note="round 2"`, then `council seat <slug> done
  tokens=<n>`. The same agent id adds tokens, not agents. If the notification's figure is at least the
  seat's recorded round-1 total, it's cumulative: record the difference.
- `council state war-room="round 2 — waiting: leach, fowler"`, then `war-room=done`.
- Then one `council collect` checks both rounds.

**A worker that can't be resumed** (the session ended, or SendMessage fails) gets a fresh round-2
worker, with its round-1 file and debate.md as its brief — only if the agent cap has room, and it
counts as an agent. Track it as `council seat <slug>-r2 running agent=<id>`. No room: the seat sits out, its points become forks or verifier claims, and the
plan says so. Record it — `council seat <slug>-r2 skipped note="sits out: no room"` — so collect shows
it as skipped rather than missing.

## Judge — every point ends one of four ways

Record the ending on the point's line under `## Conflicts` in synthesis.md:

1. **Agreed** — both agree, or one side conceded or amended on evidence it checked. The item (amended,
   if it was) goes to Kept.
2. **Settled by the code** — a cited line settles it; say which. If no cited line settles it, it goes
   to the verifier at Challenge.
3. **Moved without new evidence** — treat it as not moved (that's conformity, not persuasion). It then
   ends as 2 or 4.
4. **Fork** — both hold, with evidence, and weigh the costs differently. Write it as Two stances in the
   seats' own words, your pick last and labelled, and put it to the user before tasks are grouped. At
   most 3 forks; past 3, pick yourself and say so in the plan.

- **Evidence counts, not heads.** A lone objection with evidence stands until evidence answers it.
- A held objection on a protected subject that loses the ruling becomes a Watchpoint.
- The line: `- P1 leach#2 vs fowler#4: <one line> → agreed (fowler conceded, src/db/schema.sql:40)`, or
  `→ settled by the code (<path:line>)`, `→ to the verifier`, `→ FORK — ruling 1`.
- `from:` lines cite round-1 ids only, so the ledger stays exact.

## Challenge

- An agreement a task rests on is a claim like any other; it goes in the normal verifier batches.
- A riskiest assumption named by 2 or more seats, or on a protected subject, goes to the verifier.
- A room with no object, amend or hold at all is a warning sign: send its 3 most-named riskiest
  assumptions to the verifier.

## The plan's record

Before Risks & Watchpoints, in plain words:

```
## How the council decided
| # | The question | Who said what | Outcome |
|---|---|---|---|
| 1 | One table or two for export jobs? | Data integrity (Leach): one — the join exists · Structure (Fowler): two, then conceded on schema.sql:40 | Agreed: one table |
| 2 | … | … | Your call, <date>: "<their words>" |
Still disagreeing, on record: <seat — the objection — what would change the plan>
```

## Limits

- **Two rounds, never a third.** Facts go to the verifier; values go to the user.
- **No extra agents** — a resumed worker isn't a new one.
- **Cost:** about 40% more seat tokens than a plain plan run — an estimate until the ledger has numbers.
- **Resume after a compaction:** seats marked running are still answering — wait for their
  notifications, and collect once `war-room=done`. The `war-room:` state line, seats.tsv and debate.md
  say where you were. **In a new session** they're gone: a lost round-2 seat gets a fresh round-2
  worker (above), never a round-1 re-dispatch.
