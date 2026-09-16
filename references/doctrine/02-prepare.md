# Stage 2 — Prepare

Gather every shared fact once, so no seat has to.

## Steps

1. **Config.** Read `council.config.md` (roster, gates, hard rules, run preferences).
2. **Map.** `council map status`. Behind in areas this run touches → re-survey only those areas and
   patch their sections; bump `map-commit` only when every changed area has been covered. No map →
   write one from `${CLAUDE_PLUGIN_ROOT}/references/templates/map.md`. Hard ceiling: ~10 skeleton
   reads — manifests, entry points, schemas, route tables.
3. **Change index** — for anything with a diff: `council index [--base <ref>]` writes
   `<run>/index.md`: per changed file its hunks, changed symbols, callers and covering tests. Seats
   read it instead of each re-tracing the blast radius.
4. **Earlier council work.** The index ends with the earlier council work on the changed files; for
   a run without a diff, `council prior <path> …`. Keep ids and one line each:
   "reviews/2026-08-02-auth.md #4 — fixed in logs/2026-08-03-auth-fixes.md". Memory in scope is
   selected at Brief, once Assign has named the seats.
5. **The request, then the intent.** Read ask.md — the user's own words — and the filed request its
   `continues:` line names. Intent is one line
   summarising it (or the PR's title and body, or the plan task), never a replacement for it.
6. **Grounding gates.** `council gate --all --at grounding` — in the background if the suite is
   slow. Judge by exit code. For a failure, read the excerpt the helper prints, or Grep the saved
   `<run>/gates/<name>.txt`; never read the whole file.
   - **Exit 4 is NOTHING WAS CHECKED**, not a pass. The helper's line names which of the three it is
     — no check configured at all, none that runs at this stage, or every one skipped — so carry
     those words rather than a cause of your own. In a mode that changes code, say it at Deliver and
     offer to fit the missing ones (`${CLAUDE_PLUGIN_ROOT}/references/guardrails.md` — a council-init
     refresh writes the plan). Never let a report read clean when nothing ran.
7. **Anything look stale** — a config path, a gate that can't run? `council doctor`.

## Rules

- **Map, don't ingest:** counts, paths and signatures — not function bodies. If you're reading
  implementations, you're doing a seat's job.
- **A gate that can't run** (missing tool, deleted file) is config drift: tell the user and offer to
  fix the config. It is not a code finding.
- **Nothing checked is said out loud.** A mode that changed code carries the gates' verdict line — or
  the helper's NOTHING WAS CHECKED line — to Deliver, as stage 9 says. A mode that changed nothing
  mentions the missing checks once, in its offer, and doesn't repeat the alarm every run.

## Done when

The index (if there is a diff) and the gate results are on disk.
→ `council state phase=assign`
