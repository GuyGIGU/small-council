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
6. **Size limits for new Python:** a function at most 60 lines, a module at most 500. Code ported
   from bash is split at its seams to fit; it is not copied whole into one long function.
7. **Tests.** New library code gets unit tests in `tests/py/` (`python -m unittest discover -s
   tests/py`), which need no bash and no git and run in seconds. Scenario evals stay where they are.
8. **Deliver:** a CHANGELOG line under Unreleased; `architecture.md` updated where the session made a
   debt row true; `python evals/run_all.py` green apart from the known `python3`-stub failure on
   Windows. Commit on the session's own branch when that holds. Never push, never open a PR, never
   touch main: report, and the user decides.

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
S10, #65 and #50; Sonnet for mechanical work (S2, P3) and the other single-issue sessions. The
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
  baseline (`--update`), so every later session inherits the gain. New Python files are held to rule 6.
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

| Session | Area (today's sections of `bin/council`) | Rough size |
|---|---|---|
| S3 | The dispatcher, the launcher, home and sharing, `run open/close/status/resume`, `state` | ~1M |
| S4 | `seat`, usage, corrections, the agent stop (`cap show/allow/check`) | ~1M |
| S5 | The run plan check and `route recommend` | ~600k |
| S6 | `gate`, `gates`, `changed`, the repair glue | ~1M |
| S7 | `index`, `collect`, `check` (citations, quotes, proofs, hygiene) | ~1–1.5M |
| S8 | `map`, `doctor`, `fingerprint`, `memory`, `prior`, `ask`, `ledger` | ~1M |
| S9 | Retire the bash: `bin/council` is the launcher only; hooks call the package and `session-start.sh` stops sourcing the helper; `scripts/` entry points go; views move to `src/council/views/` | ~600k |

The open issues land on the Python, right after their area is ported, each as its own small session:
- after S4: #53 (save the audit in the run folder), #54 (flag seats with no tokens), #44 (estimates
  per role), #69 (doctor reports live hooks), #51 (unwritable `.council/`);
- after S5: #65 (a model per role), specified below;
- after S6: #68 then #47 (don't rerun green gates);
- after S7: #58, #64, #59, #60, #50 (the builder round loop);
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

### The prose track — parallel with wave 2 (skills, doctrine, references only)

- **P1** · #45, #52, #48, #49 (fewer questions; Deliver shows the PR first; the push freeze) · after
  the checking-mode PR merges, since both edit `council-implement` at its size cap · ~400–600k.
- **P2 · One rule, one place (WS6)** · every rule gets one home and is cited from the others;
  doctrine loads by surface (#67); builder rules generated from the config (#57) and rulings stored
  by the helper (#61) once S3 has landed · ~1M.
- **P3 · Layout (WS3)** · `references/` split by who reads it (doctrine, seat docs, run contracts,
  templates), every pointer updated in the same branch · ~300–500k. After P2, so files move once.

### Wave 3 — tests that prove behaviour (WS7 part 2)

- **S10** · Replace phrase pins with scenarios wherever the behaviour can be run; the Chair drill
  eval over saved run folders (#70); README's Honest limits and `roadmap-status.md` brought up to
  date · ~0.8–1.2M.

## Order and totals

```
now      S1 ─┐
         S2 ─┴─► main ─► S3 ► S4 ► S5 ► S6 ► S7 ► S8 ► S9 ─► S10
                          └ issue sessions after S4, S5, S6, S7, S8
prose    P1 ───────────► P2 ─► P3            (alongside wave 2)
```

About 10–14M tokens over 13 main sessions plus the small issue sessions. Two sessions at once at most
on code, plus one on prose: more than that and they wait on each other's merges.
