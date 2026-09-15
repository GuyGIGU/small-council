# Contributing to Small Council

Thanks for wanting to extend the council. Every part of the design has one owner; read this before
you change anything.

## Who owns what

- **The kernel and the stage doctrine own the method.** `skills/context-core/SKILL.md` holds the laws,
  the stage index, the helper table, the file layout, the limits and resume. `references/doctrine/`
  holds one file per stage. Improvements to *how work is handled* go there, once, and every mode
  inherits them.
- **Modes are thin.** A mode invokes `context-core` and adds only its specifics, under
  `## At <Stage>` headings named after real stages: target resolution, the per-item format, owner
  rules, the deliverable. Copy `skills/council-review/SKILL.md` for shape, brevity and voice.
- **The helper does the mechanics.** If a step can be done or checked by a script — opening and
  closing runs, gates, the change index, checking seat files or citations — it belongs in
  `bin/council`, not in prose the model has to remember.
- **The agents carry the contracts.** The seat worker's rules live in `agents/council-worker.md`, the
  verifier's in `agents/council-verifier.md`. Dispatch messages point at the brief and never restate
  a contract.
- **The hooks enforce what prose can't.** SessionStart handles orientation and resume; SubagentStop
  checks the seat file.

If you find yourself writing map, dispatch or aggregate logic inside a mode, stop: it belongs in the
doctrine or the helper.

## Adding a mode

1. Create `skills/<mode>/SKILL.md`.
   - Frontmatter: `name` equal to the folder (kebab-case).
   - `description`: at most 600 characters, key use case first. If the mode fans out, it says to
     propose the run with its size and cost.
2. Invoke `context-core`, then add `## At <Stage>` sections only where the mode differs. Name a tracked
   deliverable path under `<home>/`, and give a per-item format that starts with an index line:
   `<n> · <severity> · <principle> · <path:line> · <title>`.
3. Write reference docs as `${CLAUDE_PLUGIN_ROOT}/references/<file>.md`, never as a bare relative path
   a worker can't open.
4. Keep the file whole after compaction: at most 20,000 characters and 500 lines.
5. Keep it generic. No specific project's stack, seats or commands; those come from the project's
   config.
6. Add its invariants to `evals/run_structural.py` and a drill to `evals/behavioral-drills.md`.

## Changing the stage doctrine

- **Title and hand-off.** Each file's first line is `# Stage N — <name>`. Each ends with its hand-off:
  `council state phase=<next stage>`.
- **Size.** Stay under 6,000 characters. The Chair reads the file when it enters the stage, so every
  line competes for attention.
- **Commands.** Name helper commands in backticks. The structural eval checks that each one exists.

## Changing the helper (`bin/council`)

- **Bash 3.2 compatible** — macOS ships it. No associative arrays, no `mapfile`, no `${var,,}`.
- **Paths go to awk through `ENVIRON`**, never `-v`, which eats the backslashes in Windows paths.
- **Short, plain output**, meant for the Chair to read. Errors go to stderr with exit code 2. A gate
  returns its own exit code.
- **The SessionStart hook sources this file**, so anything at the top level must be safe to source.
  Nothing it calls may exit.
- **Every command is covered in `evals/run_cli.py`.**

## Adding a seat

Seats live in `references/roster/expert-catalog.md`, not in skills.
- Add a row: practitioner, slug, lens, reference doc, "applies when", and the recast/drop rule.
- Add the doc under `references/`:
  - its first line is a single `# Title` (workers echo it as proof of reading);
  - its principles are numbered `Principle 1…N`. P1–P3 are severities, and the two must never look
    alike.
- John Carmack chairs; he is never a seat.

## Running the gates

```bash
python scripts/quick_validate.py   # will it load?
python evals/run_structural.py     # is the design intact?
python evals/run_cli.py            # does the helper work?   (bash + git)
python evals/run_hook.py           # do the hooks behave?    (bash + git)
python evals/run_phrases.py        # advisory wording checks — never fails
```

`.github/workflows/ci.yml` runs all of them on Ubuntu and Windows.

**Releasing:**
1. Bump `version` in `.claude-plugin/plugin.json` — installed users only get an update when it
   changes.
2. Bump `COUNCIL_VERSION` in `bin/council`.
3. Add the matching `CHANGELOG.md` entry. An eval checks that all three agree.
4. Run the behavioral drills and, with the Claude Code CLI, `claude plugin validate . --strict`.

## The rule

**No change ships without green evals.** A new or changed mode also needs its behavioral drills run by
hand at least once. A green build with a mode that has never actually run is not done.

## Style

- **Generic.** Skills, doctrine, agents, hooks, the helper and references stay stack-agnostic. A
  specific project's config belongs only under `examples/`.
- **Plain language** in anything shown to the user, with no invented jargon. Say what a seat checks
  before its name.
- **Simplest wiring.** Choose the simplest design that works. A thin mode and a small script are
  easier to keep correct than clever prose.
