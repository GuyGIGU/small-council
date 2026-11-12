# Small Council — working on the plugin

This repo is the Small Council plugin for Claude Code. You read it, change it and test it here. This
file is the short version. The rest is in:

- [`docs/architecture.md`](docs/architecture.md): the parts, which way dependencies run, who owns
  each folder, the run folder's files, where new code belongs, how each recurring job is done, naming,
  and the names that never change.
- [`docs/decisions.md`](docs/decisions.md): the settled decisions, by id. Don't re-argue or "fix" one.
  To change one, add an entry that supersedes it, and only on the user's word.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): adding a mode, a seat or a doctrine rule, and changing the
  helper.

## Before you change code

1. Find the owner (architecture §3) and the one way that job is done (§8). Extend that; never add a
   second way beside it. If you find two ways already, say so: folding them is its own task.
2. Check `docs/decisions.md` for a decision that covers the change. A change that would undo one is a
   question for the user, not an edit.
3. Contract names (architecture §6) are frozen. Renaming one is never part of a cleanup (D23).
4. New logic goes in Python (D24). Bash that stays follows D22: bash 3.2, no jq, paths to awk through
   `ENVIRON`.

## Hard limits the checks enforce

- Skills: 20,000 characters and 500 lines each. The verifier contract: 8,000 characters. A doctrine
  file: 6,000. A review run's method load: 59,407 bytes (D13). When you add a rule, move detail into
  the reference the skill points at instead of growing the skill.
- A helper refusal names the next step (D19). A hook lets the call through on its own fault, and
  never writes to stdout (D20).
- Every command and hook path has a scenario in `evals/run_cli.py` or `evals/run_hook.py`. Prove
  behaviour by running it. A phrase pin in `evals/run_structural.py` is for document contracts only
  (D25).

## Testing

```bash
python scripts/quick_validate.py          # will it load?
python evals/run_structural.py            # document contracts and size budgets (seconds)
python evals/run_ratchet.py               # sizes and structure that may only go down (seconds)
python evals/run_all.py --fast            # the fast tier: validation, structure, ratchet, unit tests (~1 min)
python evals/run_cli.py --list            # the helper's groups; run one with --group NAME
python evals/run_hook.py --group main     # the hooks
python evals/run_all.py                   # everything, in parallel (about 30 minutes on Windows)
```

- Run `--fast` and the groups your change touches while you work. Run `run_all.py` before you ask
  for a commit: the fast tier is a first look, not the gate.
- The ratchet (`evals/ratchet.json`) holds each file's lines and longest function, the ShellCheck
  warnings, and the counts of files that parse a council file, `council.config.md` readers and
  scripts that run `bin/council`. A number may only go down. When your change lowers one, run
  `python evals/run_ratchet.py --update` in the same branch so the gain is kept; it refuses to raise
  one. A new Python file is held to 60-line functions and 500-line modules.
- Don't edit or stash tracked files while a suite is running: it reads the tree as it goes.
- On Windows, `python3` can be the Microsoft Store stub (exit 49). The judgment fixture's gate fails
  for that reason alone, and it fails the same way on main.

## This repo runs its own hooks

The plugin is installed in this session, so its hooks judge your commands here too. `council …` piped
into `head`, `tail` or `grep` is refused (D21): redirect the output to a file and read that. To try a
command by hand, use a scratch git repo outside this one. Never use this repo's own `.council/`.

## Delivering a change

- One branch per batch (`claude/<topic>`), never main. Commit only when the user says so.
- Add a CHANGELOG line under `## [Unreleased]` in the same branch.
- Agree the PR title and body with the user before `gh pr create`.
- Fix what was asked. List anything else you noticed in one line, and ask before taking it on.
