# Handover: the clean-behaviours step, from a Windows session to the cloud

This branch (`claude/clean-handover`) is never merged and gets no PR. It carries what the next session
needs. Delete it once the clean-behaviours PR has merged.

## What the step is

The helper was ported from bash to Python byte for byte. Where two copies of one job disagreed on odd
input, both were kept. The owner's decision: the old odd behaviours need not survive. Each job gets ONE
clean rule, with a scenario (D25) and a CHANGELOG line. Base: main at `a47fb43` (after PR 113).

Three read-only maps of every item are in `handover/maps/` (`reading-rules.md`, `parsers.md`,
`writes-platform.md`; line numbers are right for `a47fb43`). `handover/maps/builder-rules.md` holds the
rules the four builders worked under; they bind the rest of the step too (ignore its Windows traps).

## The four branches (all pushed, each cut from `a47fb43`, file-disjoint by design)

See "State at handover" at the end of this file for what each one holds and whether its builder finished.

### `claude/clean-read`: reading rules
1. Plan rows read one way: lines through `cells.lines_of`, one raw-cells function, one space/tab trim;
   `plan.budget` removes no inner blanks; `plan.keyed` keeps values as written; the FIRST row of a repeated
   (kind, id, field) wins everywhere; `plan_check` keeps raw cells.
2. `bytewise.records(fold=True)` drops a CR before LF on every OS; `fold=False` unchanged; `run_events.py`
   and `gate_failed.py` lose their `os.name` conditions.
3. Only LF ends a line in `evidence.py`, `audit_checks.py`, `repair_trail.py`; `paths.universal` goes.
   `repair_trail.classify` changes ONLY if no trail already on disk would newly be refused or FAIL;
   otherwise it is left and reported for the owner.
4. Numbers: plain ASCII digits, 1 to 12 of them; `None` for a figure, 0 for a sum. `cells.integer` stays signed.
5. One test of "this run is on this tree" in `records/runs.py` (code-root is this tree, blank or `-`).
6. `runs.listed_fields` reads the state header only, as `state.header` does.

### `claude/clean-memory`: memory and views
1. Memory edits find entries by the memory parser's own tests (`records/memory_entries`); `load_memory`
   reads bytes so a file that is not valid UTF-8 works; `find_entry` line ranges stay in `memory_draft`.
2. One reader of the config's Roster table (seat, slug, lens, reference; an empty Lens row is kept).
3. `config.memory_path` goes; status uses `memory.locate`; the key stays exactly `conventions:`.
4. The status card counts drafted lessons with the real parser.
5. The converge reader moves to a new `records/converge.py`.
6. `request.filed(run)` owns which file a request is in; the asks-folder guard moves into
   `records/request.py`; title extraction stays separate but ends lines at LF only.
7. `latest_of` is `checks_of(snap)[-1]`.
It was told not to touch the `Path.is_absolute` tests (they belong to the final step).

### `claude/clean-commands`: command folds
1. `diff.header(line)` is the one reader of a hunk header; four users skip `None`.
2. `index.records` and hygiene's line readers go through `bytewise.records`.
3. `earlier.hits` returns a named tuple per mention (a mentioned line is no longer cut at its first tab).
4. The events-schema stamp is read through `state.text` with a D19 refusal; a repeated detail key: first wins.
5. `council changed --glob/--each` are ordinary cli flags.
6. `clock.now_date()` is the one date-only stamp.
7. `json_esc`: every control character below 0x20 becomes a space (gate verdicts are always valid JSON).

### `claude/clean-write`: writes and legacy
1. An agent start row is appended through `paths.append_row` (seed row, tab strip and the swallowed
   `OSError` kept; `tests/py/test_cap.py:150-163` bytes unchanged).
2. `state_write.replace` goes through `paths.atomic_write(keep_mode=True)`.
3. A build's start time is read with `clock.local_moment`.
4. `council memory check` searches in Python over `Tree.files` (no `grep`), skipping NUL files and files
   over `paths.MAX_FILE`.
5. The 0.1/0.2 `.council/active-run` pointer is no longer read or written; an old file is left byte for byte.
   Kept on purpose, because current projects use them: runs with no code-root, short mode names, a council
   inside a linked worktree (`records/home.py`), a memory file at the repo root (`conventions.md`).

## What is left

1. **Check each branch against its diff** (`git diff a47fb43 origin/claude/clean-<name>`): only its own
   files touched (lists in the builders' briefs are summed up above); every visible difference has a
   scenario in `evals/run_cli.py` or `evals/run_hook.py`; no edit to `CHANGELOG.md`, `docs/decisions.md`,
   `docs/architecture.md`, `CLAUDE.md`, `CONTRIBUTING.md`. A report is a claim: where a branch has no report
   here, derive its visible differences from its commits and tests.
2. **Finish what a builder did not** (see "State at handover").
3. **Merge** the four into a new branch `claude/clean-behaviours` cut from `origin/main`. Expect conflicts
   only in `evals/ratchet.json` (rebuild it with `python evals/run_ratchet.py --update`, ShellCheck on PATH,
   never hand-merge) and perhaps neighbouring scenario lists in `evals/run_cli.py`.
4. **The final step, after the merge, one writer:** one absolute-path test, `records/home.absolute(p)`
   (`bool(re.match(r"[/\\]|[A-Za-z]:", p))`), at the 27 sites listed in `maps/writes-platform.md` (four
   shapes). The `Path.is_absolute` sites must also go through `where.native`. `records/memory.py:41-43`
   keeps its own meaning. Plus every `needs_integration` item from the reports (known so far: the
   code-root "here" test at `session_start.py:78/167`; the unguarded state reads at `commands/state.py:33`
   and `commands/run_resume.py:62`).
5. **CHANGELOG** lines under `## [Unreleased]`, one per visible difference, from the reports; architecture
   §8 wording where a report proposes it. Also one line: `council ledger advice` prints LF line endings on
   Windows where the old helper printed CRLF.
6. **Proof on the merged result:** `python scripts/quick_validate.py`; `python evals/run_all.py --fast`;
   `ruff check .`; the ratchet printing "ShellCheck measured"; every `evals/run_cli.py` group, `timing`
   last and alone; `evals/run_hook.py --group main`; `run_audit.py`, `run_memory.py`, `run_status.py`.
   Old against new: see below.
7. **PR** from `claude/clean-behaviours`: lines before and after in `src/council/`, each clean rule, each
   visible difference with an old and new example, proof counts, what was left out on purpose. Then
   auto-merge (`gh pr merge <n> --auto --merge`). CI on Ubuntu, Windows and macOS is the gate.

Left out of this step on purpose (name them in the PR): a torn-line guard for `seat_write.add` and
`events._write`; `WINDOWS_BASH` against `os.name`; the markdown-table cell splitters; `find_entry` spans in
the memory parser; drive-letter conversions; `StateError` to Refusal (D34 pins); `repair_trail.classify`
if its builder left it.

For the owner, not to be edited: `COUNCIL_BASH` is still exported by `bin/council` and listed in §6 but
read by nothing; D29's "Held by" cell names deleted suites; `CLAUDE.md` and `CONTRIBUTING.md` say
`scripts/` stays frozen.

## Old against new (`handover/harness/`)

`oldnew.py` runs the same calls on an old and a new checkout in scratch repos and compares exit code,
stdout, stderr and every file under `.council/`. `harness/README.md` explains it. It was written and used
on Windows (Git Bash); it has not been run on Linux. If it does not run there after a short fix, say so in
the PR and rely on the scenarios and CI.

```bash
git worktree add ../old a47fb43                       # the old side
export OLDNEW_OLD=$(realpath ../old) PYTHONPATH=$(realpath handover/harness) PYTHONIOENCODING=utf-8
python handover/harness/oldnew.py --new <merged worktree> --cases handover/harness/cases_spine_a.py --out <dir>
python handover/harness/hookcmp.py --new <merged worktree> --out <dir>/hooks
python handover/harness/difflook.py <dir>/diffs.txt   # the changed lines only
python handover/harness/dangling.py <merged worktree> # every module.name reference resolves
```

Case sets: `cases_spine_a.py`, `cases_seat.py`, `cases_runs.py`, `cases_close.py`, `cases_scripts_port.py`,
`cases_launcher.py`. On PR 113 the six sets and the hooks were 869 calls. Every differing call must be a
stated difference or a known artifact: the pid in `close.lock/owner`; two runs opened in the same second
swapping `-review` and `-review-2`; the `old`/`new` folder names in `council status` outputs.

## State at handover

(filled in below as each builder reported)

| Branch | Head | Items done | Report | Proof its builder ran |
|---|---|---|---|---|
| `claude/clean-commands` | `441616b` | 7 of 7 | `reports/commands.md` | everything in its report, old against new included |
| `claude/clean-write` | `5f28de9` | 5 of 5 | `reports/write.md` | suites yes (`src/council/` 20,286 to 20,095); old against new NOT run; its `harness/cases_write.py` is written but never run |
| `claude/clean-read` | `b0d4a28` | 6 of 6 committed | see `reports/read.md` if present, else none | unknown without the report: run its groups and old against new yourself |
| `claude/clean-memory` | see `git log` | items 1 to 5 committed at the time of writing; 6 (`request.filed`) and 7 (`latest_of`) NOT done unless its report says so | see `reports/memory.md` if present, else none | unknown without the report |

The builders were stopped early because the Windows machine was shut down for the night. If a report is
missing from `handover/reports/`, that builder did not get to write it: treat every claim about that branch
as unchecked.

Open point for the owner, from `reports/commands.md` (needs_user): with no `events.tsv`, an unreadable
state file still reads as "a run from before the stream", so an append writes nothing, silently. The
refusal shows only once a stream exists. Not changed; raise it in the PR text.
