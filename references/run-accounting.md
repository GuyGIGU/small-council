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

**What the token figure measures.** Checked against real transcripts (the Chrollo build of September
2026), it tracks the size of the agent's final context — not the sum of every call it made, and not a
bill. One verifier reported 160,360 while its 54 calls added up to 5.3 million. Compare runs with it;
don't price them with it.

**Nesting.** Workers and verifiers cannot start agents (their contracts forbid it), so the only nesting
is a Workflow the Chair runs: its `agent_count` is its agent runs.

**Display is not storage.** "160k" is how a figure is shown. The stored value is the whole number
(160360). A figure is never rounded when stored.

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
- **A report with no agent id stands alone.** It cannot be matched, so a repeat would add. Record
  the id at dispatch.
- **A dispatched id that never reported** counts as one agent run with no usage.

`seats.tsv` holds the summary and `usage.tsv` its parts. A reader uses one or the other, never both.
The `seat.updated` event carries a seat's totals so far, so summing events counts twice.

## Recording (`council seat`)

- `agent=` takes the id the Agent or Workflow tool returned. A role name (`workflow`,
  `council-verifier`) is refused.
- `tokens=` takes one number: `159812`, `159,812`, `159 812`, `160k`. It is refused when it holds two
  numbers ("12 tool uses, 45000 tokens"), a sign, an exponent, a decimal comma, or anything under
  1,000. No agent run costs less than that, so 160 is a slip, and the helper never guesses what it
  meant.
- `tokens=` and `agents=` come with a finished run (`done`, `failed` or `blocked`), once per agent
  run, with the notification's figure as given. A Workflow gives `agents=<agent_count>
  tokens=<subagent_tokens>`.

## What may be said

| Basis | When | Said as |
|---|---|---|
| complete | every agent run's usage is known (reported or corrected) | a total, "~4,675k tokens across 39 agent runs" |
| running | some seats are still working | "so far" |
| partial | a finished agent run has no usage report | "at least …, N without a usage report" |
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
- Only an exact figure the source shows is a correction. 160 is never read as 160,000 because it
  looks small.

## Known limits

- A dispatched agent the Chair never recorded is not counted. The Chrollo build has 8 such agent runs
  (a first check of task 4, two surveys, and a 5-agent survey workflow), outside every total.
- The resumed-agent rule assumes running totals, as observed. A smaller later figure is added, which
  is right for a fresh count and wrong if the harness ever reported less than before for the same
  agent.
- The token figure measures context size, not spend (see above).
