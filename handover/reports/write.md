# write builder: report

Worktree `SP\wt\clean-write`, branch `claude/clean-write`, from main a47fb43. Clean tree, nothing pushed.

## 1. Commits, oldest first

1. e55cd14 An agent start is counted through paths.append_row, the one way to append a TSV row
2. be6e61a The state file is replaced through paths.atomic_write(keep_mode=True), the one way to swap a file in
3. f22afbc A build's start time is read with clock.local_moment, the one parser of the helper's local stamp
4. 139d751 council memory check finds a name with one search in Python over the tree's own file list
5. f279d31 The helper no longer reads or writes the 0.1/0.2 .council/active-run pointer
6. 5f28de9 Keep the ratchet's gains from the clean-write items (evals/ratchet.json --update only)

## 2. Lines

`src/council/` (all tracked .py): 20,286 before, 20,095 after (-191). In all: 50 added, 241 removed.

| Item | src/council removed | added |
|---|---|---|
| 1 agent_gate | 40 | 8 |
| 2 state_write, run_resume | 15 | 4 |
| 3 hygiene | 23 | 3 |
| 4 memory_tree | 84 | 30 |
| 5 session_start, run_close, doctor, ignores | 79 | 5 |

## 3. Items

### 1. Counting an agent start
Rule: the starts row is appended by `paths.append_row` (never joins a torn line). Lives in `agent_gate.count_start`;
`_append_start`, `_filled`, `_ends_line`, `_write` are gone. The caller keeps the `before:<n>` seed row on a new or
empty file, the session id's tab turned to a space, and `try/except OSError: pass` around both writes (D20).
Visible: only at a fault. Old: a starts file that exists but cannot be read was rewritten with a fresh header and
the row counted. New: nothing is written; that start goes uncounted. (Not reproducible on Windows; shown by a unit
test with `append_row` raising.)
Scenarios: `evals/run_hook.py` `agent_gate_unwritable` gains "a starts file that can't be written lets the worker
start, uncounted — exit 0, nothing said (D20)" (agent-starts.tsv made a directory). Unit test
`tests/py/test_cap.py` `test_a_starts_file_that_cannot_be_read_or_written_leaves_the_start_uncounted`.
Pinned test `tests/py/test_cap.py:150-163` unchanged and passing (same bytes).

### 2. Replacing the state file
Rule: `state_write.change` and `run resume`'s `_unclose` write through `paths.atomic_write(file, data, ".state.",
keep_mode=True)`; `state_write.replace` is gone. OSError still becomes the same `StateError("cannot update …")` /
`Refusal("cannot update …")`.
Visible: macOS/Linux: a state file the user chmod'd (e.g. 0640) keeps its mode after any `council state`; old: reset
to the umask default. A temporary file left by a hard kill is now `.state.XXXXXXXX`, not `session-state.md.tmp<pid>`.
Scenario: `evals/run_cli.py` `resume` (group gates): "state: the state file is swapped in whole — no temporary file
left, and a mode the user set is kept" (mode part POSIX only). No pinned test changed.

### 3. The build's start time
Rule: `hygiene._read` reads `opened:` with `clock.local_moment(opened)` (`YYYY-MM-DD HH:MM[:SS]`, local);
`hygiene.stamp` is gone. Imports changed at hygiene.py lines 10 and 14 (`import time` gone, `clock` added) besides
the hunks at 100-120 and 185-190: outside the line ranges given; a trivial merge if the other builder touches imports.
Visible: a run whose `opened:` has no seconds (older helper). Old: `council check` (just me) counted every untracked
file (e.g. an hour-old `SCRATCH.md` naming verify-1 was reported). New: only untracked files newer than the run.
Scenario: `evals/run_cli.py` `check_just_me_hygiene` (group requests): "a run whose opened: has no seconds still
counts only the untracked files newer than the run" — fails on the old code (proved: copied old hygiene.py in, 2 FAIL),
passes on new.
Pinned test changed: `tests/py/test_check_parts.py:115-117` old `hygiene.stamp("2026-01-02 03:04:05") == mktime(...)`,
`hygiene.stamp("not a time") is None`; new `test_the_opened_time_is_the_helpers_local_stamp`: the same two on
`clock.local_moment(...).timestamp()` plus the minute-only form.

### 4. Searching the tree for a memory anchor
Rule: one search, `Tree._search`, over `Tree.files` (git's `ls-files -co --exclude-standard` minus `.council/`, or
the walk outside git). A name is found when it is a whole word (no `[A-Za-z0-9_]` just before or after it) in a file;
a file with a NUL byte, over `paths.MAX_FILE`, or unreadable is skipped. A name made only of word characters is
looked up among the file's words (one regex pass); any other name uses the whole-word regex, after a substring test.
`find` and `find_in` use it; `_grep`, `_run`, `_search` (old), `_patterns` temp file and both `git grep`/`grep`
calls are gone. A file path is opened as `os.path.join(native(top), native(shown(f)))`: no new absolute-path test.
Visible (all `council memory check`): same answer in and outside git, with or without grep; `.gitignore` honoured
outside the old git-grep path too; `a.b` found inside `a.b.c` (old: reported stale in a git repo); a
`Binary file … matches` line no longer counts as a name.
Scenario: `evals/run_cli.py` `runs_memory` (group runs): "memory check: a name is found as a whole word in a tracked
or untracked file — a.b inside a.b.c too — and not in an ignored or a binary file, or inside a longer word" and
"memory check: outside git the same search gives the same answer".
Pins: `evals/run_cli.py:1699-1705` pass (runs group). `:1884-1919` are in `memory_speed`, group timing, which I was
told not to run: I ran that block's checks from a copy of run_cli.py with its two timed parts cut
(`SP\scratch\write\mk_memcheck.py`): 11/11 on main and 11/11 on this branch.
Timing (`council memory check`, median of 3, `SP\scratch\write\timing_*.py`, outputs identical old/new):
- this plugin's tree in a scratch repo (488 files, 88 entries): old 3.06 s, new 0.44 s.
- generated tree, 5,000 files (97 entries): old 1.29 s, new 1.16 s.
  A first round had outliers (3.3 s and 50 s on single new runs) while other builders loaded the machine; a second
  round had none (new runs 1.08, 1.16, 1.20 s). Not slower.

### 5. The 0.1/0.2 `active-run` pointer (A1-A4 only)
Rule: the helper neither reads nor writes `.council/active-run`. Gone: `session_start._active_run` and its call (the
call site is now `if listed: _runs(...)`), `run_close._empty_pointer` and its call, `doctor.active_run`, its call and
`ACTIVE`; `ignores.KEPT_OUT` is `("runs/", "asks/")` (the now-dead `else want` branch in `keep_out` dropped). An
existing `active-run` file or `.gitignore` line is left as it is. SKILL council-init line ~188 now says the
.gitignore holds `runs/` and `asks/` and run open "adds either line that is missing". A5-A8 untouched.
Visible: old SessionStart said "UNFINISHED COUNCIL RUN …" / "Also open (an older run layout)" for a run open under
`<mode>-output/` behind the pointer; new says nothing. Old close emptied a pointer naming the run; new leaves it.
Old doctor warned "an older run is still marked open" / "active-run still points at a closed run" / "points at a
folder that no longer exists"; new is silent. Old run open wrote `runs/\nasks/\nactive-run\n` into a new
.gitignore; new writes `runs/\nasks/\n`.
Scenario added: `evals/run_cli.py` `runs_gitignore`: "run open, doctor and close: an old active-run file is left byte
for byte, its line is not added to .gitignore, and doctor says nothing of it".
Pinned tests changed on purpose:
- `evals/run_hook.py:395-397` old "old pointer into runs/: the run is reported once"; new "an old active-run pointer
  is read by nothing: the run it names is reported once, by the usual scan" (same assertion).
- `evals/run_hook.py:559-590` (legacy block): old checks "flagged unfinished", "mode inferred", "never says this
  session was running it", "build log … never called probably finished", "final deliverable … offered to close as
  complete" are gone; new "not reported — nothing reads the pointer now" and "after a compaction too, the old run is
  not named, and the pointer is left byte for byte". Kept: the CRLF check (now named "legacy CRLF config and memory")
  and "legacy root conventions.md: found" (A8). Header lines 17-18 reworded.
- `evals/run_cli.py:3329-3332` (now ~3378): old "empties the old active-run pointer when it names the run"
  (`strip() == ""`); new "read by nothing and left as it is" (`== run2 + "\n"`).
- `evals/run_cli.py:5954` old `{"runs/","asks/","active-run"} <= set(gi_lines)`; new `sorted(gi_lines) == ["asks/","runs/"]`.
- `evals/run_cli.py:6010` old `["active-run","asks/","runs/"]`; new `["asks/","runs/"]`.
- `evals/run_cli.py:5973` (a 0.6.0 home's `runs/\r\nactive-run`) unchanged: shows an old line is left.
- `tests/py/test_ignores.py:36-38` expected bytes without `active-run`, plus a case: an existing `active-run` line stays.
  `test_ignores.py:23-31` unchanged (it asks `ignores()` about a path; not what keep_out writes).

## 4. Proposed CHANGELOG lines

### Changed
- The agent gate appends its start row the one way every TSV row is appended; a starts file that cannot be read is
  no longer rewritten, and that start goes uncounted.
- A run's state file is swapped in the one way every file is: on macOS and Linux it keeps a mode you set on it, and a
  temporary file left by a killed write is now a hidden `.state.*` file.
- `council memory check` searches the tree itself: the same answer in and outside git, with or without grep;
  `.gitignore` is honoured; files with a NUL byte or over 4 MB are not searched.
- The helper no longer reads or writes the 0.1/0.2 `.council/active-run` pointer: a run left open outside `runs/`
  is no longer reported at session start, `run close` no longer empties the pointer, `doctor` no longer warns about
  it, and `run open` no longer adds an `active-run` line to `.council/.gitignore`. A file or line already there is
  left as it is.

### Fixed
- `council check` (just me) counted every untracked file for a run whose `opened:` had no seconds; it now counts
  only the files newer than the run.
- `council memory check` called a dotted name such as `a.b` stale when it appeared only inside a longer one
  (`a.b.c`), and could count grep's "Binary file … matches" line as a name.

Architecture §8: the row "Write a shared TSV row" can name `paths.append_row` as its owner; "Swap a file in" already
lists the state file. If §8 or §4 mentions grep for the memory search or `active-run`, that wording goes.

## 5. Proof

| Command | Result |
|---|---|
| `python scripts/quick_validate.py` | validation OK: 0 warnings |
| `python evals/run_all.py --fast` | 11 jobs, 0 failed (structural 711/711, ratchet 308/308, unit 439/439) |
| ruff check . | All checks passed |
| `run_ratchet.py --update`, then `run_ratchet.py` | 315/315, "ShellCheck measured" |
| run_cli `runs` | 539/539 (after item 5) |
| run_cli `gates` | 171/171 |
| run_cli `collect` | 65/65 |
| run_cli `reports` | 48/48 |
| run_cli `requests` | 215/216: the judgment fixture only (python3 Store stub, exit 49; same on main) |
| run_cli `filing` | 27/27 |
| `run_hook.py --group main` | 291/291 (after item 5) |
| `run_memory.py` | 61/61 |
| `run_status.py` | 165/165 |
| memory_speed checks (copy, timed parts cut) | 11/11 old, 11/11 new |

NOT RUN (machine shutting down; told to start no new suite or comparison):
- the old-against-new runs over all six case sets (`cases_spine_a`, `cases_seat`, `cases_runs`, `cases_close`,
  `cases_scripts_port`, `cases_launcher`) and `hookcmp.py`. Expect `cases_close.py` `pointer` to differ (old empties
  the pointer, new leaves it) and any case set whose run open writes a fresh `.gitignore` to differ by the
  `active-run` line; neither checked.
- my own case file `SP\scratch\write\cases_write.py` (written, never run): pointer_close, pointer_doctor,
  ignore_lines, minute_opened, memory_words.
- `run_audit.py` (I touched no audit code).

## 6. needs_integration
None required. Note for the merge: `commands/hygiene.py` import lines 10 and 14 changed (see item 3);
`commands/session_start.py` import line 10 (`fnmatchcase`) removed, outside lines 60-80 and 160-170.

## 7. needs_user
- Item 5 drops the SessionStart banner for a 0.1/0.2 run left open under `<mode>-output/` (the map called this the
  real loss); done as briefed.

## 8. Stops, and tempted but not done
Stops: none.
Tempted, not done:
- `session_start._runs` still returns `driving`, which nothing uses now (lines 160-170 belong to another builder).
- `records/ignores.py` module docstring says bin/council keeps a bash copy (`ensure_ignored`); bin/council has none.
- `test_ignores.py` test name `test_keep_out_writes_what_ensure_ignored_wrote` names the gone bash function.
- `paths.append_row` reads the whole file to test the last byte (the map suggests reading one byte); not my file.
