# memory builder: report (stopped early: machine shutdown)

Worktree `SP\wt\clean-memory`, branch `claude/clean-memory`, from a47fb43. Nothing pushed.

## 1. Commits, oldest first

- e1722c6 Memory edits find entries by the memory parser's own line tests (item 1)
- e388df4 One reader of the config's Roster table (item 2; a ruff line-length fixup squashed in)
- a26a38e council status sizes the memory file memory.locate finds (item 3)
- 2448b6c council status counts drafted lessons with the memory parser (item 4)
- e7c01da The build log's Converge table has its reader in records/converge.py (item 5)
- (last) Keep the ratchet's numbers after the memory clean-up (evals/ratchet.json, `--update`: 0 numbers went down, ShellCheck measured)

**Not done: items 6 (filed request) and 7 (latest check).** I did not start them.

## 2. Lines

`src/council/`: 20,286 before, 20,271 after. Per item (src/council only, added/removed):
item 1 +120/-112 (memory_draft 438 -> 386; memory_entries 427 -> 487), item 2 +27/-32, item 3 +17/-41, item 4 +12/-18,
item 5 +92/-80 (new records/converge.py, 87 lines).

## 3. Items

**Item 1. Memory entries (partial fold).** The rule: `council memory propose|accept|reject` test lines with the memory
parser's own functions, now public in `records/memory_entries.py`: `Shade`/`visible` (comments and fences; the Parser
uses `Shade` too), `heading_of` (any number of #), `entry_id` (on `_opening`, shared with `Parser.entry`), `cand_id`
(shared with `Parser.cand`) and `section(name)` (proposed / rejected / observed / '' by `kind()`, proposed and rejected
being `off` plus the `[#* ]*propos` / `[#* ]*reject` name; `pending()` and `memory.replace` use it too). memory_draft's
`visible`, `entry_id`, `cand_id`, `section_kind` and `HEADING` are gone; `find_entry`, `section_end`, `sections` stay.
`load_memory` decodes UTF-8 with surrogateescape (the editing stays in str, and `write` encodes with surrogateescape, so
every untouched line keeps its bytes); the tests run on `read(lines)` = `bytewise.lines(bytewise.text(...))`, which is
exactly the parser's C-locale text, line for line. `verifier_reason` splits on LF only.
Visible differences:
- A non-UTF-8 memory file: before, exit 2 with `memory: 'utf-8' codec can't decode byte 0xe9 ...`; now it is moved in
  and the Latin-1 bytes stay.
- A `####### F-2: x` line inside an entry: before, reject refused (`the edit would change which memory lines go unread`);
  now the entry ends there and the line stays.
- Section words: `## _Proposed_` was a proposed target (and replace then refused); now it is not, so a new `## Proposed`
  section is made. `## Observed failures pending review` was an observed target; now not (parser says off).
  `## Pending proposals`, `## Draft`, `## Declined ideas`, `## Retired`, `## Decisions (proposed)`: no outcome change.
Scenario: `evals/run_cli.py` `memory_moves_by_the_parsers_rules` (group runs): passes here; on the old tree both checks fail
with the two messages above. Unit tests: `tests/py/test_memory_entries.py` `test_a_section_files_by_the_parsers_words`,
`test_the_line_tests_an_editor_shares`. No pinned test changed.
Differential (`SP\scratch\memory\drafdiff.py`, `drafdiff2.py`, `cmp.py`, `classify.py`): 20,000 random files per corpus,
old (main-cut) against new: headings, sections, `find_entry` for every id, `insert` output and `move` to observed and
rejected for every F id. Helper-shaped corpus (what the helper writes plus comments, fences, CRLF): **0 of 20,000 differ**.
Wide corpus (the map's odd shapes added): 6,722 differ, and every one of them holds a 7+-hash heading or one of the
disputed section words; `classify.py` finds 0 unexplained.

**Item 2. Roster.** One reader `config.roster_table(home) -> list[Seat(seat, slug, lens, reference)]` by roster_rows'
rule plus the Lens column ('' for empty). `roster`/`roster_rows` are gone; doctor (`row.slug or "-"`, `row.reference or "-"`)
and `memory.slugs` (`slug not in ("", "-")`) project it exactly as before. Status names seats from it via
`bytewise.shown` + `clean`; empty Lens: the Seat alone. Differences (status only): `**Kent Beck**`/`*Tests*` was
`*Tests* (**Kent Beck**)`, now `Tests (Kent Beck)`; a seat with empty Lens was named from its slug (`S3`), now `Docs Seat`;
a table outside `## Roster` (or `## roster`) no longer names seats; a linked config is now followed.
Scenario: added check in `runs_card_says_what_is_known` (run_cli.py, roster rows s2, s3). Pinned tests changed:
`tests/py/test_config.py` `test_roster` (old: table with no heading gave `[("Security","sec","auth")]`; new: under `## Roster`
gives Seat tuples, under `## Seats` gives `[]`), `RosterRowsTest.test_rows_as_the_helper_read_them` (old (slug, seat, ref)
with "-"; new Seat tuples with ''), lines 28/35 (`config.roster` -> `config.roster_table`).

**Item 3. Memory file's place.** `config.memory_path` gone. `status.oversized_memory` sizes `memory.locate(home).path`;
the over-limit test is `memory.oversized(path)` (records/memory.py), used by `size_note` too. Differences: a configured
`/docs/x.md` is the repo's file (was: no warning); `- Conventions:` (capital) names no file (was: sized); a linked config
is followed; `## Memory2` reads as a Memory section (locate's rule). Scenario: run_cli `runs_open`, two status checks
(the old tree fails both); `evals/run_status.py` memory-size check for `/docs/...`. Pinned test changed:
`tests/py/test_config.py` `test_memory_path` -> `test_memory_line` (old line 119 pinned the capital `Conventions:` read;
new asserts it is None), lines 27/35 (`memory_path` -> `memory_line`). Note: the `path.is_absolute()` line in the old
`oversized_memory` (status.py:195) went away with the function it was in; nothing replaced it (locate's `absolute()` does that job).
Import time, status tool run by path (median of 9, summed top-level imports): main-cut 66.7-78.2 ms, after 68.2-68.8 ms
(measured in pairs: 66,984 vs 68,190 us and 66,729 vs 68,750 us): about +1.5 ms. status already imported records/memory.

**Item 4. Drafted lessons.** `snapshot.proposals_in` gone; `memory.proposals(home)` (locate, parse, `pending`); None when
no home, no file or an empty file. Differences: the count appears for a configured memory path; a note heading, a fenced
example and a commented heading are no longer counted; an entry at `####`, a bullet entry and a `- PROPOSED` line under
another section now are. Scenario: run_cli `runs_open` check "drafted lessons are counted in the configured memory file"
(old tree fails it).

**Item 5. Converge move.** `records/converge.py`: `result_of`, `fixed_after`, `read(run, deliverable)`, `table(content)`,
`RESULT`, `KEYS`; code moved verbatim (the `path.is_absolute()` line carried unchanged). status_closing imports it as
`final_check` (its local `converge` variable would shadow the module). No behaviour change; run_status 166/166.

## 4. CHANGELOG lines (proposed)

### Fixed
- `council memory propose | accept | reject` work on a memory file that is not valid UTF-8, and keep every byte of the lines they do not change.
- `council memory accept | reject` read a heading of seven or more `#` as the memory parser does: it ends the entry above it.
- `council status` sizes the memory file every other command reads (a configured `/docs/x.md`, a linked config), and counts drafted lessons in it with the memory parser, so a configured path is counted and a note, a commented heading or a fenced example is not.
### Changed
- `council memory propose | accept | reject` file under a section by the memory parser's words: `## _Proposed_` and `## Observed failures pending review` are no longer targets.
- `council status` names roster seats from the `## Roster` table only, without bold or italic marks, and a seat with an empty Lens by its Seat.
- A `- Conventions:` line in capitals no longer names the memory file for `council status` (the key is `conventions:`, as everywhere else).

Architecture §8: the memory_draft exception to D32 shrinks to the range finder (`find_entry`, `sections`, `section_end`);
`records/converge.py` owns the Converge table; the §8 debt note about memory_path can go.

## 5. Proof

Run: `ruff check .` all passed; `run_status.py` 166/166; `run_cli.py --group runs --block` `runs_open` 92/92,
`runs_card_says_what_is_known` 7/7, `memory_moves_by_the_parsers_rules` 2/2 (and the old tree fails the new checks);
unit tests test_config, test_memory_entries pass; `run_ratchet.py --update` ShellCheck measured; the 20,000-file
differentials above. **Not run** (stopped for the shutdown): `quick_validate.py`, `run_all.py --fast`, plain `run_ratchet.py`,
full run_cli groups `runs`, `reports`, `requests`, `filing`; `run_memory.py`; `run_hook.py --group main`; the old-against-new
harness over the six case sets and hookcmp; my own case file. These must run before merge.

## 6. needs_integration

- `src/council/commands/memory_write.py:answer` (the `waiting` line): `re.match(r"[#* ]*propos", bytewise.lower(c[5]))` -> `memory_entries.section(c[5]) == "proposed"`.
- `src/council/commands/session_start.py:_memory`: the pending count could be `memory.proposals(home)`.
- `evals/ratchet.json` `parsers` may drop memory_draft (it still parses ranges, so I left it).

## 7. needs_user

None.

## 8. Stops and tempted

Stopped: items 6 and 7 (not started), and the proof listed as not run. Tempted, not done: `find_entry`'s unread list
duplicates the parser's `skipped()` and its table-row test (`TABLE_CELL`) differs from `Parser.table` (no closing pipe
needed there); `doctor_memory.size` keeps its own size test (`// 1024`), a third beside `memory.oversized`; memory_draft
reads `--said` as strict UTF-8.
