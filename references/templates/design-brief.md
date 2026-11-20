# Brief — {{RUN}}
Deliverable: {{RUN_DIR}}/seats/designer.md, and seats/designer-2.md when the plan selects a second designer; the main session writes the {{MODE}} deliverable from them
Request: <a plan: the behaviour lines the owner agreed, one per line · research: the question in one sentence, the decision it informs, and what counts as an answer · a new project's stack: what the owner wants to build, in their words>
Ask: {{RUN_DIR}}/ask.md — the owner's own words; read them
Code root: {{CODE_ROOT}} · Council home: {{HOME}} · Run: {{RUN_DIR}} · Map: {{HOME}}/map.md
Scratch: {{RUN_DIR}}/scratch — the only place a seat may put a copy of the project or run anything

The owner does not read code. Write every item as what happens and what it costs, with a
recommendation. Every decision you bring is a consequence: what happens if nothing is decided,
your recommendation first, and whether it can be undone.

## The book — read it before anything else
{{BOOK}}
- known problems: {{KNOWN}}
- watch lists: <the watch lists of the stack rows the work touches, as council book prints them, two at most for a seat, or none> — reference, never a list to fill: the worth bar is unchanged, and nothing is reported because a list mentions it

Read the design page, the stack page and the decisions log first. A recorded decision is settled:
build on it, never re-open it. What known problems already lists is never an item here.

## Seats
### designer — reads the book and the code under the request; says where the work fits, what is broken underneath, and where there is a real fork
- ref: none
- out: seats/designer.md
- slice: the code under the request (start at: <the map's areas it touches, and the nearest existing feature like it>)
- cap: 8 · budget: ~100 tool calls
- role:

> You design before anything is built. Read the book first, then the code under the request: the
> areas it touches and the nearest existing feature like it, traced from its entry to where it
> stores or shows its result. Report three things. Where the work fits: the part it belongs in and
> the one existing way of doing that job it extends, citing the file; a second way beside it needs a
> reason the owner can weigh. What is broken underneath: a bug the request rests on, shown by a run
> (a command in a `git clone` under your scratch folder, and the output line that shows it), never
> argued; a bug the request does not rest on is one line under `## Noticed`. Where there is a real
> fork: two ways the code and the book do not settle, each with what it gives and what it costs,
> what happens if nothing is decided, your recommendation, and whether it can be undone. A small
> request, one part and one existing way with nothing hard to undo, gets three items and no more.

- answer: <research only: answer the question first, as item 1, at the confidence the evidence supports, with what would settle what stays unknown; else none>
- reading: <a protected subject (authorization, data loss, injection, secrets, concurrency or ordering, public contracts): the watch list to read for it, e.g. `references/security.md`; else none>

### designer-2 — a second, independent design of a decision that is hard to undo
- ref: none
- out: seats/designer-2.md
- only when the plan selects it: the stack of a new project, a data format, a public interface or a migration
- the decision: the dispatch's `Fork:` line, in neutral words. Make your own design of it from the
  book and the code. Never open seats/designer.md or any other seat's file: the owner needs two
  designs made apart, not one checked twice.
- cap: 8 · budget: ~100 tool calls
- role: the designer's role above, word for word, on that one decision.

## Item format

Index line: `<n> · <fit|bug|fork|answer> · <what kind: the way it extends, a wrong result, a crash, a choice of format, …> · <path:line> · <title>`

```
### <n>. <title>
- File: path:line-range (a new project: the file or folder it would make)
- Evidence state: OBSERVED (traced in the code) | REPRODUCED (a run shows it: the command and the output line) | INFERRED | ASSUMED
- Shown by: <a bug: the command and the output line, always a run · else the trace: path:line → path:line>
- What happens if nothing is done: 1–2 sentences, in what a user of the project would see or get
- Recommendation: 1–2 sentences — what to build and where, or which way to take. No code.
- Options: <a fork: each way, what it gives and what it costs · else none>
- Can it be undone: easily | with work (<what it takes>) | hard (<why>)
- Refuted if: <the one observation that would prove this wrong>
```

End your file with `## Noticed`: what you saw that is wrong and the request does not rest on, one
line and a `path:line` each, or `none`.

## Hard constraints — do not forget
- Report what the request needs only. A claim not checked against the code is worth less than none.
- Change nothing in the project. Your file and your scratch copies are the only things you write.
- Never propose adding a language, framework, library, tool or service the stack page does not
  list as a side effect: it is a fork for the owner, with what it gives and costs.
- The project's hard rules, word for word: <the config's `## Hard rules`, or none>
- Settled, never an item: <what `council memory select` printed, one line each, or none>
- The owner's decisions: <each `council state decision=` entry, word for word, or none>
