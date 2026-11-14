# The cleanup plan

How Small Council gets from one 8,000-line bash helper with copied parsers to a layered Python
codebase an agent can read and change safely. [`architecture.md`](../architecture.md) says where the
code is going; [`decisions.md`](../decisions.md) says what is settled. This page says in what order,
in which sessions, and what "done" means for each.

Each session below is one branch and one PR. A session reads this page, the architecture and the
decisions before it writes anything.

## Rules for every session

1. **Behaviour does not change.** Commands, arguments, output text, exit codes, file names and file
   formats stay exactly as they are (D23). The existing eval suite is the proof: it must pass
   unchanged. An eval is edited only when it reaches into something the session moved (an import
   path, a file location), never to accept different behaviour. A real bug found on the way is one
   line in the session's report, not a fix.
2. **Fold, never add beside.** When a session meets a second way of doing a job, it moves the
   callers it owns onto the one way (architecture §8) and deletes the copy. It never adds a third.
3. **Stay inside your files.** Each session lists the paths it owns. Anything outside them is
   read-only. If the work needs a change elsewhere, stop and report it.
4. **Python 3.8+, standard library only at run time** (D24, D32). Type hints on every public
   function. No `match`, no `X | Y` annotations evaluated at run time, no walrus in ways 3.8 rejects.
5. **Names and comments follow architecture §9.** A comment says why in a line or two. A story about
   the real run that taught a rule moves to `decisions.md` (as part of an existing entry's Source) or
   is dropped when the CHANGELOG already tells it.
6. **Size limits for new Python:** a function at most 60 lines, a module at most 500. These are
   ceilings, not targets: keep it simple.
   - Split a function where its job changes, not where it reaches 60 lines. Each piece gets a name
     that says what it does.
   - A helper earns its place with a second caller, or by naming one idea its caller would otherwise
     spell out. A helper that only passes its arguments on is inlined.
   - Fold before you write. Before you add a function, search `src/council/` for one that already does
     the job, and use or extend it (rule 2).
   - Plain over clever: no class where a function will do, no layer that adds only a name.

   Code ported from bash is split at its seams to fit; it is not copied whole into one long function.
7. **Tests.** New library code gets unit tests in `tests/py/` (`python -m unittest discover -s
   tests/py`), which need no bash and no git and run in seconds. Scenario evals stay where they are.
8. **Deliver:** a CHANGELOG line under Unreleased; `architecture.md` updated where the session made a
   debt row true; the fast tier and the groups the change touches green (CI's full suite on three
   systems is the gate before merge, since 2026-11-13). Commit and push the session's own branch.
   Never open a PR, never touch main: report, and the planning session checks the diff and opens it.
9. **Account for what you removed, and name the cause of a fix.** The report lists every rule,
   behaviour, test or assertion the session took out and where each stands now, or says none. A fix
   states what was wrong in one sentence and how that was observed. The planning session checks
   both against the diff before it relays the report ([`task-tree.md`](task-tree.md)).

## Target layout

```
bin/council              a thin bash launcher: find Python 3.8+, run the package (D22 holds for it)
src/council/             the Python package: everything the helper does
  __main__.py            the command dispatcher
  records/               one reader and writer per council file — the only code that parses them
    paths.py             the council home, run folders, safe file reads (symlink and size guards)
    locks.py             the mkdir lock protocol bash uses today, so both can write during the move
    config.py            council.config.md: one function per key, with its default
    state.py             session-state.md: fields, decisions
    events.py            events.tsv: append under the lock, read
    seats.py             seats.tsv, usage.tsv, agent-starts.tsv, corrections
    plan.py              run-plan.tsv
    gates.py             gates/<name>.json and .txt
    ledger.py            ledger.tsv
  commands/              one module per command area (WS2 fills it)
  views/                 status, cockpit, pet, history and the other renderers (moved from scripts/)
scripts/                 quick_validate.py and other developer tools only, once WS2 ends
hooks/                   thin bash that asks the package for each decision
tests/py/                unit tests for src/council
evals/                   scenario suites, run by evals/run_all.py
```

Until WS2 ends, `scripts/<name>.py` files stay as the entry points bash calls. Each becomes a few
lines that put `src/` on `sys.path` and call into the package.

## Sessions

Sizes are rough tokens for one builder session with machine checks and no checker agents.

Which model builds: Opus for the ports (S1, S3–S9), for rule-writing at the size caps (P1, P2), for
S10, S11, #65 and #50; Sonnet for mechanical work (S2, P3) and the other single-issue sessions. The
planning session decides and checks; it does not build.

### Wave 1 — start now, in parallel (different files)

**S1 · The records library (WS1)** · branch `claude/records-library` · ~1–1.5M
- Owns: `src/council/` (new), `tests/py/` (new), `scripts/*.py` except `quick_validate.py` and
  `pet.py`'s drawing code, the eval files of the scripts it touches (import paths only).
- Build `src/council/records/` as laid out above. Start from `scripts/cockpit.py`'s guarded readers
  (`text_of`, `tsv`, `jsonl`, `header`, `decisions`, `plan_of`, `gates_of`), which are already the
  nearest thing to a shared reader. `locks.py` implements `event_lock`'s mkdir protocol from
  `bin/council` exactly, so Python and bash writers exclude each other.
- Move every script onto it: `audit`, `chair_usage`, `cockpit`, `context`, `evidence`, `history`,
  `impact`, `ledger`, `memory`, `outcomes`, `repair`, `status`, `tune`. Delete each script's own
  `field`, `state_field`, `tsv`, `read_config`, `atomic_write`, `git` and `local_time`.
- Does not touch `bin/council`, hooks, skills, references, `evals/run_all.py` or CI.
- Done when: no file under `scripts/` opens `session-state.md`, `run-plan.tsv`, `events.tsv`,
  `seats.tsv`, `usage.tsv`, `ledger.tsv` or `council.config.md` itself (a grep in the report shows
  it); unit tests cover every `records` module; every script's eval suite passes unchanged.

**S2 · A fast test tier and ratchets (WS4, WS7 part 1)** · branch `claude/fast-tier-ratchets` · ~500–800k
- Owns: `evals/run_all.py`, `evals/run_ratchet.py` (new), `evals/ratchet.json` (new), `ruff.toml`
  (new), `.github/workflows/ci.yml`, `CONTRIBUTING.md`'s "Running the gates", `CLAUDE.md`'s Testing
  section.
- `python evals/run_all.py --fast`: validation, structural, the unit tests in `tests/py/` when the
  folder exists, and the quickest scenario groups, under two minutes on Windows. The full run stays
  the default and stays what CI runs.
- `evals/run_ratchet.py` measures, per file, and compares with `evals/ratchet.json`: lines per file
  and the longest function in `bin/council`, `hooks/*.sh`, `scripts/*.py` and `src/**/*.py`; the count
  of files outside `src/council/records/` that name a council file to parse it; the count of
  `council.config.md` readers outside one `configured_*` or `records/config.py` function; the count
  of scripts that call `bin/council` back. A number may only go down. A lower number rewrites the
  baseline (`--update`), so every later session inherits the gain. New Python files are held to rule 6, and so are `src/council/`'s, which may grow up to its limits
  instead of being frozen (the user's call, 2026-11-14: freezing them pushed sessions to squeeze lines).
- Lint: `ruff.toml` with the rule set the Python can pass today, plus a stricter set for
  `src/council/` (pyflakes, pycodestyle, bugbear, simplify, annotations). ShellCheck at warning level
  as a ratchet count, not a wall. CI runs the ratchet and the fast tier before the full suite.
- Does not touch `bin/council`, `scripts/`, `src/`, hooks, skills or references.
- Done when: the fast tier runs under two minutes; the ratchet fails on a planted regression (a
  function made one line longer than its baseline) and passes once it is removed; CI config is valid.

Both branch from `claude/architecture-record`. S2's ratchet only tightens, so S1 landing after it
lowers numbers and never breaks it; whichever merges second runs `run_ratchet.py --update`.

### Wave 2 — the helper moves to Python (WS2 and WS5), one session at a time

Each session ports one area of `bin/council` into `src/council/commands/`, deletes that bash, and
leaves `bin/council` dispatching the ported commands to `python -m council`. The slop pass (WS5)
happens in the port: names, comments and function sizes are fixed as the code is rewritten, so no
bash is polished and then thrown away. Each starts from main after the one before it merges.

The order is leaves first. `state` and `run open`, `close` and `resume` call the plan check (S5),
usage (S4), the gates table (S6), the ledger, the memory file and redaction (S8), so they are ported
after all of those, as S8b. S3 found this on 2026-11-13: porting them first would have meant a Python
copy of about 560 lines beside bash that keeps running, or Python calling the bash back. A session
that meets such a dependency stops and reports it; it does neither.

| Session | Area (today's sections of `bin/council`) | Rough size |
|---|---|---|
| S3 | The dispatcher, the launcher, home and sharing, `run status`, and one lock rule for bash and Python writers | ~600k |
| S4 | Usage and the agent stop (`cap`, `cap check`). `seat`, `correct` and `cap allow` moved to S8b: they call the plan check, the ledger, redaction and the state writer, so porting them first meant a Python copy of those or Python calling the bash back (S4 found this on 2026-11-13) | ~1M |
| S5 | The run plan check and `route recommend` | ~600k |
| S6 | `gate`, `gates`, `changed`, the repair glue | ~1M |
| S7 | `index`, `collect`, `check` (citations, quotes, proofs, hygiene) | ~1–1.5M |
| S8 | `map`, `doctor`, `fingerprint`, `memory`, `prior`, `ask`, `ledger` | ~1M |
| S8b | `state`, `run open`, `run close`, `run resume`, and from S4 `seat`, `correct` and `cap allow` | ~600k |
| S9 | Retire the bash: `bin/council` is the launcher only; hooks call the package and `session-start.sh` stops sourcing the helper; `scripts/` entry points go; views move to `src/council/views/` | ~600k |

The open issues land on the Python, right after their area is ported, each as its own small session:
- after S4: #53 (save the audit in the run folder), #54 (flag seats with no tokens), #44 (estimates
  per role), #69 (doctor reports live hooks), #51 (unwritable `.council/`);
- after S5: #65 (a model per role), specified below;
- after S6: #68 then #47 (don't rerun green gates);
- after S7: #58, #59, #60, #50 (the builder round loop), as step T2 of the task tree below;
- after S8: #55 (memory size budget and a tidy command), #62 (map refresh at close).

Held until the user says otherwise: #63 (a lead-builder seat).

**#65 · A model per role** · after S5, which ports the run plan check that enforces it · ~400–600k.
The user agreed on 2026-11-12 to replace D30. The session adds the new decision to `decisions.md`
and marks D30 superseded in the same branch as the code, so the index never claims a rule the helper
doesn't enforce yet.
- Config: `- models: builder=<name>, review=<name>, verifier=<name>`, beside today's mapping and
  survey routing. A name is `inherit`, `fable`, `opus`, `sonnet` or `haiku`: what the Agent tool
  takes, and nothing that goes stale with a model version. `- seat models:` keeps working as it does.
- Every role defaults to `inherit`, so no run changes until its project opts in. `council-init`
  proposes a split from the session's model and the user confirms it.
- The plan check refuses a verifier on a weaker model than the builder it checks. This replaces
  "the verifier always inherits". The Chair stays on the session's model.
- The ledger records the model per seat.
- `lead=` is left out while #63 is held.

**The task tree** · [`task-tree.md`](task-tree.md), a proposal the user asked for on 2026-11-13: the
request, its tasks and their changes kept as one tree on disk, a builder's orders generated from
it, and a builder's report checked against its diff. It gathers #50, #57, #58, #59, #60, #61, #64
and #67 under one design (and #93, added 2026-11-13), so those issues are built as its steps and
not one by one:
- T1 after S5: the task fields, their plan check, `NEEDS:` and the research rules (#64), plus
  the decision checks from #93 (an `Owner:` row or `New way:`; the verifier's decision question)
  · ~700–900k.
- T2 after S7: the report head, the saved diff and the checks on it (#58, #59, #50, #60) · ~1M.
- T3 after T1 and S8: the generated task pack (#57, #61, #67) and `council tree`, plus #93's setup
  side (the project's decision records proposed into memory; the map's one-way-per-job table)
  · ~700–900k.
- T4 in S10: the planted drill cases (#70).

### The prose track — parallel with wave 2 (skills, doctrine, references only)

- **P1** · #45, #52, #48, #49 (fewer questions; Deliver shows the PR first; the push freeze) · after
  the checking-mode PR merges, since both edit `council-implement` at its size cap · ~400–600k.
- **P2 · One rule, one place (WS6)** · every rule gets one home and is cited from the others, and
  the doctrine is split so it can load by surface (#67). The helper side of #67, the builder rules
  generated from the config (#57) and the rulings stored by the helper (#61) are step T3 of the task
  tree · ~800k.
- **P3 · Layout (WS3)** · `references/` split by who reads it (doctrine, seat docs, run contracts,
  templates), every pointer updated in the same branch · ~300–500k. After P2, so files move once.

### Wave 3 — tests that prove behaviour (WS7 part 2)

- **S10** · Replace phrase pins with scenarios wherever the behaviour can be run; the Chair drill
  eval over saved run folders (#70); README's Honest limits and `roadmap-status.md` brought up to
  date · ~0.8–1.2M.

### The size pass — after S9, beside S10

- **S11 · Make the Python smaller** · after S9, once every command is in one language · may run
  beside S10, since S11 owns `src/council/` and `tests/py/` and S10 owns `evals/` and the documents it
  names · ~600k–1M.
  The port about doubled the helper. On 2026-11-14 about 4,600 lines of bash had become about 13,500
  lines of Python in 102 files, with 3,541 lines of bash still to port. Rule 6 keeps each function and
  module small, but nothing keeps the whole small. S11 shrinks it without changing behaviour (rule 1).
  - Measure first. For three ported areas, compare the bash with the Python it became and count where
    the extra lines went: docstrings, argument parsing, wrappers, copies, splits. The report gives
    that count, and the cuts follow from it.
  - Apply rule 6's split and fold rules to the code that came before them.
  - Fold the copies. Two functions that do one job (parse a council file, read a table, quote a
    path, word a refusal) become one in its owner (architecture §3), and the callers move to it
    (rule 2).
  - Delete what nothing calls. Search for every name's callers in the hooks, `scripts/` and the evals
    before you delete it.
  - Cut comments and docstrings that restate a name or a signature (architecture §9). Keep the ones
    that say why.
  - Remove wrappers that only pass their arguments on.

  Done when the eval suite passes unchanged and the report gives `src/council/`'s line and file
  counts before and after. The report also lists each fold and each deletion with the callers that
  moved. `python evals/run_ratchet.py --update` keeps the gains. There is no line target. Never join
  lines to fit: a split that the 60-line limit forced stays split.

## Order and totals

```
now      S1 ─┐
         S2 ─┴─► main ─► S3 ► S4 ► S5 ► S6 ► S7 ► S8 ► S8b ► S9 ─┬► S10
                                                                 └► S11
                          └ issue sessions after S4, S5, S6, S7, S8
prose    P1 ───────────► P2 ─► P3            (alongside wave 2)
```

About 11–15M tokens over 15 main sessions plus the small issue sessions. Two sessions at once at most
on code, plus one on prose: more than that and they wait on each other's merges.
