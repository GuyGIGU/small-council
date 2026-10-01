# Run accounting — what a run's numbers mean

A run records who worked, how many agents ran and what they reported using. Every reader (the
status widget, `council tui`, the close line, the ledger, `council history`, `council tune`) says a
number only as far as the record supports it. Blank is unknown, never zero.

## Words

| Word | Meaning |
|---|---|
| **Seat** | A named slot of a run: one row of `seats.tsv` (`security`, `verify-3`, `task-4`). |
| **Agent run** | One agent the Chair started for a seat: an Agent tool call, or each agent a Workflow started — errored ones too, because they ran. A SendMessage resume of the same agent id is **not** a new agent run. A later pass of an agent already counted under another seat adds none. The Chair is never an agent run. |
| **Check** | One gate command (`council gate`), saved under `gates/` with a `gate.finished` event. A check is not an agent run and is never counted as one. |
| **Tokens** | The figure Claude Code reports for a finished agent run (`subagent_tokens` in its completion notification; a Workflow's notification gives one figure for all its agents), stored as whole tokens. |

**What the token figure measures.** Checked against real transcripts (a build run of September 2026), it
tracks the size of the agent's final context — not the sum of every call it made, and not a
bill. One verifier reported 160,360 while its 54 calls added up to 5.3 million. Compare runs with it;
don't price them with it.

**Nesting.** Workers and verifiers cannot start agents (their contracts forbid it), so the only nesting
is a Workflow the Chair runs: its `agent_count` is its agent runs.

**Display is not storage.** "160k" is how a figure is shown. The stored value is the whole number
(160360). A figure is never rounded when stored, and a rounded figure is never accepted.

Every display uses one rule: round half up to a whole thousand below 995,000 tokens, and to one
decimal million at or above 995,000; omit a trailing `.0`. The progress and close lines, status
card/text, TUI and history now agree: 26,430,386 appears as `26.4M` everywhere (the close line
and history prefix estimated totals with `~`), and 2,500 appears as `3k`. Only the display is
rounded; the stored totals and accounting bases stay exact.

The status card, text and JSON compare known exact agent-token figures with the **whole**
`budget/run/estimated-tokens` plan value, including its advisory Chair share. They do not subtract
that share as history does when estimating a future worker. A partial record says "at least";
unknown usage never becomes zero. An optional `budget/run/token-ceiling` is the owner's limit.
Passing either number emits one event, and passing the ceiling on an open run asks the Chair to stop
starting work until the owner says go. These token figures are context size, not a bill.

## Where it is written

| File | What it holds |
|---|---|
| `usage.tsv` (0.14+) | Append-only: every dispatch (`kind` dispatched) and every usage report (`kind` finished), with `at`, `seat`, `agent`, `runs` and `tokens`. The audit trail. |
| `seats.tsv` columns `tokens`, `agents`, `reported` | Derived from `usage.tsv` on every `council seat` call: the seat's tokens, its agent runs, and how many of those reported usage. |
| `corrections.jsonl` | Evidence-backed corrections (`council correct`), laid over `seats.tsv` by every reader. `seats.tsv` itself is never edited. |

How `usage.tsv` becomes a seat's figures:
- **Per agent id, the latest report counts.** A resumed agent reports a running total (one verifier
  reported 413,657, was resumed, then reported 463,078 for the same agent). A later figure at least
  as large replaces the earlier one, so a repeated report never adds twice. A smaller later figure is
  taken as a count of its own and added.
- **A report with no agent id stands alone.** It cannot be matched: the same figures again for that
  seat are taken as a repeat and recorded once, and a different figure adds. Record the id at dispatch.
- **A dispatched id that never reported** counts as one agent run with no usage.
- **A seat with no agent on record** (no id, no report) has an unknown agent count — its `agents` cell
  stays blank, never 0. `agents=0` on a finished report is the one way to say that no agent ran (the
  Chair did the work).

`seats.tsv` holds the summary and `usage.tsv` its parts. A reader uses one or the other, never both.
The `seat.updated` event carries a seat's totals so far, so summing events counts twice.

## Recording (`council seat`)

- `agent=` takes the id the Agent or Workflow tool returned. A role name (`workflow`,
  `council-verifier`) is refused.
- `tokens=` takes one exact number: `159812`, `159,812`, `159 812`. It is refused when it holds two
  numbers ("12 tool uses, 45000 tokens"), a sign, an exponent, a decimal comma, a rounded figure
  (`160k`, `1.2M`), or anything under 1,000. No agent run costs less than that, so 160 is a slip, and
  the helper never guesses what it meant.
- `tokens=` and `agents=` come with a finished run (`done`, `failed` or `blocked`), once per agent
  run, with the notification's figure as given. A Workflow gives `agents=<agent_count>
  tokens=<subagent_tokens>`.
- A seat the Chair did itself, with no agent: `council seat <slug> done agents=0`.

## What may be said

| Basis | When | Said as |
|---|---|---|
| complete | every agent run's usage is known (reported or corrected) | a total, "~4.7M tokens across 39 agent run(s) on the close line; 4.7M on the card" |
| running | some seats are still working | "so far" |
| partial | a finished agent run has no usage report, or a seat has no agent on record | "at least …, N without a usage report" / "no agent on record for …" |
| older | a row written before 0.14 (no `reported` value) and not corrected | "not reliably recorded"; agent runs "at least N" |
| suspect | a figure under 1,000 tokens for an agent run | not shown; the seat is named |
| none | no agent run on record | nothing to cost |

- **The close line** (`actual:` in `session-state.md`) uses the same bases.
- **The ledger** marks rows it writes with `accounting` 2. Their tokens are a checked figure or "-".
  Rows without the mark are older, and their tokens are never priced by `council ledger advice`.
- **`council history` costs only completed runs whose basis is complete, with an exact agent-run
  count.** It counts every other run under "left out", with the reason.
- **`council tune` reads that history.** Five measured runs make a proposal eligible; they do not
  make it reliable. Read its spread.

## Correcting a record (`council correct`)

`council correct <seat> tokens=<exact> agents=<exact> evidence="<source>"` appends a line per field to
`corrections.jsonl`: the value as recorded, the exact value, and where the evidence is (a transcript
file and line, a message id). It refuses a rounded figure, a figure under 1,000 other than 0, an
unknown seat, and a missing source.
- A seat no agent ran for (the Chair did the work) is `tokens=0 agents=0`.
- A later pass of an agent counted under another seat gets `agents=0` and the difference between that
  agent's consecutive reports.
- An agent run that never got a seat row is added with `unrecorded=yes` (both figures, a new slug).
  Every reader counts it as a done seat; `seats.tsv` is not touched.
- Only an exact figure the source shows is a correction. 160 is never read as 160,000 because it
  looks small.

Tool calls: `tools=<tool_uses>` on a report goes to `tools.tsv` (per agent id the latest figure, as for
tokens); the seat's line and `council collect` show it against the plan's `budget/<slug>/tool-calls`.

A closed run (complete or abandoned) takes no more agent reports: a late agent's figure goes through
`council correct`, which also refreshes the run's ledger rows. It still takes the Chair's own record
(`council seat <chair> done agents=0`, for the plan's Chair) and a seat left working marked failed — or
skipped, if it never started. A run closed
complete before Deliver may be closed again as abandoned, which takes its rows out of the ledger.

## The stop at the limit

A hook (`hooks/agent-gate.sh`) runs `council cap check` before every Agent, Task or Workflow call.
Each call it lets through is one agent start of the run this session drives (`agent-starts.tsv`), so
an agent counts from its start, before the Chair records it. A Workflow is one start, however many
agents it runs: once its `agents=N` report is recorded, its other N - 1 are added to the starts. The
stop counts the larger of the agent runs recorded and those starts, so an agent recorded later is not
counted twice, and agents started after a Workflow are not hidden by its count. Agents recorded
before the run's first counted start (a run resumed from an older version) are carried into the
starts as one `before:<n>` row. While an in-progress run has used
its agent cap, or its known tokens passed its ceiling, the call is refused, and Claude is told to ask
the user. Their go, in their words, is recorded with
`council cap allow <n> --user-said "…"` (`cap-allowances.tsv`, and a `run.cap_allowed` event): n more
agent runs may start before the stop holds again. `council cap` shows where a run stands. The status
card, text, `--line` and JSON (`usage.limit`) read it the same way: "Stopped at the limit — waiting for
your go" while stopped, "Your go allows up to 13 agent runs" once a go covers the next agent. A torn
or garbage last row of `cap-allowances.tsv` is passed over: the last readable row counts. Limits:
- A Workflow that is already running isn't stopped: the agents it starts are not checked, so one
  started below the cap can pass it.
- Starts are counted only for the one run this session drives by its recorded session id. With no
  session id, or two runs open alongside, a start is checked but not counted, and the count waits for
  the Chair's records.
- A run opened before plans and agent limits (no `plan-schema` in its state) is never stopped;
  `council cap` and the seat notes say when it passes the cap.
- A run driven by another session doesn't stop this one. A run that recorded no session stops every
  session on its working tree.
- While a run is over its limit, the hook also refuses agents that have nothing to do with the council.
- The card shows its own run's stop. The hook checks every in-progress run the session may be
  driving, so another open run's stop can refuse an agent while this card reads not stopped.

## Known limits

- A dispatched agent the Chair never recorded is not counted in the run's cost until it is added from
  evidence (the stop counts its start). One
  real build run had 8 such agent runs (a first check of a task, two surveys, and a 5-agent survey
  workflow); all were added from its transcripts.
- The resumed-agent rule assumes running totals, as observed. A smaller later figure is added, which
  is right for a fresh count and wrong if the harness ever reported less than before for the same
  agent.
- The token figure measures context size, not spend (see above).

## Status JSON contract

`council status --json [--run <name>]` needs optional Python 3.8+ and returns
`schema: "council.run-status/1"`. Reading writes nothing. Its main fields are:

- `snapshot_at`: UTC time of this reading.
- `run`: identity, path, project, mode, status, phase, stage and open/close times.
- `state`: machine key, visible label, role, icon and summary.
- `attention`: issues with kind, severity and text; `progress`: seats, checks, working, next and counts.
- `latest_check`, `checks`: saved check results; `recent` and `recent_source`: recent recorded activity.
- `freshness`: last activity time, quiet minutes and whether the run is stale.
- `usage`: token and agent-run figures with their basis and display wording; unknown values stay null.
- `usage.limit`: the stop at the limit, as `council cap` reads it: `agent_runs`, `agent_cap`,
  `tokens` (known), `ceiling`, `allowed_until` (the user's latest go: agents may start below this
  count; null when none is on record), `over` (at the cap or past the ceiling), `stopped` (over, no go
  covers the next agent, and the run is in progress) and `text` (the phrase above, or empty).
- `closing`: null for an open run; after close, the filed request, deliverable, verdict counts (null
  when missing or stale), checks, spend, agent runs against the cap, and owner follow-ups.
- `seats`: names, states, tokens, token bases, agent-run counts and notes.
- `evidence`: labels and paths to supporting records. An absent or older claim index is labelled
  "Claims index out of date" instead of showing obsolete verdicts.

This is a snapshot, not a subscription. Without Python, relay `council run status` for phase and cost.
`council status --line` is a separate, under-200-character plain sentence for an owner notification.
It prints nothing when `.council/council.config.md` has `- notifications: off`.
