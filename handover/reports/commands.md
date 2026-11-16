# Clean behaviours: commands builder

Worktree `SP\wt\clean-commands`, branch `claude/clean-commands`, from main a47fb43. Not pushed.

## 1. Commits, oldest first

| Commit | Item |
|---|---|
| 34dd894 | 1. One reader of a diff hunk header: `diff.header` |
| e13b41d | 2. index and hygiene read lines through `bytewise.records` |
| 28bf846 | 3. `earlier.hits` hands back a `Hit` per mention |
| b6c6479 | 4. The events-schema stamp is read through `state.text`; a repeated detail key: the first wins |
| 4cdd701 | 5. `council changed`: `--glob` and `--each` are ordinary cli flags |
| fa93f5c | 6. Dates through `clock`: `clock.now_date` is the one date-only stamp |
| 09230e4 | 7. `json_esc`: every control character below 0x20 becomes a space |
| (last) | `evals/ratchet.json` rebuilt with `--update` |

## 2. Lines

`src/council/` (`git ls-files 'src/council/*.py' 'src/council/**/*.py'`): 20,286 before, 20,297 after (+11).

| Item | src removed | src added | note |
|---|---|---|---|
| 1 hunk header | 29 | 38 | `Hunk` NamedTuple and `header()` with docstrings (+15 in diff.py); three inline parses gone |
| 2 records | 11 | 7 | `index.records` and `hygiene._records/_file_lines` are now one-line folds |
| 3 earlier | 20 | 30 | the `Hit` NamedTuple and its docstring (+8); join/split and tab rows gone |
| 4 events | 9 | 22 | `_unstamped` (the D19 refusal, +10), `details` loop (+5) |
| 5 changed | 30 | 7 | `changed.options`, `USAGE`, the `cli._flag` branch gone |
| 6 dates | 9 | 14 | `clock.now_date` (+3), one-date field in ask (+1), imports |
| 7 json_esc | 2 | 3 | docstring one line longer |

Tests and evals: +127 / -31 (10 files, including `evals/ratchet.json`).

## 3. Items

### Item 1. The diff hunk header (map section 1)
Rule: `diff.header(line)` (src/council/diff.py) gives `Hunk(old, new, count)` for a line git writes as
`@@ -a[,b] +c[,d] @@` (matched from the start of the line, a missing count is 1), and `None` for any other line.
`diff.files`, `cite_origin.hunks`, `index.hunks` and `hygiene.added` read headers only through it, and each skips a
`None` header: the numbering in force stays. It does not use `cells.leading`.

On every header git writes: byte-identical (all eval groups pass; old-against-new shows nothing). On a malformed one:
- `diff.files` (council patch save, patch_checks): was reset to line 0/0 and left the file header; now ignored, the
  previous hunk's numbering goes on (and a malformed first header leaves the file in its header state, so its lines
  are not counted).
- `cite_origin.hunks` (council check origins): was the third blank-separated word read with awk's leading number
  (`+x` as 0, `5,x` as a pure removal, `-1 5` with no plus as 5); now the hunk is skipped.
- `index.hunks` (council index `- hunks:`): was the first `+N[,M]` anywhere on a line starting `@@` (so a combined
  `@@@` header or a tab-separated one counted); now skipped.
- `hygiene.added` (council check just-me hygiene): was the first `+N` anywhere, else the number kept; now the number
  in force is kept and the line is ignored.
Unreachable from the helper (every diff comes from git `-U0`/`--binary`), so no scenario can feed one; unit tests:
`test_patch.DiffTest.test_a_hunk_header_as_git_writes_it_and_nothing_else`,
`test_a_malformed_header_keeps_the_numbering_in_force`, `test_check_parts...test_paths_left_out_and_hunks` (extended),
`test_cite_origin_reads_the_new_side_and_skips_a_malformed_header`. No pinned test changed.

### Item 2. Line readers onto `bytewise.records` (reading-rules item 2)
Rule: `index.records(data)` is `bytewise.records(<UTF-8 text>)`; hygiene's git-output lines are
`bytewise.records(read(data), fold=False)` (today's: every CR kept), its file lines `bytewise.file_lines(path)`
encoded back to bytes. Coded against today's `bytewise` API.
Visible: one corner, as stated. On Windows an untracked file whose last line has no newline and ends in CR keeps
that CR in the `+line` text `council index` reads, so a definition that needs the line end (a shell `name()`) is no
longer named. Old `- symbols: first, last_one`, new `- symbols: first` (file `first() {\r\n  :\r\n}\r\nlast_one()\r`).
POSIX already kept it. Hygiene's file lines have the same corner, but `hygiene.kind` and `Hit` strip every CR, so
nothing shows.
Scenario: `evals/run_cli.py` `index_limits` (collect), check "index: an untracked file's unterminated last line keeps
its CR, on every OS". No pinned test changed.

### Item 3. `earlier.hits` (map section 5)
Rule: `earlier.hits` returns `Hit(path, where, text)` per mention (records/earlier.py); `earlier.line(hit)` joins the
three fields with em dashes. No join-then-split of the paths, no CR removal, no tab-joined rows; each path is taken
as given (`scope.normp` as before); a list of only empty paths gives `[]` as before.
Visible: a mentioned line holding a tab is shown whole (clipped at 120 as before), in `council prior` and the index's
"Earlier council work" list. Old `a.txt — reviews/2026-09-05-tab.md:2 — 6 · P3 · a.txt:1`, new `... a.txt:1<TAB>then<TAB>more words`.
A `council prior` path word holding a newline or CR: old split it / dropped the CR (and found `a.txt` in
`$'a.txt\nother.txt'`), new looks for the word as given (no mention). Seen from Git Bash directly; through the
harness's Windows process launch the newline never reaches the helper, so that call reads the same there.
Scenario: `runs_change_index` (runs), check "prior: a mentioned line that holds a tab is shown whole".
Pinned test changed on purpose: `tests/py/test_earlier_scope.py:88-94`, old
`assertEqual(hits[0], "src/cache/x.py\treviews/2026-01-01-a.md:5\t...")` and `earlier.line(hits[1]) == EM.join(hits[1].split("\t"))...`;
new compares tuples (`("src/cache/x.py", "reviews/2026-01-01-a.md:5", "see src/cache/x.py:4 for it")`) and the
joined line. New test `test_a_mentioned_line_with_a_tab_is_shown_whole_and_a_path_is_taken_as_given`.

### Item 4. The events-schema stamp, and repeated detail keys (map section 6, reading-rules item 4)
Rule: `events._schema` is `state.field(state.text(run), "events-schema")`: the stamp is read by the state's one
guarded read. Where a stream exists and no stamp was read, `events._unstamped` tells a state the guarded read leaves
out (a link, a file outside the run, one over 4 MB) from one with no stamp, and the refusal says so (D19):
`the run's session-state.md is a link, lies outside the run or is over 4 MB, so its events-schema stamp is not read
and no event can be recorded — put a plain copy of it, under that size, in its place: <path>`. Used by
`events.append` (every event write) and `events.check` (`council run events check`, `council doctor`).
`events.details`: the first of a repeated key wins (setdefault), as `state.header`.
Visible:
- A state over 4 MB (or linked): `council run events check` old exit 0 `events: valid · 1 event(s)`, new exit 1 with
  the sentence above; every event write refuses with it (old wrote the event). With no events.tsv such a run reads
  as a run from before the stream (append returns False; old would append), as the map says.
- `council audit` "skipped on purpose": a detail `from=prepare;skipped=judge;reason=ruled;skipped=all of it` old
  named `all of it`, new `judge`. Note: `council state skip=` turns `;` in the reason into `,` before it is written
  (old against new on that path: same), so only a hand-edited events.tsv reaches it.
Scenarios: `evals/run_cli.py` (runs, beside the legacy-run checks) "run events check: a state over 4 MB is named, with
the next step, not called unstamped"; `evals/run_audit.py` "a skip reason that itself holds ;skipped= never
replaces the helper's own list of skipped stages". Unit tests: `test_events.AppendTest.test_a_state_past_the_guarded_read_is_named_with_the_next_step`
(4 MB state and a symlinked one), `test_details_the_first_of_a_repeated_key_wins`. No pinned test changed (the
"without an events-schema stamp" pins at test_events.py:101, :154 and run_cli.py:729 still hold for a state that is
read and has no stamp).

### Item 5. `council changed` flags (map section 8)
Rule: `--glob` is in `cli.VALUED` and `cli.REPEATED`, `--each` in `cli.SWITCHES`; `changed.main` reads
`args.lists["glob"]` (each pattern through `expand`, order kept) and `args.value("each")`, and calls
`cli.no_words`. `changed.options`, `changed.USAGE` and the special case in `cli._flag` are gone. Exit codes unchanged.
Visible (all exit 2, refusal sentence only):

| Call | old | new |
|---|---|---|
| `changed --glob` | `--glob needs a pattern` | `--glob needs a value` |
| `changed --glob= -- true` | `the --glob pattern(s) '' match no file ...` | `--glob needs a value` |
| `changed --glob a.txt extra` | `usage: council changed [--base <ref>] ...` | `changed doesn't take 'extra' — see: council help` |
| `changed --each=1` | `unknown option '--each=1' — see: council help` | `--each takes no value` |
| `version --each` | `version doesn't take '--each' — see: council help` | `version doesn't take --each — see: council help` |
| `help --glob x` | `help doesn't take '--glob x' — see: council help` | `help doesn't take --glob — see: council help` |

Scenario: `evals/run_cli.py` changed block (requests), check "changed: --glob and --each are ordinary flags,
refused as every flag is". Pinned tests changed on purpose: `tests/py/test_cli.py:29-31`
(`test_glob_words_pass_through`: old `parse(...).words == ["changed", "--glob", "*.py", "--each", "--glob=x"]`; new
`test_glob_and_each_are_ordinary_flags`: words `["changed"]`, `lists["glob"] == ["*.py", "x", "-*.sh"]`, each `"1"`,
and the three refusals); `tests/py/test_gate_command.py:218-221` (`test_options` on `changed.options`: removed,
`expand` keeps its own `test_expand`).

### Item 6. Dates (map section 9a)
Rule: `clock.now_date()` is the one date-only stamp. `ask.Filing` reads it once (`self.today`) for a new request's
file name and a continuing request's section heading; `ask-saved=` is `clock.now_min()`; `memory_write`'s two
`--today` are `clock.now_date()`; `records/audit_file.py` "Taken at:" is `clock.now_utc()`. `import time` and the
datetime import go from those three modules. No visible change. Unit test `test_clock.test_the_date_stamp`.

### Item 7. `json_esc` (map section 9b, option 1)
Rule: `gate_run.json_esc` escapes `\` and `"` and turns every character below 0x20 into a space (tab, CR, LF as
before). Changed where it is: moving it beside the verdict reader removes no line.
Visible: a gate command (or name, or invalid reason) holding a form feed, ESC, NUL or another control character:
old wrote it raw, so the verdict was not valid JSON and `council status` left the gate out; new writes a space, the
verdict parses and the gate is listed. Old `"command": "echo 'a<ESC>b<FF>c'"`, new `"command": "echo 'a b c'"`.
Verdicts already on disk still match in `verdicts.green` for every command that held only tab/CR/LF.
Scenario: `runs_gates_and_seats` (runs), check "gate: a command holding control characters still leaves a verdict of
valid JSON, each one a space". Pinned test extended on purpose: `tests/py/test_gate_command.py:133` keeps its old
assertion and gains `json_esc("f\x0cg\x1bh\x00i\r\nj\x7fé") == "f g h i  j\x7fé"` and a `json.loads` round trip.

## 4. Proposed CHANGELOG lines

### Changed
- `council changed`: `--glob` and `--each` are ordinary flags; a refusal for a missing or empty `--glob`, a value
  given to `--each`, a stray word, or `--glob`/`--each` given to another command now says what it says for any flag.
- `council prior` and the change index's "Earlier council work" list show a mentioned line whole when it holds a
  tab (it was cut at the first tab); a path word is looked up as given.
- A run whose `session-state.md` is a link, lies outside the run or is over 4 MB no longer records events through
  it: the refusal names that and the next step (it used to read the stamp anyway).
- `council index`: on Windows an untracked file's last line with no newline keeps its CR, as on every other OS and
  in every other reader.

### Fixed
- A gate command holding a control character other than tab, CR or newline left a verdict that was not valid JSON,
  so `council status` left the gate out; each such character is now a space.
- `council audit`'s "skipped on purpose" note could take the skipped stages from the user's skip reason when the
  reason held `;skipped=`; the helper's own list (the first) now wins.

Architecture §8: if §8 names "a diff hunk header" or the date stamps, it can say "`diff.header` is the one reader of
a hunk header" and "`clock.now_date`/`now_min`/`now_sec`/`now_utc` are the stamps"; the events row can say the stamp
is read through `state.text`. I did not open §8 to check its wording (not my file).

## 5. Proof
FILLED BELOW

## 6. needs_integration
- `src/council/commands/state.py:33` and `src/council/commands/run_resume.py:62` read `state.path(run)` without the
  guard (no link, size or containment check). To follow item 4's rule they should read through `state.text(run)`
  (and give the same D19 refusal when it is left out). Not my files.

## 7. needs_user
- Item 4 leaves one asymmetry the brief did not settle: with no events.tsv, an unreadable (linked / huge) state reads
  as a run from before the stream, so `append` returns False and writes nothing, silently (the map's own note). The
  refusal shows only once a stream exists. Raising there too would make every command on such a run refuse; say if
  you want that.

## 8. Stops, tempted, not done
No stops. Tempted, not done:
- `index_symbols.py:84-85` strips the hunk header with its own regex to get the function context; `diff.header` could
  return that context too (map section 1, item 5). Not in my brief.
- `index.records` stays as a one-line delegator (five callers) rather than inlining `bytewise.records(_text(...))`
  five times.
- `cite_origin` still decodes `-U0` output itself rather than through `bytewise`.
