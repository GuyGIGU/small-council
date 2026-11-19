# A project's own decisions, at setup

Read by `council-init` once the code is mapped (Phase D) and before memory is written (Phase E). A
project that has settled how it works has usually written it down. Setup carries those decisions
into the council's memory as proposals for the user, and fills the map's `## One way per job` table,
so a plan task's `Owner` can name a row and a verifier can tell a second way from the first.

## Where to read

These files are read whole, past Phase A's cap on reads: they are the point of this step.

- Decision records: `docs/adr/`, `doc/adr/`, `adr/`, `docs/decisions/` or any `docs/decisions*`
  file, and numbered records elsewhere (`0007-use-postgres.md`) that carry a status line.
- `ARCHITECTURE.md`, and a `docs/architecture*` file.
- The sections of `CLAUDE.md` and `AGENTS.md` that state rules (always, never, must, do not), but
  not the Small Council block between its `small-council:begin` and `small-council:end` markers.

A record that says it is superseded, rejected or deprecated is not proposed; the one that replaced it
is. Two records that disagree are both shown to the user, with their dates, and neither is proposed.

**A decisions log is adopted, not copied** (D53). A project's own log or ADR folder becomes the book's
decisions log: its path goes under the config's `## Book` as `- decisions: <path>`
(`references/run/book.md`), every agent reads it there, and its entries are not proposed into memory,
so there is never a second copy. Only a decision stated outside such a log (an `ARCHITECTURE.md`, a
CLAUDE.md rule) becomes a proposal, as below. With no log, decisions stay memory's D entries.

## Each decision becomes a proposal

One line under `## Proposed` in conventions.md, in the format its comment gives:

```
- PROPOSED decision: <the decision, in the record's words> — <its reason, if it gives one> (evidence: <file:line>; from council-init, <date>)
- PROPOSED enforced convention: <an always / never rule, in the record's words> — <its reason> (evidence: <file:line>; from council-init, <date>)
```

- Quote the record. Never turn it into a stronger rule than it states, and never add one it doesn't.
- The evidence is the line where the decision is stated, not the file's first line.
- A decision the code already contradicts is still proposed, with what the code does beside it, so
  the user decides which one stands.
- Present the proposals in Phase E as a count and their titles. Accepting one is the user's word, and
  today it is moved by hand: up into `## Decisions (D)` or `## Enforced Conventions (EC)` with the
  next number, as any proposal is. `council memory accept` takes only an observed failure (`F-<n>`),
  and setup adds no command for this. Say so when presenting them.

## The map's One way per job table

One row per recurring job that is done one way here: errors, config, data access, logging, an HTTP
client, time, ids, and whatever else the project repeats.

| Column | What goes in it |
|---|---|
| Job | A few words a plan task's `Owner` can name: "read a config setting" |
| Owner | The module or folder that owns the job |
| The one way | The function, class or pattern that does it |
| Anchor path | A file, or `path:line`, where that way is done |

- An architecture doc's own "how we do X" table is copied row for row, each anchor checked against
  the code.
- Otherwise a row comes from the code: a job done the same way in several places, through one owner.
- A job done two ways today gets the row only when a record names the one way; the other is debt,
  listed under the map's `## Hot spots`. With no record to choose, leave the row out and name the job
  in the Phase E summary for the user.
- An empty table is fine: the plan check then skips the owner check, and says so.
