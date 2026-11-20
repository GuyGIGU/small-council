# Watch lists

A watch list is a checklist page for one part of a project's stack: what tends to go wrong with a
database, a frontend, a parser. Fourteen ship with the plugin, each at `references/<name>.md`; a
project adds its own under `.council/refs/`. A watch list is reading for an agent, never an agent:
there are no expert seats behind these pages (D72, D73).

| Watch list | What it covers | Applies when |
|---|---|---|
| `security` | Security | Almost always: input handling, auth, secrets, files, network, dependencies. With no web surface: integrity and safety (cheating, what plugins and mods may access) |
| `refactoring` | Structure and refactoring | Always: every codebase has structure |
| `quality-frontend` | Frontend quality | A UI component layer (web, mobile, desktop), read for the project's own UI framework |
| `quality-backend` | Backend quality | A server, an API, workers, async or runtime logic, whatever the runtime (FastAPI, Go, Rails, .NET) |
| `quality-postgres` | Data integrity | Any persistent state: a relational database, migrations, embedded SQL, files, caches, save data |
| `quality-performance` | Performance | A hot path worth measuring: render, request latency, batch or compute throughput, frame time |
| `quality-llm` | LLM pipelines, and numerical correctness | An LLM or prompt pipeline. For a deterministic compute or simulation engine: its boundary, NaN-and-edge and parse-defensively principles, applied to numbers |
| `quality-ui` | UI (visual) | A visual surface |
| `quality-ux` | UX | User-facing interaction, game UI and interactive CLIs included |
| `quality-testing` | Tests | Always: every codebase has, or should have, tests |
| `quality-accessibility` | Accessibility | Any user-facing interface: web, native mobile, desktop, game menus and HUDs, interactive CLIs |
| `quality-concurrency` | Concurrency and runtime | Threads, async/await, goroutines, actors, worker pools, queues, signal or interrupt handlers, a game's job system. Not for strictly single-threaded code with no async I/O |
| `untrusted-input` | Untrusted input and bytes | Parsers, decoders, uploads, file formats, IPC, CLI arguments, save files, plugin or mod data |
| `quality-operability` | Operability | Anything that runs somewhere other than a developer's terminal: services, workers, cron jobs, shipped apps, firmware. Not for libraries and dev-only tools |

Each page's principles are stack-agnostic. The ten inherited from the origin keep their origin-stack
examples (TypeScript, Next.js, tRPC, Prisma, Postgres) in a final section: illustrations, not rules.
**Look for the analogous part before leaving a list out.** A project with no database still has
persistent state (`quality-postgres`); one with no LLM may have a compute engine (`quality-llm`).

## On the stack page

The book's stack page (`references/run/book.md`) has a `Watch lists` column: each row names zero or
more lists for that part, by name (`quality-postgres, security`) or, for the project's own, by path
(`.council/refs/godot.md`). Setup proposes them from the table above and the owner confirms them with
the row's reason. `council book` prints each named list with the path an agent opens;
`council init detect` prints, for each shipped list, what the file list shows for it.

## A project's own watch list

A part none of the fourteen covers (a game engine's frame loop and scene tree, firmware, a DSL) gets
a page of its own at `.council/refs/<name>.md`: the part's real constraints (engine rules, hard
limits, known traps), each citing evidence from the repo, `status: draft` on its first line until the
owner accepts it. It is named on the stack page like any other list.

## In a brief

- The main session names the watch lists of the stack rows the work touches on the brief's
  `watch lists:` line, **two at most for one agent**, each with its path as `council book` prints
  it; `none` when no row it touches names one.
- **A watch list is reference, never a list to fill.** The bar for an item is unchanged, and nothing
  is reported because a list mentions it. An agent opens a list for the part of the work it bears
  on, and cites a principle only for a problem it found in the code.
- The protected-subject `reading:` line (a plan's or research's designer) is a separate rule and
  stays as it is.
