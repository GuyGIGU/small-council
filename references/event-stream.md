# Run event stream v1

New runs keep an append-only `events.tsv` beside `session-state.md`. The CLI writes events for
mechanical actions it can observe: opening, resuming and closing a run; changing its phase or status;
updating a seat; building a context pack; and finishing a gate, collection or citation check. The
file is local to the run and ignored by git. It is an observation record, not the authority for
current state: use
`session-state.md`, `seats.tsv`, gate verdicts and `run-plan.tsv` for that.

TSV keeps the Bash 3.2 helper readable with the tools it already requires. The fixed columns cover
the mechanics that exist today; there is no JSON dependency or event server.

The first line is exactly:

```
schema	seq	at	type	subject	value	detail
```

Each later line has seven tab-separated cells. `schema` is `1`; `seq` starts at 1 and rises by one;
`at` is UTC in `YYYY-MM-DDTHH:MM:SSZ` form. The containing folder identifies the run. Cells never
contain tabs, newlines or control characters. The writer replaces those with spaces or drops them.
It allocates sequence numbers under a per-file lock, then appends one complete line. Seat updates
hold their state lock through the event append, so concurrent updates to the same seat appear in
state-change order. Lock folders record their owner's process ID; a later command can reclaim a
lock left by a terminated writer (or an old ownerless lock). Consumers can
read the TSV directly, or use `council run events show --run <folder>` for a short view and
`council run events check --run <folder>` to verify structure and sequence.

| Type | Subject | Value | Detail |
|---|---|---|---|
| `run.opened` | `run` | mode | `phase=convene` |
| `run.phase_changed` | `run` | new phase | `from=<old phase>` |
| `run.status_changed` | `run` | new status | `from=<old status>` |
| `run.resumed` | `run` | `in-progress` | `from=<old status>` |
| `run.paused` | `run` | `paused` | `agent_runs=<n>;reported=<n>;tokens=<n>;basis=<basis>` (0.14; before: `agents=<n>;tokens=<n>`) |
| `run.closed` | `run` | `complete` or `abandoned` | as `run.paused` |
| `run.waiting_changed` | `run` | `on` or `off` | `from=<off or on>` — the run started or stopped waiting on the user (0.14) |
| `run.cap_passed` | `run` | agent runs recorded | `cap=<n>` — the first seat record that took the run past its agent cap (after 0.14) |
| `run.estimate_passed` | `run` | known exact tokens | `estimate=<n>` — first seat record above the run's whole estimate |
| `run.ceiling_passed` | `run` | known exact tokens | `ceiling=<n>` — first seat record above the owner's token ceiling |
| `seat.updated` | seat slug | new state | `tokens=<seat total>;agent_runs=<n>;reported=<n>` (0.14; before: `tokens=<cumulative tokens>`) — totals so far, never to be summed across events |
| `seat.usage_corrected` | seat slug | `tokens` or `agents` | `from=<recorded>;to=<exact>` — an evidence-backed correction, whose evidence is in `corrections.jsonl` (0.14) |
| `context.built` | seat slug | context level | `expands=<n>;metrics=<run-local path>` (see `precision-context.md`) |
| `gate.finished` | gate name | `passed` or `failed` | `exit=<code>;seconds=<n>;empty=<0 or 1>` |
| `collect.finished` | `run` | `passed` or `failed` | `seats=<n>` |
| `verification.finished` | `run` | `passed` or `failed` | `items=<n>;broken=<n>;other=<n>` |
| `memory.proposed` | the drafted entry's id (`F-<n>`) | `claim` or `repair` | `source=<claim id or task id>` |

The stable columns, version and sequence let later readers follow runs without parsing prose.
`references/run-accounting.md` says what the token and agent-run figures mean, and which basis a
total may be stated on.
Detail keys above are part of v1 for their event type; new optional types can be added without
changing the seven-column layout. A gate with no matching files has `empty=1` even if its exit is
zero. Skipped gates have no `gate.finished` event because no command ran.

Events are written after the corresponding state or gate result. A process killed between those
writes can leave a missing event; an event write failure is reported by the CLI and `council doctor`
detects a missing or malformed stream. The checker cannot infer an event that was never appended.
Human-authored work, including edits to the run plan and seat files, is not automatically observed.
`log.md` remains the place for those decisions. Future phases can add explicit event producers where
there is a useful mechanical boundary.

Runs created before this contract have no `events-schema` stamp and need no event file. They are not
backfilled with guessed events. New runs carry `events-schema: 1`; a missing file is an error.
