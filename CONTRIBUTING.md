# Contributing to Ultra Council

Thanks for wanting to extend the council. This project has one architectural rule that everything
else follows from, so read the contract first.

## The two-layer contract (non-negotiable)

- **`context-core` owns the pipeline.** Phases 1–10 — map the territory, write one edge-ordered
  brief, partition and dispatch isolated workers, aggregate before judging, verify against reality,
  remember what was settled — live in `skills/context-core/SKILL.md`. Improvements to *how work is
  handled* go here, once, and every mode inherits them.
- **A mode is thin.** A mode (`council-review`, `council-plan`, …) does not re-implement the
  pipeline. It says "load `context-core` and follow its phases 1–10" and hands the core five inputs:
  `{personas + reference_docs, output_schema, gates, memory_namespace, synthesis_cap}`. The
  exemplar to copy is `skills/council-review/SKILL.md` — match its shape, brevity, and direct voice.

If you find yourself writing map/dispatch/aggregate logic inside a mode, stop — that belongs in the
core.

## Adding a mode

1. Create `skills/<your-mode>/SKILL.md` as a **thin** mode (see above). Keep the frontmatter
   `description` free of any specific project's stack, seats, or gate commands — those come from
   config at run time, never from the skill body.
2. Add `skills/<your-mode>/manifest.json` with `name` (must equal the folder name), `version`,
   `license`, `author`, `description`, optional `requires` (e.g. `["context-core"]`), and the
   `references` list. Every declared reference must exist under `references/`.
3. Ship a **generic default roster** in the mode and state that if `<project>/.council/council.config.md`
   exists, the mode uses *its* tailored roster and gates instead.
4. Add whatever new reference docs the mode needs under `references/` and declare them in the manifest.
5. Extend `evals/run_structural.py` with the invariants your mode must never break.

## Adding a seat

Seats are catalogued in `references/roster/expert-catalog.md`, not hard-coded into skills.

1. Add a row: the named expert, its domain, its reference doc, an **"Applies when"** rule, and a
   **recast / drop** rule so `council-init` can decide include / drop / recast per project.
2. Add the seat's reference doc under `references/` if it is new.
3. **John Carmack is the always-on chair** — the synthesis filter ("a real problem in *this* codebase
   at *this* scale, or pattern-matching?"). He is never a roster seat; do not add him as one.

## Running the gates

Run all four locally before you open a PR. `bash` and `python3` are required (Git Bash on Windows).

```bash
python scripts/quick_validate.py    # hard-fails on a broken skill / manifest / missing reference
bash   scripts/build.sh             # validate + package every skill → dist/*.skill
python evals/run_structural.py      # framework invariants (no LLM)
python evals/run_package.py         # every skill packages into a valid, CRLF-free, path-safe .skill
```

`.github/workflows/ci.yml` runs the same four on Ubuntu **and** Windows on every push — the Windows
leg is what guards against CRLF creeping into a package.

## The rule

**No skill ships without passing the evals.** Structural + package evals are the automated floor; a
new mode also needs its behavioral drills (`evals/behavioral-drills.md`) run by hand in Claude Code
at least once. A green build with a mode that has never actually run is not done.

## Style

- Keep skill bodies **generic and stack-agnostic**. A specific project's real config belongs only
  under `examples/`, never in `skills/` or `references/`.
- Reference docs are listed as `references/<name>.md`; the core resolves them to absolute paths at
  dispatch time. Never hard-code an absolute path in a skill.
- Prefer the simplest wiring that works. A mode that stays thin is easier to keep correct than a
  clever one.
