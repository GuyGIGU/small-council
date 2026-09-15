# evals/

Three automated layers plus hand-run drills. A skill isn't done until it's tested.

## 1. Validation — will the plugin load?

```bash
python scripts/quick_validate.py
```

Plugin and marketplace manifests, every skill's and agent's frontmatter (known keys only, names match,
description under Claude Code's cap), hook commands pointing at real scripts, every
`${CLAUDE_PLUGIN_ROOT}/…` and `references/…` path a skill names existing on disk, and every seat doc
opening with the `# Title` line workers echo as proof of reading.

## 2. Structural evals — is the method intact?

```bash
python evals/run_structural.py
```

The core's nine phases in order and its field-tested rules (close every run, persist proposals, judge
gates by exit code, verify adversarially, one council home in the main checkout); the modes riding the
core with consistent deliverable paths; the agents' contracts; the templates' schemas; size budgets
that keep every skill whole after compaction; the rename; version consistency.

## 3. Hook evals — does the SessionStart hook behave?

```bash
python evals/run_hook.py      # needs bash + git
```

Runs `hooks/session-start.sh` against fixture projects: silent outside council projects; orients
council projects; flags unfinished runs and says "resume" after a compaction; quiet about closed runs;
handles legacy CRLF runs, linked worktrees, and stale maps; survives garbage input.

## 4. Behavioral drills — run in Claude Code

See `behavioral-drills.md` (D1–D11). They need a live agent and subagents, so they can't be scripted
here: roster fit, triggering, a seeded bug caught, memory respected, right-sized runs, resume after
compaction, close-out, proposals surviving, the fix loop, map reuse, and worktrees. `fixtures/` holds
the seeds for D3/D4/D9.
