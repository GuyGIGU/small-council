# Parsers map (batch B): one job parsed in two or three places

Tree read: `scratchpad\wt\cut-views` (HEAD 56e5560). Nothing in it was changed. Snippets are in
`scratchpad\maps-clean\scratch-b\` (hunk.py, mem.py, mem2.py, mem3.py, memp.py, roster.py, earlier.py, schema.py, props.py,
filed.py, latest.py, changed.py, esc.py), each run with `PYTHONIOENCODING=utf-8 PYTHONPATH=<tree>\src`.
All paths below are relative to `src/council/` unless they start with `evals/`, `tests/` or `docs/`.

Verdict table (details in each section):

| # | Item | Real behaviour difference? | Fold shape |
|---|---|---|---|
| 1 | hunk header (4 copies, not 3) | Only on a header git never writes | plain fold, one parser in `diff.py` |
| 2 | memory entries: memory_draft vs memory_entries | Yes, on three inputs (non-UTF-8 file, section words, 7+ hashes) | partial fold only; two jobs |
| 3 | config.roster vs roster_rows | Yes, many (columns returned differ too) | one table reader, two projections |
| 4 | memory_path vs memory.locate/memory_line | Yes (linked config, `/x`, `Memory2`, `Conventions:`, BOM) | retire memory_path; status uses `memory.locate` |
| 5 | earlier.hits round trip | One real bug (a tab in the mentioned line); the rest is unreachable | structured hand-off |
| 6 | events._schema vs state.text | Yes on a linked or over-4 MB state file (hand edits only) | pick a side; see section |
| 7 | views: five sub-items | proposals_in yes; filed_request yes; latest_of no (one hand-made tie); converge_of is an owner move; read_claims already gone | mixed |
| 8 | changed.options vs cli flags | Refusal text only (and `--glob=`) | fold onto cli |
| 9 | ask/memory_write dates; json_esc | dates: none; json_esc: yes (writes invalid JSON for 3 control chars) | dates plain fold; json_esc a choice |

---

## 1. Diff hunk header (`@@ -a,b +c,d @@`)

### The copies (four, not three)
1. `commands/cite_origin.py:16-37` `hunks(diff, spans)`. Splits on blanks, takes the third word, drops a leading `+`, reads
   start and count with `cells.leading` (awk's leading number, so `x` reads as 0). Needs the line to start `"@@ "`.
   Called from `cite_origin._one` (lines 93 and 97), from `cite_origin.origin`, from `check.py:136`, so by `council check`
   for every citation that resolved (when the run has a base).
2. `commands/index.py:130-143` `hunks(diff)`. `re.search(r"\+[0-9]+(,[0-9]+)?", line)` anywhere in a line that starts `@@`.
   Returns the display string `12, 30-34, removed near 7`. Called from `Index` (index.py:199) so by `council index`
   (and what `run open` / `prior` do through it).
3. `commands/hygiene.py:79-99` `added(top, since)` (the header test is line 90). `re.search(rb"\+[0-9]+", line)` on a line that starts `@@`; keeps the start only; counts added lines itself. Reached from `hygiene._read`
   (hygiene.py:183-188), `hygiene.hits` (223), `check.py:189-192`, so by `council check` (the build-hygiene scan).
4. `diff.py:8` `HUNK = re.compile(r"@@ -([0-9]+)(?:,[0-9]+)? \+([0-9]+)(?:,[0-9]+)? @@")` used in `diff.files` (lines 49-52).
   A malformed header gives `(0, 0)` and does NOT skip. Reached from `commands/patch.py:66` (`council patch save`) and
   `patch_checks`. This copy was not in your list; it is the one that already has a shared-looking owner (architecture §3
   lists `diff.py` as "a unified diff's files and lines").
5. Not a number parse but a fifth reader of the same line: `commands/index_symbols.py:84-85` strips `^@@[^@]*@@[ \t]*` to get the
   function context after the header. It reads the other half of the line. No conflict, but a shared header parser would return
   that context too.

### Where they disagree (snippet `hunk.py`; start/count each copy reads)
Well-formed git headers (`-1,2 +5,3`, `-1 +5`, `-1 +5,0`, `+05,3`): all four agree (start 5, count 3/1/0; octal-looking `05` read as 5 by all).
They disagree only on headers git never writes:

| Input | cite_origin | index | hygiene | diff.py |
|---|---|---|---|---|
| `@@ -1 +x @@` | start 0, count 1 | skipped | start 0 (keeps the previous number, here 0) | (0, 0) |
| `@@ -1 +5,x @@` | start 5, count 0 (`x` is 0: treated as a pure removal) | `5` (count dropped) | 5 | (0, 0) |
| `@@ -1 +5@@` (no space) | start 5 | 5 | 5 | (0, 0) |
| `@@ -1,2 @@ +7,2` (no plus word) | start 0 | `7-8` (finds the `+7,2` in the trailing text) | 7 | (0, 0) |
| `@@ -1 5 @@` | start 5 (third word, no plus needed) | skipped | skipped | (0, 0) |
| `@@@ -1 -2 +5,3 @@@` (combined diff) | nothing | `5-7` | 5 | (0, 0) |
| `@@\t-1\t+5,3\t@@` (tabs) | nothing (needs `"@@ "`) | `5-7` | 5 | (0, 0) |
| `@@  -1  +5,3  @@` (two spaces) | 5-7 | 5-7 | 5 | (0, 0) |
| `@@ -1 +5,3 @@ ctx +9,9` | 5-7 | 5-7 (first match) | 5 | 5 |

Index and hygiene can pick the wrong `+N` if the function context after `@@` holds a `+N` AND the real new side is malformed;
that cannot happen on a valid header (the first match is the real one).

### Can the helper produce the disagreeing input?
No. Every diff reaching these four comes from `git diff ... -U0` / `git diff --binary` (cite_origin.py:93, index.py:~195,
hygiene.py:83, patch.py:62), or index.py synthesises `+line` text with no header. git writes only `@@ -a[,b] +c[,d] @@`.
A malformed header can come only from a hand-fed diff, and no command takes a diff from the user (`patch save` diffs the tree itself).
Combined-diff `@@@` would appear only for a merge diff with `-c`/`--cc`; none of the four commands asks for one.

### What a user would see change under one parser
Nothing, on any input a real repo produces. `council check` origin words, `council index` `- hunks:` line, the hygiene lines,
and `council patch save` stay byte-identical. Changes appear only for a hand-made diff in a test.

### Checks that pin today's behaviour
- `tests/py/test_check_parts.py:132-137` `index.hunks(["@@ -1,2 +3,0 @@", "@@ -9 +12 @@", "@@ -20 +30,5 @@", "+@@ not one"])` (well-formed only).
- `tests/py/test_patch.py:20-43, 82-103` (`diff.files` with `@@ -1,2 +0,0 @@`, `-3,3 +3,4`, `-0,0 +1`).
- `evals/run_cli.py:1070, 1169` (`- hunks:` text and `303-304`), `1983-1990, 2137-2146` (origin words introduced/touched/pre-existing),
  `5713-5820` (`check_just_me_hygiene`, hygiene hits with line numbers `ios/Notebook.swift:6`).
- No test feeds a malformed header to cite_origin, index or hygiene, so none pins the disagreement above.

### Decisions / contracts
None touched. D32 is about council files; a diff is git output, so `diff.py` (top level) is the right owner, not `records/`.
D23: no contract name changes.

### Owner, size, risk
Owner: `diff.py` (architecture §3 row for `src/council/`: "`diff.py` (a unified diff's files and lines)"). Add
`header(line) -> (old_start, new_start, new_count) | None` using the existing `HUNK` plus an optional `,d`, `None` when
malformed; `diff.files` and the three callers use it and skip a `None` header (diff.files would then keep the previous numbering
instead of resetting to 0; pick one and say it). Roughly: remove 3 inline parses (about 12 lines in cite_origin, 5 in index, 3 in
hygiene), add about 10 in diff.py. Net about -10. Note cite_origin must keep reading the `+c,0` count as "removed after c", and
hygiene needs the start only (count ignored).
Risk: low. Only unreachable input changes; the well-formed cases agree today.

---

## 2. The memory-entry parser: `commands/memory_draft.py` vs `records/memory_entries.py`

### The copies
- Reader: `records/memory_entries.py` (427 lines). `Parser` class (116-405), `parse`, `rows`, `skipped`, `pending`, `kind` (section words),
  `idnorm`. Callers: `records/memory.py:rows/unread/replace`, `commands/memory.py` (`council memory`, index, select, check),
  `doctor_memory.py`, `session_start.py:157`, `memory_audit`.
- Editor: `commands/memory_draft.py` (438 lines) has its own line-level reading to find where an entry is, so it can
  insert and move text: `visible` (196-213: comment and fence skipping), `HEADING` (24), `entry_id` (216-230, the heading-entry
  test, a copy of `Parser.entry`'s id test), `cand_id` (233-241, a copy of `Parser.cand`), `headings` (244-249), `section_kind`
  (252-262, a copy of `memory_entries.kind` with fewer answers), `sections`, `section_end` (265-279), `find_entry` (320-355 area),
  `first_evidence` (299), `load_memory` (182-193, strict UTF-8, 1 MB cap).
  Callers: `commands/memory_write.py:_script` -> `commands/script.py` `memory` tool -> `memory_draft.main` (`council memory propose|accept|reject`),
  and `evals/run_memory.py:478-520` calls its functions directly.

### Where they disagree (snippets mem.py, mem2.py, mem3.py)
1. Entry identity agrees. 20,000 random files built from 30 line shapes (headings 1-7 hashes, ids with and without dash, `~~D-15~~`,
   fenced, commented, table rows, tab after `#`): the set of heading-entry ids `memory_draft.headings` found equals the set of ids in
   `memory_entries.parse(...).rows` in 20,000 of 20,000 files. So `entry_id`/`cand_id`/`visible` can be one function.
2. Section words disagree (`memory_draft.section_kind` vs `memory_entries.kind`): `## Pending proposals`: parser `off`, draft `other`;
   `## Draft`, `## Declined ideas`, `## Retired`: parser `off`, draft `other`; `## Decisions (proposed)`: parser `settled`, draft `other`;
   `## Proposals` both treat as proposed. Effect: `propose` into a file with only `## Pending proposals` makes a second `## Proposed`
   heading rather than filing under it. The helper itself writes `## Proposed — awaiting the user's yes/no`, so a hand-written
   section is the only way in.
3. A memory file that is not valid UTF-8 (hand-saved as Latin-1): `memory_entries.rows` reads it (`AP-1`, `café`);
   `memory_draft.load_memory` raises `UnicodeDecodeError`, and `script.captured` turns it into exit 2 with stderr
   `memory: 'utf-8' codec can't decode byte 0xe9 in position 29: invalid continuation byte`. That message names no next step (D19).
   Reachable by `council memory propose` / `accept` / `reject` on such a file. (Evals note "no proof yet on run_memory plus
   non-UTF-8 bytes", trim-commands report, row 19.)
4. `HEADING` allows 1-6 hashes; `Parser` treats `#######` as a heading of level 7 (then a deep candidate). A 7-hash line is
   named as unread by the parser and ignored by the draft. Hand-written only.
5. Entry ranges: the parser has no line spans; `find_entry` computes its own. They cannot be compared from outside and no
   difference was found; `evals/run_memory.py:485-520` is the existing "both readers must agree" fixture (shared id, `####` entry,
   table-row id, `#####` sub-heading) and passes today.
6. Bullet and numbered entries: the parser reads them (`- **F-1 — x.**`, `1. **F-1 — x.**`); `find_entry` refuses
   them ("must appear exactly once as a heading entry (found 0); move a hand-written proposal by hand"). This is deliberate,
   not a defect: the helper only files heading proposals.

### Can the helper produce the disagreeing input?
Items 2 and 4 and 6: hand edits only. Item 3: the helper does not write non-UTF-8, but a person saving a Latin-1 file is ordinary;
the reader accepts it, the writer fails.

### What a user would see change
If `load_memory` read bytes the way the parser does (C-locale text, as `bytewise.read`), `council memory propose|accept|reject`
on a non-UTF-8 file would work instead of exiting 2 with the decode message (the replacement is written back byte for byte, so
the other lines would keep their bytes). If `section_kind` became `memory_entries.kind`, the target sections for a hand-written
`## Pending proposals` change (it would be treated as the proposed section if the owner says so). Nothing changes for files the
helper wrote.

### Checks that pin today's behaviour
`evals/run_memory.py:265-290` (propose files under `## Proposed`, order of sections), `:444`, `:485-520` (the agreement fixture),
`evals/run_memory.py:478-481` (calls `one_line`), `tests/py/test_memory_entries.py` (parser rows), no scenario with non-UTF-8 memory.
`evals/ratchet.json` `parsers` lists `memory_draft.py` (value 8); a fold would lower it to 7 and need `run_ratchet.py --update`.

### Decisions / contracts
D32 ("`records/` the only code that parses a council file") and architecture §3 commands row ("Never: a run file's parser"):
memory_draft is a standing exception, counted in the ratchet. Architecture §6: memory entry ids (AP, EC, D, F) and the format
agents parse are frozen; the fold keeps them. D19 (refusals name the next step) applies to the decode error.

### Owner, size, risk
Owner: `records/memory_entries.py`. A good fold is partial: move `visible`, `entry_id`, `cand_id`, `section_kind` and the
heading walk into records (one function `headings(lines)` and one `section_kind` that reuses `kind`), leave `place`, `cited`,
`insert`, `move`, `one_line` (editing and text hygiene) in the command. Removes about 70 lines from memory_draft and adds about 20
to records. Better still: make `Parser` record each entry's start/end line and level so `find_entry` is `records` too
(about +25 in records, -45 in the command); that removes the second parser entirely and lets the `parsers` ratchet drop.
Risk: medium. The two jobs differ (read rows vs find line ranges for an edit); `find_entry`'s range rules are subtle (a deeper
`#####` heading with a separator ends an entry; one without stays inside). The 20,000-file agreement result and the existing
agreement fixture make the id and fence part safe; the range part needs a differential run over a corpus before and after.
If the owner wants it cheap: do only the id/cand/visible/section words fold now and leave ranges.

---

## 3. `config.roster` vs `config.roster_rows`

### The copies
- `records/config.py:187-203` `roster(home)` -> `[(seat, slug, lens)]`. Caller: `views/status_names.py:19` (`roster_names`, used by
  `seat_name` for `council status` text/widget/JSON: seats named "Lens (Seat)").
- `records/config.py:206-230` `roster_rows(home)` -> `[(slug, seat, reference)]`. Callers: `commands/doctor.py:99`
  (`council doctor` roster check), `commands/memory.py:105` `slugs()` (-> `memory_select.py:58`, `memory.py:115`: scope matching and
  orphan scope words for `council memory`/`select`).

### Where they disagree (snippet roster.py, 26 tables)
| Input | roster (status) | roster_rows (doctor, memory) |
|---|---|---|
| Table not under `## Roster` (e.g. `## Seats`) | read | not read |
| Heading `## roster` (lowercase) | read | not read (`startswith("## Roster")` is case-sensitive) |
| Heading `## Roster of seats` | read | read (prefix match) |
| Header has no Lens column | `[]` | rows with the reference |
| Header has no Slug column | `[]` | rows with slug `-` |
| Lens or slug cell empty | row dropped | row kept (slug `-`; or lens not needed) |
| `<Seat> | <slug> | <lens>` placeholder row | returned as a seat (`('<Seat>', '<slug>', '<lens>')`) | dropped |
| `**A B**` / `` `a` `` / `*l*` markup | seat `**A B**`, lens `*l*` (only backticks stripped) | `A B` (backticks and asterisks stripped) |
| A second table with the header again | both tables read | the second header becomes a data row `('Slug','Seat','Reference')` |
| Rows after a blank line between header and rule | none | rows |
| Indented table (`  | Seat |`) | read | not read (needs `startswith("|")`) |
| Non-UTF-8 byte (`Caf\xe9`) | `Caf\ufffd` (replacement char) | `Café` bytes kept |
| CRLF | both fine | both fine |
| Short row (fewer cells than the header) | dropped | kept, missing cells `-` |

### Can the helper produce these?
The config template (`references/templates/council.config.md:55-64`: `| Seat | Slug | Lens | Surface | Reference | Recast note |` under
`## Roster`, with a `<Seat>` placeholder row left in the template) is what `council-init` writes. So the placeholder row, the
Lens-bearing header and `## Roster` are the normal shape. Differences are visible on normal output in one place: the template's
placeholder row is returned by `roster` (so status can name seat slug `<slug>` "<lens> (<Seat>)", never used because no seat has that slug)
and dropped by `roster_rows`. Everything else is a hand edit (older configs "list seats instead of a table", the doctor hint).

### What a user would see change
Under one reader with the doctor/memory rule (`## Roster` only, header found by names, markup stripped, placeholder dropped):
`council status` seat names lose stray `**`/`*` marks when the config bolds a seat or lens; a seat whose Lens cell is empty
no longer gets a "(Seat)" name (or gets a name from the Seat cell alone if the owner wants that); a roster table in another
section stops naming seats; `council doctor` and `council memory` do not change. No exit code or refusal text changes.

### Pins
`tests/py/test_config.py:123-125` (roster), `:135-152` (rows, including BOM, placeholder, `Café`), `:27-35` (empty config readers).
`evals/run_cli.py:3128-3135` (status card with a roster and `s1..s8` skipped), `:3253` (doctor "repeats a slug"). No eval checks the
status name of a bolded seat.

### Decisions / contracts
Config keys and the Gates table columns are frozen (architecture §6); the Roster columns are read by name, not renamed. D32:
both in records already.

### Owner, size, risk
Owner: `records/config.py`. One function `roster_table(home)` returning a NamedTuple `Seat(seat, slug, lens, reference)` per row,
and `roster`/`roster_rows` become two list comprehensions at the call sites (or are deleted). Removes about 16 lines (one of
the two loops), adds about 6. Needs decisions: (a) is `## Roster` the only home (recommended: yes, it is what the template and
`config.roster_rows` already say); (b) row with empty Lens: keep, status falls back to the seat name; (c) bytewise or UTF-8 text
(recommend bytewise, as doctor and memory print it through `bytewise.shown`).
Risk: low to medium. Doctor and memory behaviour is the frozen side; status gains a small cosmetic change.

---

## 4. `config.memory_path` vs `memory.locate` / `config.memory_line`

### The copies
- `records/config.py:171-184` `memory_path(home)` -> a string. Only caller: `views/status.py:190` `oversized_memory`, which builds its own
  choices list (configured raw, configured first word, `home/conventions.md`, `root/conventions.md`) and reports the first
  existing file's size (`council status` memory-size attention, widget and `--json`).
- `records/config.py:153-168` `memory_line(home)` -> `(value, first word)` and `records/memory.py:48-68` `locate(home)` (+ `absolute`,
  27-45). Callers of `locate`: `commands/memory.py:84` (`council memory`, select, check, propose), `commands/doctor_memory.py:18`
  (`council doctor`), `commands/session_start.py:148` (SessionStart hook, `run open` size note via `memory.size_note`).
- Second size reader for the same file: `records/memory.py:71-78` `size_note` (for `run open`). It uses `locate`; status's
  `oversized_memory` uses memory_path. Same constant (`COUNCIL_MEMORY_SIZE_LIMIT`), two locators.

### Where they disagree (snippet memp.py, 31 configs; status picks = file that `oversized_memory` sized, "locate" = `memory.locate().path`)
| Case | memory_path / status | memory_line / locate | Sensible side |
|---|---|---|---|
| Linked config (`council.config.md` is a symlink) | `''` (text_of refuses links); status sizes nothing | follows the link: `docs/c.md` | locate: the helper follows it everywhere else for this file (`config.first()` reads with `read_bytes`) |
| A second `## Memory` heading | none found (both return the first `conventions:` they meet) | same | they agree; I could not make a second heading disagree |
| `## Memory2`, `## Memory_x` | not a Memory section (`\W|$` after Memory) | is a Memory section (`[^A-Za-z]|\Z`) | memory_path (Memory2 is another heading); but the bash rule it copies is the other one |
| `## memory` lowercase | Memory section | Memory section | agree |
| `- Conventions: x` (capital C) | read | not read (key is case-sensitive; `conventions.md` fallback used) | locate: config keys are lower-case and exact (architecture §6); memory_path is more forgiving but then `council memory` and status read different files |
| `* conventions:` | read | read | agree (both `[-*]`) |
| `+ conventions:`, no bullet | ignored | ignored | agree |
| `./docs/c.md` | `./docs/c.md`; status joins to `root/./docs/c.md` | `absolute()` drops `./` | locate (same file either way) |
| `/docs/c.md` (the repo-root style) | `/docs/c.md`; status sizes the literal `/docs/c.md`, finds none, ends with None | `absolute()` maps it to `root/docs/c.md` when that exists | locate: it is what `council memory` reads (`evals/run_cli.py:1773` pins "a configured /conventions.md is the repo's root one") |
| Configured file missing | falls to home/conventions.md then root | same (`alt`), plus a note | agree on the file; locate also says so |
| `C:/x` drive path | passed on | passed on | agree |
| BOM before the first line `## Memory` | found (text_of drops BOM) | not found (`file_lines` keeps BOM on line 1) | memory_path, but only when the heading is the very first line (never in a real config: `# Council config` is line 1) |
| Value `docs/c.md <!-- x -->` | keeps the comment | keeps the comment | agree (both wrong for a comment; same) |
| Path with a space | first word tried second | first word returned in tuple | agree |

### Can the helper produce these?
Linked config, capitals, `Memory2`, `/x` forms: hand edits. `council-init` writes `## Memory` + `- conventions: .council/conventions.md`.
`/x` is a documented hand form (evals/run_cli.py:1773).

### What a user would see change
If `views/status.py:oversized_memory` used `memory.locate(home).path`: `council status` would warn (or stop warning) about the memory
size for a config with a linked file, a `/x`-written path, or a `Memory2` heading, matching what `council memory` and `run open`
already measure. Typical projects see no change. Capital `Conventions:` flips from "sized" to "not sized" unless the owner
makes `memory_line` case-insensitive.

### Pins
`tests/py/test_config.py:116-121` (`memory_path`; line 119 pins the capital `Conventions:`), `:27-35`.
`evals/run_status.py:349-366` (memory size: 30 KB note, 20 KB none, "the card follows the configured memory path": `docs/project-memory.md is 66 KB`).
`evals/run_cli.py:422-425` (run open size note), `1766-1773`, `3273-3321`, `7176-7179` (locate scenarios). `tests/py/test_memory_entries.py:94-111`.

### Decisions / contracts
Config keys frozen (§6: `conventions` stays). `architecture.md` §8 records this as debt. D32 holds (both in records).

### Owner, size, risk
Owner: `records/memory.py` (`locate`). Delete `config.memory_path` (about 14 lines) and `status.oversized_memory`'s own choices
list (about 8 lines); add a 4-line `memory.size(home)` shared by `size_note` and status (they would share the one
`COUNCIL_MEMORY_SIZE_LIMIT`). Net about -20 lines. Decide on `Conventions:` case.
Risk: low. Status loads `records/memory` (which imports `memory_audit`, `config`, `bytewise`): check the import cost for
`views.status`, a separate process in the mod (D34 is about the command dispatcher).

---

## 5. `earlier.hits` round trip

### What it is
`records/earlier.py:50-64` `hits(home, paths)`:
1. `joined = "".join(p + "\n" for p in paths).rstrip("\n")` then `joined.split("\n")` back into a list (53-56), with `\r` removed.
   This is a join-then-split of an already-split list.
2. Each hit comes back as one tab-joined string (`path<TAB>where<TAB>text`, rows at 132/136).
3. The callers split it again: `earlier.line(row)` (140-143) does `row.split("\t")` and joins the first three with an em dash.
Callers: `commands/index.py:79-82` (`council index` "earlier work" list), `commands/prior.py:24-29` (`council prior`; its paths come from
argv words or from `earlier.indexed(run)`, which reads one line each).

### Proven differences (snippet earlier.py)
- A mentioned line that holds a tab loses its tail: the file line `see src/a.py<TAB>and then<TAB>more words` is stored as row
  `src/a.py<TAB>reviews/r.md:4<TAB>see src/a.py<TAB>and then<TAB>more words`; `line()` shows only the first three fields:
  `src/a.py — reviews/r.md:4 — see src/a.py`. The text is cut at its first tab. This is reachable by the helper (any deliverable line
  with a tab in a mention), so it is a real bug in the round trip, not an odd hand input.
- A path argument holding a newline is split into two paths (`['src/b','c.py']`): from `council prior $'a\nb'` only (argv); `indexed()`
  cannot return one because it reads single lines.
- A trailing or leading empty path is dropped/ignored (both give the same rows as without it). Empty list returns `[]`.
- A `\r` inside a path is removed.
- A path holding a tab never matches (row split) in the join path; the same with a structured result (it would match).

### What one structured hand-off changes
Return `list[Hit(path, where, text)]` (NamedTuple); `line(hit)` formats it. The tab bug disappears (the full 120-char clipped text
is shown); a newline in an argv path is one path (a path with a newline does not occur in a git path list). Callers never see
tab-joined text, so `earlier.line(row)` loses its split. Nothing else changes: same hits, same order, same clip.
The `.replace("\r","")` stays or goes (decide: `prior` words come from argv; a CR can come only from a Windows shell quirk).
`index.py:79` only slices `[:prior.SHOWN]`; `memory_select` uses `indexed` only.

### Pins
`tests/py/test_earlier_scope.py:88-94` (asserts rows are tab strings: it must change to the NamedTuple), `evals/run_cli.py:1081-1109`
(`prior` outputs, "mention(s) shown"), `:1846`, `:1096-1105` (./, res://, backslashes).

### Decisions / contracts
Output lines other code reads (§6): `prior: ...` lines are not in the frozen list; the printed format `path — where — text` is kept.

### Owner, size, risk
Owner stays `records/earlier.py`. Removes about 6 lines (the join/split, the row string building, `cells` in `line`), adds 4 (the
NamedTuple). Risk: low. The visible change is the tab bug fix.

---

## 6. `events._schema` vs `state.text`

### The copies
- `records/events.py:93-98` `_schema(run)`: `state.path(run).read_bytes().decode("utf-8","replace").lstrip(BOM)`, then
  `state.header(content, exact_keys=True).get("events-schema")`. No link check, no size cap, no containment check.
- `records/state.py:20-21` `text(run)` -> `paths.run_text` -> `paths.text_of(file, run, MAX_FILE=4 MB)`: refuses a link or junction,
  a file outside the run, one over 4 MB, and a non-UTF-8 failure only with strict mode.
- Callers of `_schema`: `events.append` (133), `ready` (160), `validate` (194): so every command that records an event and every
  hook that reaches `council run turn-end`, `seat`, `gate`, `check`, `run open|close`, `memory propose`.
- The same unguarded read pattern also appears at `commands/state.py:33` and `commands/run_resume.py:62` (`state.path(run)`).

### Proven difference (snippet schema.py)
| session-state.md | `_schema` | `state.header(state.text(run))` | `events.append` today |
|---|---|---|---|
| plain | `1` | `1` | writes |
| over 4 MB | `1` | `''` | writes |
| a symlink to a real file | `1` | `''` | writes |
| BOM + CRLF, or an invalid UTF-8 byte | `1` | `1` | writes |
| missing | `''` | `''` | `EventError: event file exists without an events-schema stamp` (if events.tsv exists) |

With `state.text`, an over-4 MB or linked state file reads as "no stamp": `append` then raises
`EventError("event file exists without an events-schema stamp: …")` when events.tsv exists, and returns `False` (silently writes no
event) when it does not (`events.py:134-137`). That is the trim-records builder's reason for stopping.

### Can the helper produce it?
A linked state file or one over 4 MB is a hand edit or a cloud-sync junction. The helper's own state writer
(`records/state_write.py`) writes regular files; no command grows it near 4 MB.

### What a user would see change
Only for a linked or over-4 MB `session-state.md`: events stop being written and the commands that append them print the
"without a stamp" refusal (that text does not name a next step; D19) instead of appending. Every other state file behaves as before.
This matches what status and every other reader already say about such a file (they treat it as empty).

### Pins
`tests/py/test_events.py:63, 101, 104` (stamp missing, schema 2), `evals/run_cli.py:723-729` (no stamp: "without an events-schema stamp"),
`:2657` (schema 9: "every event write now fails"), `:4674`. None covers a linked or huge state file.

### Decisions / contracts
Event schema `events-schema: 1` and the stream format are frozen (§6, event-stream.md). D33 (locks) unaffected.

### Owner, size, risk
Owner: `records/state.py` (`state.text`) is the one guarded read. Fold: `_schema` becomes
`state.header(state.text(run), exact_keys=True).get("events-schema","")` (about -4 lines, +0). If the owner prefers the old
behaviour for a link/large file, the other choice is to keep `_schema`'s read and make `state.text` the exception, but then the
two policies stay. Recommended: take `state.text`'s policy, and give the unstamped-because-linked case a refusal that says so
(D19). Risk: low in practice, medium in principle (it is on every event write, and a failure path changes from "writes" to
"refuses").

---

## 7. Views

### 7a. `proposals_in` (`views/snapshot.py:258-273`) vs `records/memory_entries.pending` (418-421)
- `proposals_in(home)`: reads only `home/conventions.md` (not the configured memory path), counts `### ` headings and `- PROPOSED`
  lines under a `## ` heading that starts `propos`. Caller: `snapshot.snapshot` (294) -> `status.py:338-340`
  ("N drafted lesson(s) wait").
- `memory_entries.pending(text, rows)`: counts `- PROPOSED` lines anywhere plus parsed entries (any level 2-4 heading entry or bullet
  entry) whose state is off and whose section name matches `[#* ]*propos`. Callers: `doctor_memory.py:99`, `session_start.py:157`.

Snippet props.py, same file text into both:

| Input | proposals_in | pending |
|---|---|---|
| `## Proposed` + `### Notes about it` (not an id) | 1 | 0 |
| fenced `### F-1: x` inside `## Proposed` | 1 | 0 |
| `<!-- ### F-1: x -->` | 1 | 0 |
| `#### F-1: x` under Proposed | 0 | 1 |
| bullet entry `- **F-1 — x.**` under Proposed | 0 | 1 |
| `- PROPOSED AP-9 x` under `## Accepted` | 0 | 1 |
| `**Retired:** yes` inside a Proposed entry | 1 | 0 |
| file not at `home/conventions.md` (configured path) | `None` | counts |
| `## Pending proposals` | 0 | 0 |

The helper writes `### F-n: title` under `## Proposed — awaiting…`, where both agree. The disagreements come from hand-written text,
code examples and a configured memory path (which the helper allows). The sensible side is `pending` (it is what `accept` and `reject`
can act on, and it uses the real parser), with `memory.locate` for the path. User-visible change: the status card's "drafted lessons
wait" count for projects that put memory elsewhere (it appears for the first time) and for notes/fences (it drops). Pins:
`evals/run_status.py` has no proposals scenario (grep `proposed` found none), `tests/py` none; the `memory.proposed` key in the
status JSON is a contract only by shape. Owner: `records/memory.py` gets `proposals(home) -> int|None` (locate, rows, `pending`);
snapshot loses 16 lines, memory gains about 8. Risk: low-medium (status would import `records/memory`).

### 7b. `converge_of` / `converge_rows` (`views/snapshot.py:160-221`; also `converge_result`, `converge_fixed` 140-157)
Only reader of the log's `## Converge` table; no second copy (grep: no `Converge` outside `views/` and `estimates.py`). Caller:
`views/status_closing.py:116` (closing card; `council status` for a finished build). The module that should own it is `records/`
(it reads a council deliverable file, `logs/<…>.md`; architecture §3 says `views/` never owns a run-file parser). Candidates:
`records/closing.py` ("what a close checks and says") or a new `records/converge.py`; I would use a new small module (about 70
lines: `rows(content)`, `result(cell)`, `fixed(cell)`, `of(run, deliverable)` using `paths.contained/linked/text_of`).
No behaviour change (a move). It also lets `evals/ratchet.json` `parsers` drop `views/snapshot.py` only if `snapshot` stops parsing
anything else (it still parses `claims.jsonl` rows and gate JSON, so probably not). Same shape elsewhere: markdown table readers
that each have their own cell split: `config.roster` (195), `config.roster_rows` (218), `snapshot.converge_rows` (197, escape-aware),
`memory_draft.verifier_reason` (89, escape-aware), `records/map_file.py:28-29`, `records/gate_table.py:153-185`,
`records/synthesis_counts.py:74-76`. A `cells.table_row(line)` (escape-aware) would serve all; the escape rule differs between them
(escape-aware vs plain `split("|")`), so folding them is a behaviour choice of its own.
Risk: low (a move).

### 7c. `read_claims` against `paths.text_of`
Gone. `views/snapshot.py:55` `jsonl(run, name)` is `cells.jsonl_rows(text_of(run/name, run))`: already on `paths.text_of`
with the run as root. Nothing to do. (`memory_draft` and `commands/evidence` read claims.jsonl through their own
`evidence.read_file`, a separate job, out of scope.)

### 7d. `filed_request` (`views/status_closing.py:22-47`) vs `records/request.py`
Callers: `status_closing.py:120` (closing card "request" line). Counterparts: `request.continued` (37-45, the state's `ask:` else ask.md's
`continues:`), `request.filed` (48-56), `request.in_your_words` (26-34), `request.words` (108-116, plan check/`council check`).
Snippet filed.py:

| Case | `filed_request` | `request` |
|---|---|---|
| state `ask:` set, normal file | `Fix the cache — Make the cache fast.` | filed path found, words include the `## Summary` text after (ends only at `## Later`/dated heading) |
| ask.md `continues:` only (no state `ask:`) | `No filed request recorded.` | finds `.council/asks/a.md` and reads it |
| file outside the asks folder (`out.md`) | refused (`No filed request recorded.`) | read (`request.words` is unguarded about the folder) |
| `## in your words` lowercase | read (`.lower()`) | not read (`words=''`) |
| first line of words blank | first non-blank line | all lines |
| file over 64 KB | cut (limit 65536) | 4 MB limit |

The status card wants a one-line title; plan checks want all the user's words. Different jobs on the same file; they share:
(a) which file (the state's `ask:` else ask.md `continues:`, made absolute from the project root), and (b) the guard that the file
is inside `.council/asks`. Rule to pick: use `request.filed(run)` for (a) and add the containment guard to `request` for (b); keep the
one-line extraction in views, or move it to `request.title_and_words(text)`. User-visible change: the closing card begins to show
the request for a run that has only `continues:` in ask.md; `request.words` stops reading an `ask:` that points outside the asks
folder (the helper only writes inside). Pins: `evals/run_status.py:263-292` (closing card: filed request, escaped, `ask: ../../outside.md` gives "No filed request recorded."; this one pins the guard),
`evals/run_cli.py:6465, 6488` (ask sections, `## In your words` with a dated line), `:3720-3726` (request filing). Owner: `records/request.py`. Net about -8 lines. Risk: low-medium. Folding the extraction itself is NOT a plain fold (different terminators).

### 7e. `latest_of` (`views/status.py:404-410`) vs `checks_of(snap)[-1]` (71-90)
Snippet latest.py: unique gate names, and the same name appearing twice at different times: identical (name, result, time) on all.
The only difference: two gate files whose `gate` field is the same AND the same `when` (a tie): `latest_of` picks the later
file (`a`), `checks_of[-1]` picks the later-inserted name (`b`). Hand-made; each gate is its own `gates/<name>.json`.
`latest_of` also formats name with `check_name` and adds `at`/`clock`. Fold: `latest_of` = `checks_of(snap)[-1]` then format, and the
caller (status.py:258 and 283) passes `checks` in so it is computed once. About -5 lines. Risk: low. Pins: `evals/run_status.py:238-239` (`latest_check` name `tests`). No decision touched.

---

## 8. `changed.options` vs `cli.takes_flags` / `cli.Args`

### The copies
- `commands/changed.py:48-63` `options(words)` -> `(globs, each)`: loops over `words`; `--each`, `--glob PATTERN`, `--glob=PATTERN`; anything else
  is `Refusal(USAGE)`. `expand()` (66-81) handles `{a,b}`.
- `commands/cli.py:86-90` (the `_flag` special-case `if word == "--glob" or word.startswith("--glob=") or word == "--each"`) makes
  `parse` push `--glob`, its value and `--each` into `args.words` for EVERY command (so `changed` can re-parse them) instead of reading
  them as flags. `cli.REPEATED = ("surface","expand")` already holds the shared way to take a repeated valued flag.
- Callers: `changed.main` (line 20) via `council changed [--glob P] [--each] [--base R] -- <cmd>`, and gates that run `council changed`
  inside `-- …` commands (evals/run_cli.py:5233).

### Proven differences (snippet changed.py; real `__main__` runs for the other commands)
| Input | today | with `--glob` in `VALUED`+`REPEATED`, `--each` in `SWITCHES` |
|---|---|---|
| `changed --glob` (no pattern) | `--glob needs a pattern` | `--glob needs a value` (cli.MISSING default) |
| `changed --glob=` (empty) | accepted: globs `['']`, then the "match no file" refusal | `--glob needs a value` |
| `changed --glob a b` | USAGE refusal | `changed doesn't take 'b'` (needs an `no_words` call) |
| `changed --each=1` | `unknown option '--each=1'` | `--each takes no value` |
| `changed --glob --each` | pattern `--each` | pattern `--each` (same: valued flag pops the next word) |
| `changed --glob -x` | pattern `-x` | pattern `-x` (same; evals/run_cli.py:4161 `--glob -*.sh` stays) |
| `version --each` | `version doesn't take '--each' — see: council help` | `version doesn't take --each — see: council help` |
| `help --glob x` | `help doesn't take '--glob x'` | `help doesn't take --glob — see: council help` |
| `--base main --glob x` | same | same |
All exit 2. Pattern order and expansion (`{a,b}`) are untouched: `args.lists["glob"]` keeps order, `expand` stays.

### Can the helper produce them?
Yes, by a user typing these; none from the helper itself.

### What a user would see change
Refusal wording for `changed --glob` with nothing after it, `--glob=`, and for every non-changed command given `--glob` or `--each`.
Exit codes unchanged. Then `--glob` and `--each` become ordinary flags: `args.lists["glob"]` and `args.value("each")`.

### Pins
`tests/py/test_gate_command.py:218-221` (`changed.options` directly: must change), `tests/py/test_cli.py:29-31` (`test_glob_words_pass_through`: pins that `parse` leaves `--glob`/`--each` in words; it would be reversed), `evals/run_cli.py:4127-4195` (changed scenarios),
`:5233`, `evals/run_structural.py:408, 442` (docs). 

### Decisions / contracts
Helper commands, their arguments and exit codes are frozen (architecture §6, D23): `--glob` and `--each` are kept, as is exit 2; only the
refusal sentence moves. D19 holds (the new sentences name the flag).

### Owner, size, risk
Owner: `commands/cli.py`. About -10 lines in changed (`options` becomes about 6 lines, `expand` stays) and -5 in `cli._flag`
(the `--glob`/`--each` branch). Risk: low.

---

## 9. Dates through `clock`; `json_esc`

### 9a. Dates
- `commands/ask.py:129` (`"%Y-%m-%d"` file name), `:140` (`## <date> — <mode>, run <name>` section), `:171`
  (`ask-saved=` with `"%Y-%m-%d %H:%M"`); `commands/memory_write.py:66` and `:130` (`--today`, `"%Y-%m-%d"`).
- `clock.py` has `now_min()` = `"%Y-%m-%d %H:%M"` (identical to `ask.py:171`), `now_sec()`, `now_utc()`. It has no date-only function.
- Same shape: `commands/run_open.py:85` (`"%Y-%m-%d-%H%M%S"` folder name), `records/audit_file.py:53` (`datetime.now(timezone.utc).strftime(...)`
  = `clock.now_utc()` exactly), `commands/hygiene.py:112` (`time.strftime("%Y")`).
- Callers: `council ask save` (ask.py), `council memory propose|accept|reject` (memory_write), `council run open`, `audit`.

No disagreement. Same format strings, same local time. The only effect of folding: `ask.py:129` and `:140` read the clock twice, so a
call that straddles midnight could name the file with one date and head the section with another; reading once fixes that
(theoretical). Add `clock.now_date()` (2 lines), use `clock.now_min()` at `ask.py:171`, `clock.now_date()` at the four date sites.
Net about +2 lines, -5 imports/uses (`import time` goes from both modules). Pins: `evals/run_cli.py:2619` (`ask-saved:` present),
`6465`, `4090-4103` (they compute the date themselves). Risk: low. It was skipped before because each module gained an import line
(shared builder note); under the new rule that cost is accepted.

### 9b. `gate_run.json_esc` (`commands/gate_run.py:54-56`)
`value.replace("\\","\\\\").replace('"','\\"')` then tab, CR and newline to a space. Used to hand-build the gate verdict JSON line
(`gate_run.py:123-125`, the TIMED OUT note at `:113`), the `invalid` tail (`commands/gate.py:233`) and the pattern `verdicts.green` compares
against (`commands/gate_set.py:134`, `records/verdicts.py:51-59`: `_first(path, COMMAND) != command`, a textual compare).
All other JSON in the package uses `json.dumps`: `correct.py:102`, `evidence.py:404`, `repair_trail.py:213` (all `ensure_ascii=False,
separators=(",",":")`), `patches.py:69` (`indent=1`, ASCII), `views/status.py:435`. `views/status_card.py:124` `esc` is HTML, not JSON.

Proven (snippet esc.py): `json_esc` leaves other control characters raw: form feed `\x0c`, ESC `\x1b`, NUL `\x00` give a verdict that
`json.loads` rejects ("Invalid control character"). `records/gates.py:56` reads each verdict with `cells.parse_json`, and a file that
does not parse is "left out" of the status's gate list. For tab, CR, LF the two differ by design: `json_esc` writes a space,
`json.dumps` writes `\t`, `\r`, `\n`. Quotes, backslash, UTF-8, U+2028, DEL and lone surrogates (from `surrogateescape`) agree with `json.dumps(ensure_ascii=False)`.
A gate command with such a control character comes from a hand-typed config (the `Gates` table), not from the helper.

Two ways to fold, one is a behaviour choice:
(1) Keep the "tab/CR/LF as spaces" rule (so the verdict stays one line and `verdicts.green`'s textual compare keeps matching old verdicts)
and also turn every other control character below 0x20 into a space, then make `json_esc` live in `records/gates.py` or `cells.py` next to the
reader. Safe: old verdict files still match.
(2) Use `json.dumps(value, ensure_ascii=False)[1:-1]` for the value: control characters become `\n`, `\u001b` etc. Then `green()` compares
the new escaped command against old files written with spaces and would mismatch for commands that held a tab/newline (they would re-run once).
Pins: `tests/py/test_gate_command.py:133` (the exact `json_esc` output), `evals/run_cli.py` gate scenarios (170 checks in the gates group),
`records/verdicts.py` readers. Decisions: JSON schemas frozen (§6 lists `council.run-status/1`, `council.seat-advice/1`; the gate verdict line
is a "run-folder file", frozen). Owner for (1): `records/gates.py` (it already owns the verdict read). Net about 0 lines moved plus 1 changed.
Risk: low for (1), medium for (2).

---

## Something else with the same shape (not in your list; not mapped in depth)
- `views/status.py:189-211` `oversized_memory` and `records/memory.py:71-78` `size_note`: two size checks of the memory file (see item 4).
- Markdown-table readers each with its own cell split: `config.roster`, `config.roster_rows`, `snapshot.converge_rows`, `memory_draft.verifier_reason`,
  `map_file.py:28`, `gate_table.py:153`, `synthesis_counts.py:74` (item 7b).
- Unguarded `session-state.md` reads beside `state.text`: `events.py:95`, `commands/state.py:33`, `commands/run_resume.py:62` (item 6).
- `commands/index.py:_records` and `hygiene._records` / `hygiene._file_lines`: both strip a trailing empty element from a split on `\n`
  (hygiene.py:66-69, index.py near 127); `bytewise.records` is the shared version (shared builder noted `index.records` differs on a bare CR).
- `request.words` reading a filed request path with no folder guard (`records/request.py:114`), where the status view guards it (7d).
- `records/memory.py:idlines` regex `_IDS` (18-19) is a third id recogniser beside `Parser.entry` and `memory_draft.entry_id`; it is meant to be looser
  (names ids the parser cannot read), so it is not a fold.
- `memory_draft.load_memory` and its 1 MB cap (`MAX_MEMORY`) against `paths.MAX_FILE` (4 MB) and `COUNCIL_MEMORY_SIZE_LIMIT` (25,600): three memory size numbers.

## Order I would build them in (all independent)
1 (hunk), 9a (dates), 8 (changed flags), 7e (latest), 5 (earlier hand-off), 3 (roster table), 4 (locate in status), 7a (proposals), 6 (events schema),
7b (converge move), 7d (request), 2 (memory parser: partial first), 9b (json_esc).
