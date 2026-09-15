# Contributing to Small Council

Thanks for wanting to extend the council. One architectural rule drives everything else, so read the
contract first.

## The two-layer contract (non-negotiable)

- **`context-core` owns the pipeline** — the nine phases, the council home and file layout, resume,
  verification, memory, and close-out, in `skills/context-core/SKILL.md`. Improvements to *how work is
  handled* go there, once, and every mode inherits them.
- **A mode is thin.** It invokes `context-core` and hands it six inputs: `roster`, `worker_format`,
  `synthesis`, `gates`, `deliverable`, `memory`. Copy `skills/council-review/SKILL.md` — its shape,
  brevity, and voice.
- **Contracts live in the agents.** The seat worker's rules are in `agents/council-worker.md`, the
  verifier's in `agents/council-verifier.md`. Dispatch messages point at the brief; they don't restate
  the contract.

If you find yourself writing map / dispatch / aggregate logic inside a mode, stop — it belongs in the
core.

## Adding a mode

1. Create `skills/<mode>/SKILL.md`. Frontmatter: `name` equal to the folder (kebab-case) and a
   `description` of at most 600 characters, key use case first. If the mode fans out, the description
   says to propose it with its size and cost.
2. Invoke `context-core`, hand it the six inputs, and name a tracked deliverable path under `<home>/`.
3. Reference docs are written `${CLAUDE_PLUGIN_ROOT}/references/<file>.md` in the skill body — never a
   bare relative path a worker can't open.
4. Keep it whole after compaction: at most 20,000 characters and 500 lines (Claude Code re-attaches only
   the first ~5k tokens of a skill after compaction). Move long formats into `references/`.
5. Keep it generic: no specific project's stack, seats, or commands — those come from the project's
   config at run time.
6. Add its invariants to `evals/run_structural.py` and a drill to `evals/behavioral-drills.md`.

## Adding a seat

Seats live in `references/roster/expert-catalog.md`, not in skills. Add a row — practitioner, slug,
lens, reference doc, "applies when", recast/drop rule — and the doc under `references/`, with a single
`# Title` as its first line (workers echo it as proof they read the doc). John Carmack chairs; he is
never a seat.

## Running the gates

```bash
python scripts/quick_validate.py   # will it load?
python evals/run_structural.py     # is the method intact?
python evals/run_hook.py           # does the hook behave? (needs bash + git)
```

`.github/workflows/ci.yml` runs all three on Ubuntu and Windows.

**Releasing:** bump `version` in `.claude-plugin/plugin.json` — installed users only receive an update
when it changes — and add the matching `CHANGELOG.md` entry (an eval checks that they agree). Run the
behavioral drills, and with the Claude Code CLI, `claude plugin validate . --strict`.

## The rule

**No change ships without green evals.** A new or changed mode also needs its behavioral drills run by
hand at least once. A green build with a mode that has never actually run is not done.

## Style

- Skills, agents, hooks, and references stay **generic and stack-agnostic**. A specific project's config
  belongs only under `examples/`.
- **Plain language** in anything shown to the user — no invented jargon.
- **The simplest wiring that works.** A thin mode is easier to keep correct than a clever one.
