# Rules for the four clean-behaviours builders

Read this first, then your own brief, then your map file. `SP` below is
`SP`
(bash: `SP`).

## What this step is

The Small Council plugin's helper was ported from bash to Python byte for byte. Where two copies of one job
disagreed on odd input, both were kept. The owner has now said the old odd behaviours need not survive: each job
gets ONE clean rule, with a scenario and a CHANGELOG line. A read-only map of every item is in `SP\maps-clean\`
(reading-rules.md, parsers.md, writes-platform.md). The maps were made on a tree that equals today's main; line
numbers are right. Your brief names your items and the rule already settled for each. Do not re-decide a settled
rule; if the code shows the rule is wrong or the map is wrong about a fact, stop that item and say so in the report.

## Where you work

- Your own git worktree and branch, named in your brief. Work only there. Never touch the main checkout
  (`<the main checkout>`) or another worktree.
- Three other builders work at the same time in sibling worktrees. The branches are merged afterwards, so:
  - Edit only the files your brief lists as yours (and the tests and eval scenarios for them).
  - A change you need in a file that is not yours: do not make it. Write it under `needs_integration` in your
    report (file, function, the exact change). A later step applies those.
  - Do NOT edit `CHANGELOG.md`, `docs/decisions.md`, `docs/architecture.md`, `CLAUDE.md`, `CONTRIBUTING.md`.
    Put your CHANGELOG lines, and any architecture §8 wording that must change, in your report.
  - In `evals/run_cli.py` and `evals/run_hook.py`, put a new scenario beside the related ones, not at the end of
    the file or at the end of a group's list (three builders appending at one spot would conflict).
  - `evals/ratchet.json`: run `--update` at the end so your fast tier passes. It is rebuilt at the merge.

## Rules that bind

- Behaviour that stays must stay byte for byte: output, refusal text, exit codes, files written. Only the stated
  differences of your items may show. A file the helper itself wrote, with any earlier version, must still read as
  before; only odd or hand-edited input may read differently.
- One way per job. Extend the owner (docs/architecture.md §3, §8); never add a second way beside it.
- A helper needs a second caller or must name one idea. The clever way is the plain way: do not add layers.
- `src/council/`: functions at most 60 lines, modules at most 500. These are ceilings. Never join lines to fit.
- Contract names (architecture §6) are frozen: commands, flags, exit codes, file names, TSV columns, config keys,
  state fields, event names. None is renamed or removed.
- A refusal names the next step (D19). A hook lets the call through on its own fault and never writes to stdout
  (D20). `records/` is the only parser of council files (D32). New logic in Python, stdlib only (D24).
- Every behaviour you change gets a scenario that runs the helper, in `evals/run_cli.py` or `evals/run_hook.py`
  (D25), plus unit tests in `tests/py` where the function has them. A pinned test that holds the old odd
  behaviour is changed on purpose: list each one in your report with file:line.
- Deletion and folding only. No refactor that an item does not need. Things you are tempted to fix go in the
  report under "tempted, not done".
- If you find a fault in code you build on, stop that item and report it. Never work around it in your own files.
- One commit per item. The message says what the one rule now is. Each commit ends with exactly:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- No push, no PR.

## Traps on this machine (Windows, Git Bash)

- `export PYTHONIOENCODING=utf-8` before any Python run.
- Never pipe a `council ...` command into head, tail or grep (a hook refuses it): redirect to a file, read that.
  Use `tail -n 3`, not `tail -3`.
- Never use the repo's own `.council/`. Try commands by hand only in a scratch git repo under `SP\scratch\<your name>\`.
- Do not edit tracked files while a suite is running.
- Never run `evals/run_all.py` without `--fast`. Do not run the `timing` group of `run_cli.py` at all: four
  builders share this machine, and it is run once on the merged result.
- `python evals/run_cli.py --group requests` gives 214/215 here: the judgment fixture fails because `python3` is
  the Microsoft Store stub (exit 49). Same on main. Not yours to fix.
- Run every suite in the foreground with a timeout. Do not start background shells and then end your turn: the last
  builder hung for three hours that way. Never run a command that waits forever.

## Proof you run before reporting

In your worktree:

```bash
python scripts/quick_validate.py
python evals/run_all.py --fast
SP/devtools/Scripts/python.exe -m ruff check .
PATH="SP/devtools/Scripts:$PATH" python evals/run_ratchet.py --update
PATH="SP/devtools/Scripts:$PATH" python evals/run_ratchet.py     # must print "ShellCheck measured"
python evals/run_cli.py --list          # then each group your change touches: --group NAME (never timing)
python evals/run_hook.py --group main   # if you touched a hook path (session_start, agent_gate, cap check)
python evals/run_status.py              # if you touched views/ or anything the status card reads
python evals/run_memory.py              # if you touched memory code
python evals/run_audit.py               # if you touched audit code or evals/run_all.py
```

Old against new (main after the last merge against your worktree), each set into its own folder under
`SP\scratch\<your name>\oldnew\`:

```bash
SP=SP
export OLDNEW_OLD="$(cygpath -w $SP/main-cut)" PYTHONIOENCODING=utf-8 PYTHONPATH="$(cygpath -w $SP/harness)"
python $SP/harness/oldnew.py --new "$(cygpath -w <your worktree>)" --cases <case file> --out <your folder>/<set>
python $SP/scratch/hooks/hookcmp.py --new "$(cygpath -w <your worktree>)" --out <your folder>/hooks
python $SP/scratch/mine/difflook.py <your folder>/<set>/diffs.txt     # the changed lines only
```

Case files: `$SP/harness/cases_spine_a.py`, `$SP/scratch/seat/cases_seat.py`, `$SP/scratch/runs/cases_runs.py`,
`$SP/scratch/close/cases_close.py`, `$SP/scratch/port/cases_scripts_port.py`, `$SP/scratch/launcher/cases_launcher.py`.
Each takes one to five minutes. Every differing call must be one of your stated differences or a known harness
artifact: the pid in `close.lock/owner`; two runs opened in the same second swapping `-review` and `-review-2`
(with the session line following); the harness's `old`/`new` folder names in `council status` outputs. Anything
else is a regression: fix it or report it. If your items change behaviour on odd input, add your own small case
file (`SP\scratch\<your name>\cases_<name>.py`, same shape as the others) that shows each stated difference.

## Your report

Write it to `SP\reports-clean\<your name>.md`. Plain words. Sections:

1. Commits, oldest first.
2. Lines: `src/council/` before and after (`git ls-files 'src/council/*.py' 'src/council/**/*.py'`, counted), and per item
   the lines removed and added.
3. Each item: what the one rule now is, where it lives, every visible difference with an old and new example,
   the scenario you added (function name), and each pinned test you changed (file:line, old and new assertion).
4. Proposed CHANGELOG lines (one per visible difference, under `### Changed` or `### Fixed`), and any architecture
   §8 wording that should change.
5. Proof: each command above with its counts; the old-against-new table with every difference explained.
6. `needs_integration`: changes needed in files that are not yours.
7. `needs_user`: anything that needs the owner's word.
8. Stops, and what you were tempted to do but did not.

Your final message: five lines at most (items done, items stopped, lines removed and added, anything that failed).
