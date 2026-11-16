# Reading rules map (line endings, repeated keys, numbers)

Tree read: `...\scratchpad\wt\cut-views` (HEAD 56e5560). All line numbers are from that tree. Every claim marked
"proven" was run; the snippets are in `...\maps-clean\scratch-a\` (i1.py, i1b.py, i2.py, i2b.py, i3.py, i3b.py,
i3c.py, i4.py, i6.py, i7.py, i8.py), run with `PYTHONIOENCODING=utf-8` and `src` on the path. The machine is Windows
(`os.name == "nt"`); for the POSIX branch I swapped the `os` name inside `bytewise` and `index` for a stub.

Facts that change how the proposed rules read, in one place:

- Nothing the helper writes ever has CRLF. Every writer in `src/council` writes bytes or `newline="\n"` (grep of
  `write_text`, `open(..., "w")`, `newline=`; `run_open.py:111` even turns a CRLF template into LF on Windows). CRLF,
  bare CR, FF, VT, NEL, U+2028 reach a council file only by a hand edit, an editor that saves CRLF, pasted text, or
  captured tool output (the gate output file `gates/<name>.txt`, written raw by `gate_exec.py:61`). Exceptions are
  named per item below.
- The evals never write a CRLF plan: `evals/run_cli.py:171-179` `write`/`append` force `newline="\n"`.
- `plan.keyed` lower-cases the VALUE of a row, not its key (`plan.py:62-69`, docstring "trimmed and lower-cased").
  The brief for item 5 says "keys"; see item 5.
- `bytewise.records` has an `os.name == "nt"` branch (`bytewise.py:44`): on Windows it turns every CRLF into LF
  before splitting; elsewhere the CR stays. So today the same file reads differently on Windows and Linux. The
  proposed "one rule, every OS" removes that split; that is the largest visible effect of items 1 and 2, and it shows
  on Linux/macOS, not on Windows.

---------------------------------------------------------------------------------------------------------------------

## Item 1. Plan-row trimming (`run-plan.tsv`)

### Copies (every reader of the plan's rows)

| Reader | file:line | Splits lines | CR | Cell trimming | Which row wins | Reached by |
|---|---|---|---|---|---|---|
| `plan.budget` | records/plan.py:52-59 | `text.split("\n")` | none cut from the line; the VALUE has every space, tab, CR removed anywhere (`re.sub(r"[ \t\r]", "", value)`) | matches `parts[:3] == ["budget","run",field]`, so a 3-cell CRLF row has `field\r` and never matches | last | `usage.budget_value` (usage.py:183), `usage.agent_cap` (:192) -> `council cap check` (cap.py:90), `council run close` (closing.py:55-59), `council status` (status_usage.py:67-68), `council cap`/agent hook gate |
| `stages.required` | records/stages.py:42-57 | `text.split("\n")` | one trailing CR cut | value only: `.strip(" ")` (spaces, not tabs); kind/id/field untrimmed | last size (`size[-1:]`) | `stages.skipped` -> `council state phase=` (state.py:70), `closing` (closing.py:49) |
| `plan.selected` | plan.py:26-28 | `cells.lines_of` | ALL trailing CRs cut (`rstrip("\r")`, cells.py:19-23) | none; exact compare of the first four cells | any | agent_gate.py:242 (Agent-start hook), seat.py:155 (`council seat X running`) |
| `seat_rows.tool_budget` / `is_verifier` | records/seat_rows.py:22-53 | `cells.lines_of` | all trailing CRs cut | none; budget cell must be `[0-9]+` exactly | last (budget), any (verifier) | collect.py:63,139, seat_notes.py:12 (`council collect`, `council seat`) |
| `plan.summary` | plan.py:31-49 | `lines_of` | all trailing CRs cut | `cells.clean` on each of five cells (controls to space, runs of spaces to one, `.strip()` of ALL Unicode whitespace); needs >= 5 cells | last | snapshot.py:285 (`council status`, status card) |
| `plan.rows` (-> `cells.tsv_rows`) | plan.py:21-23, cells.py:87-94 | `lines_of` | all trailing CRs cut | none; short rows padded with "" | list | seat.py:131, closing.py:108, audit_checks.py:62-76 (which does its own `.strip()`) |
| `plan.keyed` | plan.py:62-69 | `lines_of` | all trailing CRs cut | value `.strip().lower()` (Unicode strip and Unicode lower); needs >= 4 cells | last | evidence.py:79 (`council evidence build/check`) |
| `plan_check.Check.line` | commands/plan_check.py:109-127 | `lines_of` | all trailing CRs cut | each of 5 cells trimmed of `[ \t]`; `Value.padded` records whether trimming took anything off (then compares as text) | duplicate rows refused | `council run plan check` (plan.py:45) |

So there are seven different trimming behaviours for one file. The brief's two named copies are right in kind, but the
claim "`plan.budget` keeps the CR of a 3-cell CRLF row" needs a correction: it is the field cell that keeps the CR, so
the whole row silently does not match.

### Proof (i1.py, i1b.py)

```
H = "kind\tid\tfield\tvalue\treason\n"
budget(estimated-tokens), rows written as shown, run through plan.budget:
  "budget\trun\testimated-tokens\r\n"                 -> ''      (3 cells, CRLF: no match)
  "budget\trun\testimated-tokens\t1000\r\n"           -> '1000'  (4 cells, CRLF: CR removed from value)
  "budget\trun\testimated-tokens\t1000\twhy\r\n"      -> '1000'
  value " 10 00 "                                       -> '1000'  (inner blank removed: 10 00 reads as 1000)
  value "1\t0"  (a tab inside)                          -> '1'
  value "1000\rx"                                       -> '1000x'
  "budget\trun\tagent-cap\t5\tr\n" then "budget\trun\tagent-cap\n"      -> ''   (the later 3-cell LF row blanks it)
  "budget\trun\tagent-cap\t5\tr\r\n" then "budget\trun\tagent-cap\r\n"  -> '5'   (the later 3-cell CRLF row is ignored)
stages.required (4-cell rows):
  CRLF 4-cell, size full, one selected worker           -> 10 stages (same as LF)
  "seat\ta\trole\t\tworker" (a tab before the value)    -> role read as '' -> 6 stages (keyed gives '' too; plan.selected would still say True)
  value " selected" / " worker " (space padded)         -> stages: 10 stages (trims spaces); plan.selected -> False; tool_budget(" 12") -> ''
  bare CR inside a line "...worker\rseat\ta\t..."      -> stages 6 (the row is one line to it); keyed: value 'worker\rseat' (also one line)
plan.summary on a padded " selected " -> 'selected' (cleans);  plan.selected same row -> False
```

### Can the helper produce the odd input?

No. `run_open.py:98-114` writes the plan from `references/templates/run-plan.tsv` with CRLF turned into LF
on Windows. After that only the Chair (Write/Edit tool, normally LF) or a hand edit changes it. A 3- or 4-cell row
is also invalid for `council run plan check` ("expected exactly 5 tab-separated columns", plan_check.py:118-120), so
the readers that tolerate it only matter for a plan that skipped the check or was edited after it.

### What a user would see under the proposed rule

- A plan saved with CRLF (an editor): on Windows nothing changes for 5-cell rows (every reader already drops the CR).
  On Linux/macOS, `stages.required`, `budget` and the rest already drop it too; the only readers that today differ
  are the 3/4-cell CRLF rows. Visible change: `council cap check` / status card / run close figure for a plan that
  has a 3-cell CRLF `budget` row after a valued one (the earlier value stops being blanked/kept inconsistently),
  and `1 0` in a budget value would stop reading as `10` if the rule stops removing inner blanks. Both are
  hand-edit cases only.
- "One trailing CR" differs from the code: `lines_of` cuts ALL trailing CRs and `test_plan_check.py:57` pins a plan
  with `\r\r\n` line ends as valid. The proposed "one CR" would turn that plan's last cell into `why\r`. If one rule
  is wanted, keep `lines_of`'s "all trailing CRs" (what the tests pin) or change that test on purpose.
- Trimming: the readers want different things on purpose. `plan_check` needs the raw cell (it compares padded values
  as text, `Value.padded`). So a shared reader should hand out RAW cells (CR cut), and each reader trims with one
  helper (`bytewise.trim`: space and tab, both ends). That removes `plan.budget`'s inner-blank removal,
  `stages`' space-only strip, `keyed`'s Unicode strip. It would change: `stages.required` for a tab-padded value
  (now trimmed: more correct), `plan.selected`/`tool_budget`/`is_verifier` for a space-padded value (now match),
  `plan.budget` for `1 0` (now `1 0`, not a number, so unset) and `keyed` for U+00A0 or U+2028 around a value.

### Pins today

- tests/py/test_plan.py:15 (`budget ... agent-cap 6\r\n` after ` 8 `), :40-43, :51-54 (U+2028 in a reason is one row)
- tests/py/test_spine.py:97 (stages: ` worker ` and `selected\r`, size `squad`)
- tests/py/test_plan_check.py:56-57 (`\r\n` and `\r\r\n` plans valid), :134-135 (padded cells shown as written)
- tests/py/test_cells.py:13 (`lines_of`)
- evals/run_cli.py:679, 1369, 1503, 1580 (budget rows, LF only; :1580 is the 23-digit cap, see item 6). No eval
  has a CRLF plan. evals/run_status.py:115, 450-503, 835 (plan edits, LF).

### Decisions / contracts touched

None by id. D23 freezes "run-folder files and TSV columns", not how a row is read. D25: each changed reader needs a
scenario that runs the helper (today only unit tests cover CRLF plans; add one `run_cli` scenario with a CRLF
plan on `cap check` and `state phase=`).

### Size and risk

Remove about 12 lines (the `split`/trim code in `budget`, `required`, `selected`, `tool_budget`, `is_verifier`,
`keyed`, one `_lines` use), add about 12 (one `plan.cells(line)` and one trim). Net about 0. Risk: medium. Seven readers
move to one rule and `budget` feeds `cap check`, which can stop an agent start; the cases that change are all hand
edits, but the all-trailing-CR test must be decided first.

### Better rule?

Yes, a small correction: (a) "CR" rule = what `lines_of` does (all trailing CRs) unless the owner wants the test
changed; (b) one `plan.cells(line)` that returns raw cells and one trim function; (c) keep "last row wins" only where
plan check cannot have refused a duplicate (it refuses them, plan_check.py:132-133, so "first" or "last" cannot
differ on a checked plan). This is a real behaviour difference only on unchecked or hand-edited plans.

---------------------------------------------------------------------------------------------------------------------

## Item 2. `index.records` against `bytewise.records` / `file_lines` / `lines`

### Copies

| Copy | file:line | What it does | Reached by |
|---|---|---|---|
| `index.records(data: bytes)` | commands/index.py:25-29 | decode UTF-8 (surrogateescape), split "\n", drop one trailing empty piece, then on `os.name == "nt"` only, cut ONE trailing CR from each line | `council index` (index.py:100, 105, 189, 193, 198): `git diff --name-status`, `git ls-files --others`, the first 400 lines of an untracked file, `git diff --numstat`, `git diff -U0` |
| `bytewise.records(text, fold=True)` | records/bytewise.py:39-48 | on nt: `text.replace("\r\n","\n")` over the whole text, then split "\n", drop trailing empty; elsewhere the CR stays. `fold=False` keeps CR everywhere | 19 default callers (index_symbols.py:98, memory_tree.py:29,68,81,131, state.py:33, config.py:212, events.py:213, ledger.py:106,112, memory.py:93, memory_audit.py:196, memory_entries.py:420, runs.py:67,91, seats.py:59, state_write.py:156, quotes.py:79,109, check.py:56) and ~30 `fold=False` callers (gate output, seat files, verdicts, config tables, seats.tsv in seat_write/seat_notes) |
| `bytewise.lines(text)` | bytewise.py:51-56 | `records(text)` then cut one trailing CR on every OS, BOM off line 1 | earlier.py:76, memory_entries.py:401 |
| `bytewise.file_lines(path, fold)` | bytewise.py:59-65 | `records` of a file read as UTF-8 | see above |
| `cells.lines_of` | cells.py:19-23 | split "\n", ALL trailing CRs cut, on every OS | plan, state header, events, jsonl, tsv |

### Proof (i2.py, `index.records` vs `bytewise.records(fold)` vs `fold=False` vs `lines`)

```
input             os     index.records   bytewise.records   fold=False    lines
'a\r\nb\r\n'      nt     ['a','b']       ['a','b']          ['a\r','b\r']  ['a','b']
'a\r\nb\r\n'      posix  ['a\r','b\r']   ['a\r','b\r']      ['a\r','b\r']  ['a','b']
'a\r\nb\r'        nt     ['a','b']       ['a','b\r']        ['a\r','b\r']  ['a','b']     <- index != bytewise
'a\r'             nt     ['a']           ['a\r']            ['a\r']        ['a']         <- index != bytewise
'\r'              nt     ['']            ['\r']             ['\r']         ['']          <- index != bytewise
'a\r\nb\r\r'      nt     ['a','b\r']     ['a','b\r\r']      ...            ['a','b\r']   <- index != bytewise
'a\r\r\nb'        nt     ['a\r','b']     ['a\r','b']        ['a\r\r','b']  ['a','b']
every other input I tried (incl. '', '\n', 'a\rb\n', 'a\n\r\n'): index == bytewise on both OS
```

The two copies agree except for ONE shape: a last line with no newline that ends in CR, on Windows only
(index cuts that CR; `bytewise.records` folds only a CR that is followed by LF). Everywhere else, including POSIX,
they are the same function. `index.records` is a plain fold with one corner case; the corner case is the only
behaviour difference.

The real mismatch in this item is a different one: the same helper reads `\r\n` three ways: `records` keeps the CR on
POSIX and drops it on Windows; `lines`/`lines_of` drop it on both; `fold=False` keeps it on both (seat_files
`items` cleans it later, i2b.py: a CRLF seat file gives clean titles).

### Can the helper produce the odd input?

`index.records` reads git's output and the bytes of an untracked source file (index.py:189). Git output always ends in
LF; the unterminated last line with a CR is only possible for an untracked file whose last line is `...\r` with no
newline (a source file saved by a Windows editor). The other readers read files the helper wrote (LF) or that people
edit. For the CRLF part: a CRLF source file is common on Windows (the eval at run_cli.py:2233-2245 builds one).

### What a user would see under the proposed rule (every OS: LF ends the line, drop a trailing CR)

- Windows: only the corner case above (last unterminated line `...\r`: the CR in `index.md`'s `+line` preview
  goes in both copies). Nothing else changes.
- Linux/macOS: every `bytewise.records(fold=True)` caller starts dropping the CR of a CRLF line. Concretely:
  `council index` writes `+line` previews and hunk lines without a trailing `\r` for a CRLF file (today it keeps it);
  `seats.tsv` / `events.tsv` / `state` / `ledger` / `config` rows with CRLF stop carrying a CR in their last cell
  (test_seats.py:83-85 notes today `skipped\r` is "no skipped state" on Linux); `council status` etc. read a CRLF state
  the way Windows does. It is a correction toward the Windows behaviour, not a regression.
- `fold=False` callers (~30) would drop the CR too: gate output lines, verdict lines, seat-file lines, config gate
  table. Most already have `[ \t\r]*` in their patterns. Printed gate output (`gate_failed.indent`,
  `gate_output.tail`) would lose a trailing CR on every OS (test_gate_command.py:107-108 pins "kept on POSIX").
  Only one reading of fold=False needs thought: `gate_output` lines are command output, where a CR before LF is
  Windows noise and a bare CR is a progress bar (not touched by this rule).

### Pins today

- tests/py/test_earlier_scope.py:30 (records CRLF, nt vs posix), :35-36 (`fold=False`), :47-50 (`file_lines`)
- tests/py/test_gate_command.py:107-108 (indent keeps CR on POSIX), :297
- tests/py/test_reports.py:53 (ledger CRLF), tests/py/test_seats.py:46-49, 83-85
- tests/py/test_listing.py:42 (`listed_fields` CRLF)
- No test names `index.records`. evals/run_cli.py:2233-2245 runs `council index` over a CRLF file (indirect; the
  assertion is about cite origin).

### Decisions

None by id (no decision names line endings). `evals/ratchet.json` lowers (one function fewer).

### Size and risk

Folding only `index.records` onto `bytewise.records`: remove 6 lines (and `import os` if unused: it is used
at index.py:41), add 0. Changing the rule for everyone (drop the `nt` branch and `fold`): remove about 8 lines in
`bytewise.py`, about 30 `fold=False` arguments, and 5 test lines; add 0. Risk: low for the plain fold; medium for
the rule change (many callers, but each one only gains a stripped CR; Linux/macOS output moves).

### Better rule?

The fold is safe. For the rule, say it as: records = split on "\n"; a trailing CR of a line that ended in LF
is dropped; an unterminated last line keeps whatever it has (what `bytewise.records` already does on Windows).
That equals today's Windows behaviour exactly, so Windows users see nothing and `index.records`' corner case goes.
Do not use `lines_of`'s "all trailing CRs" for bytes of source files.

---------------------------------------------------------------------------------------------------------------------

## Item 3. `splitlines()` on council-file text

`str.splitlines()` splits on \n, \r, \r\n, \x0b, \x0c, \x1c-\x1e, \x85, \u2028, \u2029. Every sibling reader named
below splits on "\n" only (`lines_of`, `bytewise.records`, `str.split("\n")`). Sites in `src/council`
(`grep splitlines`): 17.

### Sites, owners and the sibling that disagrees

| # | file:line | Text | Sibling reader of the same file | Reached by | Proven |
|---|---|---|---|---|---|
| 1 | records/config.py:175 `memory_path` | council.config.md | `config.memory_line` (config.py:150-165, `file_lines(fold=False)`, `\n` only), `roster_rows`, `field` | `council status` (views/status.py:190) | yes |
| 2 | commands/repair_trail.py:109 `classify` | gate output `gates/<g>.txt` | `gate_failed` hit numbering (gate_failed.py:47, `records(fold=False)`), `gate_output.*` | `council repair record/check` (repair_trail.py:189, 296) | yes |
| 3 | views/status_closing.py:37 `filed_request` | `.council/asks/*.md` | `request.in_your_words` (request.py:26-34, `split("\n")`), `request.ask_words` (bytes, `\n`) | `council status` closing card | yes |
| 4 | views/snapshot.py:266 `proposals_in` | conventions.md | `memory_entries.pending` (memory_entries.py:420, `bytewise.records`) | `council status` | yes |
| 5 | commands/evidence.py:89, 110, 249, 435 | synthesis.md, verify-*.md, claims.jsonl (via `read_file`, which first runs `paths.universal`, evidence.py:45) | `seat_files.verify_problems` / `shape` (`file_lines(fold=False)`), `cite_check`, closing.py | `council evidence build/check`, `council memory` draft (memory_draft.py:100) | yes |
| 6 | commands/memory_draft.py:86 `verifier_reason` | a verify file | same as 5 (it counts lines the way evidence does) | `council memory` draft | by reading |
| 7 | commands/audit_checks.py:291 | claims.jsonl | `snapshot.jsonl` -> `cells.jsonl_rows` (`lines_of`, snapshot.py:53-54) | `council audit` | by reading |
| 8 | commands/repair_trail.py:126 `load_ledger`, :310 `allowances` | repairs.jsonl, repair-allowances.tsv | `snapshot.repairs_of` (`jsonl_rows`) | `council repair`, memory_draft.py:149 | by reading |
| 9 | commands/audit.py:232, :357 | a Claude transcript's tool-result text (not a council file) | none | `council audit` | n/a: not council-file text |
| 10 | commands/doctor.py:214 | the captured output of an in-process command | none | `council doctor` | n/a: own output |

### Proof (i3.py, i3b.py, i3c.py)

```
1. config "## Memory\r- conventions: x.md\n"  (also FF, VT, FS, NEL, U+2028 in place of \r):
     memory_path -> 'x.md'     memory_line -> None      (one line for memory_line: it is the heading, so no conventions line)
2. gate output "downloading 10%\rdownloading 90%\rModuleNotFoundError: x\nbye\n":
     classify signal -> 'output:3: ModuleNotFoundError: x'      gate_failed's own numbering of that line -> 1
   FF case "a\x0cb\nModuleNotFoundError: x\n":  classify 'output:3'   gate_failed 2
   CRLF output: both agree ('output:2')
3. ask file "# Ask - x\n## In your words\nfirst\x0csecond part\n":
     status_closing -> 'Ask - x - first'      request.in_your_words -> ['first\x0csecond part', '']   (also bare CR)
4. conventions.md "## Proposed\r- PROPOSED a\r- PROPOSED b\n":  proposals_in -> 2     memory_entries.pending -> 0
   "## Proposed\n- PROPOSED a\x0c- PROPOSED b\n":              proposals_in -> 2     pending -> 1
5. 'a\rb\x0cc\nd\n' through evidence.read_file + splitlines -> ['a','b','c','d']; bytewise.file_lines -> ['a\rb\x0cc','d']
   verify row "| 1 | x | CONFIRMED | a.py:3\x0cmore |": evidence's cells keep 'a.py:3' and lose 'more'; siblings keep one row
```

### Can the helper produce the odd input?

- Gate output (row 2): YES, with no hand edit. `gate_exec.py:61` writes the child's raw bytes; pip, npm, pytest -v
  and many Windows tools print progress with bare CR, and some print FF. This is the one that shows in real runs:
  the `output:N:` line number in `repairs.jsonl` and in `council repair` output disagrees with the number
  `council gate` prints for the same line.
- Ask file (row 3): `council ask save` writes the user's words as pasted; U+2028 and U+0085 arrive by pasting from
  web pages and documents. Display only (the card's summary line).
- Config / conventions / synthesis / verify files (rows 1, 4, 5): hand-edited or agent-written text; FF/VT/NEL/U+2028
  only by paste. Claims.jsonl is `json.dumps(ensure_ascii=False)` (evidence.py:404), so U+2028/U+0085 would stay raw
  there, but they cannot get in: `synthesis()` and the verifier-row parser split on the same characters first
  (by reading).
- Events/other `\n`-only readers are consistent: test_events.py:53-56 pins a U+2028/U+0085 detail as one row.

### What a user would see under the proposed rule (only LF ends a line)

- `council status` memory-size line / "memory file" row: a config with `\r`, FF, NEL or U+2028 next to the Memory
  heading stops finding the conventions path (memory_path = memory_line = None). Hand-edit only.
- `council repair` output and `repairs.jsonl` `signal`: `output:3:` becomes `output:1:` for the CR progress-bar
  case, and the matched line is the whole CR-joined line (the text after `.strip()[:200]` is longer/different).
  A written file differs, on gate output that holds bare CRs.
- `council status` closing card: the request summary takes the whole first words line (including text after a
  U+2028) instead of the part before it.
- `council status` proposals count: 2 -> 0 for the bare-CR conventions file (it now agrees with `memory_entries`).
- `council evidence build/check`: with bare-CR or FF in a synthesis/verify file the claim list and the `file:line`
  numbers (evidence.py:110, 249) stop counting each CR/FF as a line break; `claims.jsonl` content and stale-check
  results can change for such files (hand-edited / pasted only). `evidence.read_file` would stop calling
  `paths.universal` (CR and CRLF to LF); that removes `paths.universal` (paths.py:146-148) and its test
  (test_paths.py:66). A CRLF verify file still reads the same (one trailing CR dropped).

### Pins today

- tests/py/test_cells.py:13 (`lines_of` splits on newline only; names this exact rule)
- tests/py/test_plan.py:51-54 (a U+2028 reason is one row)
- tests/py/test_events.py:53-56
- tests/py/test_paths.py:66 (`universal`)
- evals/run_cli.py: evidence scenarios (grep `evidence build`) write LF files; none holds FF/CR. No scenario pins the
  gate-output numbering: add one (gate whose output has a bare CR, then `council repair record`).

### Decisions

None by id. The rule agrees with `cells.lines_of`'s docstring ("str.splitlines() would also split on form feeds and
Unicode breaks inside a cell, and invent rows") and with `records/state.header` (lines_of).

### Size and risk

Replace 14 `splitlines()` with `cells.lines_of(...)` (or `bytewise.records`) (about 0 net lines); delete
`paths.universal` (3 lines) and its test (1-2 lines); `evidence.read_file` loses one call. Risk: low for rows 1, 3, 4,
7, 8, 9, 10; medium for row 2 (a written file, `repairs.jsonl`, and `repair check` re-derives the signal and refuses
if it differs from the recorded one, repair_trail.py:296-299: an old `repairs.jsonl` written under splitlines would
then fail the re-check for a gate output with bare CR) and row 5 (evidence is a 4-site reader with `file:line`
numbers in written output).

### Better rule?

Keep "only LF ends a line", but note that row 2 has the one compatibility trap: runs recorded before the change
carry the old `output:N` numbers. If owner is fine with `council repair check` refusing an old trail with a
CR-bearing gate output, go on; otherwise leave row 2 for last.

---------------------------------------------------------------------------------------------------------------------

## Item 4. First or last of a repeated key

### Copies

| Reader | file:line | Rule | Keys read | Reached by |
|---|---|---|---|---|
| `events.details` | records/events.py:66-68 | `dict(...)`: LAST wins; key not trimmed; any value accepted | audit_checks.py:123 (`skipped`, `reason`), :215 (`seconds`), :352 (`agent_runs`); repair_trail.py:102 (`exit`), :274 | `council audit`, `council repair` |
| `chair_usage.main` | commands/chair_usage.py:94 | regex `(?:^|;)was=([^;]*)`: FIRST wins; an empty first value means "partial" | `was` | `council run close` (close_report.py:41), `script chair_usage` |
| `snapshot.events_of` | views/snapshot.py:229-230 | regex `(?:^|;)calls=([0-9]+)(?:;|$)` / `basis=([a-z]+)(?:;|$)`: FIRST that is well-formed | `calls`, `basis` | `council status` (card, widget) |
| `status.event_news` | views/status.py:141 | regex `until=[0-9]{1,9}`: FIRST well-formed | `until` | status card |
| `state.header` / `runs.listed_fields` | state.py:24-37, runs.py:61-76 | FIRST wins | session-state.md keys | everything |
| `agent_gate.read_call` | commands/agent_gate.py:43-53 | LAST wins (pinned by test_cap.py:104) | hook words `seat=`, `type=`... | the Agent-start hook |

So in this tree `events.details` is NOT used for `was=`, `calls=` or `basis=`; those three have one reader each, all
"first" (the brief's "other reader takes the last" is `events.details`, which nobody calls for these keys).
Calling `was`/`calls`/`basis` through `events.details` would be a change, not a fold.

### Proof (i4.py)

```
'from=paused;was=a;was=b'                 details -> {'from':'paused','was':'b'}   chair_usage regex first -> 'a'
'from=paused;was=;was=b'                  details -> was 'b'                       chair_usage first -> '' (partial=True)
'calls=3;basis=partial;calls=9;basis=complete'   details -> calls 9, basis complete    snapshot regex -> calls 3, basis partial
'calls=12x;basis=complete'                details -> calls '12x'                    snapshot regex -> calls None, basis complete
state.header('mode: a\nmode: b\n') -> {'mode': 'a'}
```

### Can the helper produce a repeated key?

Where it writes them, the keys are fixed and unique: `run_resume.py:36` `from=%s;was=%s`; `close_report.py:47`
`calls=%s;basis=%s` (digits and a validated word); `gate_exec`/`run_close` write `exit=;seconds=;empty=;timed_out=`
and `agent_runs=;reported=;tokens=;basis=`. The one place user text sits after a helper key is `state.py:80`:
`;skipped=<list>;reason=<the user's skip words>`. A reason containing `;skipped=` or `;reason=` is a repeat, and
`events.details` (last wins) would let the reason's text replace the helper's own `skipped` list in
`council audit` ("skipped on purpose: ..."). "First wins" is the safer rule there: the helper's keys come first.
`was=` can repeat only if the session id holds `;was=` (the id comes from `CLAUDE_CODE_SESSION_ID`, not cleaned of `;`).

### What a user would see under the proposed rule

Only `council audit`'s "skipped on purpose" note for a skip reason that contains `;skipped=`, and
`council repair`'s `exit=` check (repair_trail.py:102) for a detail with a repeated `exit`. Nothing else (the `was`,
`calls`, `basis`, `until` readers are already "first"). Output, exit codes and written files: no change for any
event the helper writes.

### Pins today

- tests/py/test_events.py:33 (`details` on unique keys)
- tests/py/test_cap.py:104-107 pins the OTHER shape (`agent_gate.read_call`: a later `seat=` wins). That is a hook
  parse; the proposed rule must not touch it (see "Same shape" below).
- evals/run_cli.py:4744-4757, 4763-4771 (`was=`, `calls=`, `basis=` on unique keys)

### Decisions

None. Architecture §6 freezes "event types, subjects and detail keys" (names), not the repeat rule.

### Size and risk

`events.details` becomes a 3-line loop with `setdefault` (+2 lines). Moving the three regexes onto it would also
need a digits-only check for `calls`/`basis` (the regexes insist on a well-formed value; `details` does not): +3
lines per site, about -6 lines of regex. Risk: low.

### Better rule?

Agree: first wins. Say separately whether `calls`/`basis`/`until` should keep their well-formed-value check; if
`snapshot` reads them through `details`, `calls=12x` would show as 12x (today: no calls figure). Keep the format
check at the reader.

---------------------------------------------------------------------------------------------------------------------

## Item 5. `plan.keyed` lower-casing

### What it really does

`plan.keyed` (plan.py:62-69): key = `(kind, id, field)` EXACT as written; value = `.strip().lower()` (Python's
Unicode strip and Unicode lower). The keys are not lower-cased. Its one caller is `evidence.run_fields`
(evidence.py:77-82): `plan.get(("verification","run","level")) == "self"` or `plan.get(("run","run","size")) == "solo"`
decides `self_check`, which switches off one rule in `assess` (evidence.py:355-369).

### The readers that compare the same values case-sensitively

| Reader | file:line | Compare |
|---|---|---|
| `stages.required` | stages.py:50-53 | `== "solo"`, `== ("role","worker")`, `("disposition","selected")` exact |
| `closing._no_verdicts` | closing.py:108-111 | `r["value"]` vs `"self"` exact |
| `audit_checks.Run` | audit_checks.py:62-76, :95 | `.strip()` then `== "selected"/"worker"/"solo"` exact |
| `plan.selected`, `seat_rows.is_verifier` | plan.py:26, seat_rows.py:50 | exact |
| `plan_check` | plan_check.py:168, 180 | `v not in ("self","independent","adversarial")`, `("solo","squad","full")`: refuses any other case |

### Proof (i1b.py, i1.py)

```
plan "run run size Solo / seat a role worker / seat a disposition selected":
   plan.keyed(...)[("run","run","size")] -> 'solo'   (evidence would treat the run as solo/self-checked)
   stages.required(run)                  -> 10 stages (not solo: exact compare)
keyed keys keep case: ('seat','Hunt','role') stays 'Hunt' (ids are NOT folded)
test_plan.py pins: value 'SELF' -> 'self'
```

### Can the helper produce it?

No, and the plan check refuses it: `council run plan check` accepts only lower-case enum values for `size` and
`verification level` (plan_check.py:168, 180), and `id` may be mixed case (`[A-Za-z0-9._-]+`, plan_check.py:122).
So only a plan that skipped the check (legacy run, hand edit after the check) differs.

### What a user would see under the proposed rule

If the rule is "ASCII lower case everywhere" applied to enum VALUES (size, level, role, disposition): for a hand-edited
`Solo` or `SELF` plan, `council state phase=` (stages) and `council evidence check` would agree; today they disagree.
If the rule is applied to KEYS (ids, which are seat slugs), seat slugs `Hunt` and `hunt` would collide with each other
and with seat file names (case-sensitive on Linux, insensitive on Windows): do not. Output/exit code change: none
for any checked plan.

### Pins today

- tests/py/test_plan.py:44-48 (`SELF` -> `self`, `6`)
- evals/run_cli.py: none for case. No scenario for a mixed-case plan.

### Decisions

None.

### Size and risk

Option A (ASCII-lower the enum values in every reader through one `plan.value(cell)`): +3 lines, -0, touches
stages, closing, audit_checks, selected, seat_rows. Option B (drop `.lower()` from `keyed`, since the checker only
accepts lower case): -1 line and one test line (`SELF` case). Risk: low either way.

### Better rule?

The proposed rule is wrong as worded: the keys are not lower-cased, and ids must stay exact. Rewrite it as "values of
the enum fields compare in ASCII lower case, keys exactly". Option B is simpler and matches the checker; choose A
only if the owner wants `SELF` accepted.

---------------------------------------------------------------------------------------------------------------------

## Item 6. Number readers

There are more than the three the brief names. All of them, fed the same input (i6.py, run on this tree):

```
input            rounds._number  plan_check.number  commands/ledger.number  cells.leading  cells.optional_number  cells.integer  audit_checks.number  records/ledger.count
'5'              5.0             5.0                5.0                    5              5                      5              5                    5
'+5'             5.0             5.0                5.0                    5              None                   None           5                    ValueError
'-5'             -5.0            -5.0               -5.0                   -5             None                   -5             -5                   ValueError
'5.5'            5.5             5.5                5.5                    5              None                   None           None                 ValueError
'1e3'            1.0             1000.0             1000.0                 1              None                   None           None                 ValueError
'1e'             1.0             1.0                1.0                    1              None                   None           None                 ValueError
'5abc'           5.0             5.0                5.0                    5              None                   None           None                 ValueError
'.5'             0.5             0.5                0.5                    0              None                   None           None                 ValueError
'٣' (Arabic 3)   0.0             0.0                0.0                    0              None                   None           3                    ValueError
'1_000'          1.0             1.0                1.0                    1              None                   None           1000                 ValueError
'' / '0x10'      0.0             0.0                0.0                    0              None                   None           None / 0.0           ValueError
'1234567890123'  1.23e12         1.23e12            1.23e12                1234567890123  None (13 digits)       None           1234567890123        ValueError
```

### Copies and callers

| Reader | file:line | Rule | Callers |
|---|---|---|---|
| `rounds._number` | commands/rounds.py:29-32 | awk prefix, float; sign and decimal point, NO exponent; blanks = space/tab | rounds.py:77 only (compares two events.tsv sequence cells: `council seat verify-N running`, the third-check refusal) |
| `plan_check.number` | commands/plan_check.py:31-34 (NUMBER :13) | awk prefix, float, WITH exponent, all whitespace blanks | plan_check.py:49-52, 212, 227, 239, 252: every call is behind `Value.whole()` (digits only) or `DIGITS.fullmatch`, so the sign, decimal and exponent branches cannot run on a checked plan; only `test_plan_check.py:111-113` reaches them |
| `commands/ledger.number` (+ `_PREFIX`, `_STRNUM`, `above_zero`) | commands/ledger.py:18-19, 61-70 | awk prefix, float, with exponent; `above_zero` compares non-numeric text with "0" as STRING (`"x" > "0"` is true) | ledger.py:86, 104-112 (`council ledger`) |
| `records/ledger.count`, `tokens_of` | records/ledger.py:40-52 | digits only, up to 12, else ValueError (the row is "unreadable") | `council ledger advice` (seat_advice) |
| `cells.leading` | cells.py:50-53 | awk prefix, integer, optional sign, blanks space/tab | cite_origin.py:28,30 (hunk headers), seat_notes.py:38,40, memory_audit.py:184, seat_write.py:98-99 |
| `cells.optional_number` | cells.py:56-60 | digits only, 1-12, no sign, trimmed; else None | usage.py:30-31, 84 |
| `cells.integer` | cells.py:39-47 | int or `-?[0-9]{1,12}`, trimmed; bool/list/None -> None; `abs() < 10**12` | gates.py:41,58, index.py:215-216, seats.py:117, snapshot.py:65 |
| `audit_checks.number` | commands/audit_checks.py:39-43 | `int(str(v).strip())`: accepts +, -, `_`, Unicode digits, any length | audit_checks.py:215, 352 |
| `usage.budget_value` / `agent_cap` | records/usage.py:183-197 | `[0-9]+` and `<= INTMAX` (2^63-1) | cap, status, close |
| `plan.budget` value | see item 1 | all blanks removed | |
| `cells.token_count` | cells.py:63-76 | separate, deliberate forms (74.3k, 1,200) | seat tokens=, not in this item |

### Can the helper produce an odd number?

Mostly no. `seats.tsv` tokens/agents cells come from `seat_write` after `token_count`/digits validation; the event
sequence is `int` from `events.append`; ledger rows are written from ints (`records/ledger`). The odd forms (`1e3`, `5abc`,
`+5`, `-5`, `.5`) occur through a hand edit or a legacy file. The hunk header numbers in `cite_origin` are
git output (`+12,3`); `words[2]` without a leading `+` (a malformed header) is the only way a sign gets in.
`cells.integer` keeps its sign deliberately: gate verdict JSON `exit` can be negative (a child killed by a signal), so
it must not become "no sign".

### What a user would see under the proposed rule ("plain ASCII digits, up to 12, else not a number")

- `rounds._number`: nothing for a real stream (digits). A hand-edited seq `1e3` or `5.5` becomes "not a number"
  (0 or refuse), not 1 / 5.5.
- `plan_check.number`: nothing for a checked plan (its branches are unreachable); `test_plan_check.py:111-113` changes.
- `commands/ledger.number` / `above_zero`: `council ledger` totals for a hand-edited ledger with `1e3` or `5abc`
  cells change (1000 -> not a number; the ledger's string-compare rule for "x" must be decided). The
  `ledger.count` reader already says "unreadable".
- `cells.leading`: `5abc` -> 0 instead of 5; `-3,4` -> 0 instead of -3 (the unit test pins both); a cell with `+12abc`.
  `seat_write._row` would stop adding to a tokens cell `5abc` (it would restart from 0): a written file differs
  for a hand-edited seats.tsv.
- `cite_origin.py:28-30`: a malformed hunk header (`-4,2`) reads start 0 instead of -4; no effect on well-formed git output.
- `memory_audit.span`: `40-44` splits at the first `-`, so a sign never reaches `leading`; `12abc` -> 0 instead of 12.
- The 12-digit limit conflicts with `budget_value` (INTMAX, ~19 digits) and with `evals/run_cli.py:1580`: an
  `agent-cap` of 23 digits means "a cap bash can't compare: the gate never fails closed". Under a 12-digit rule,
  `usage.agent_cap` would fall back to the configured cap. The scenario probably still passes (one seat) but its
  meaning changes.
- `cells.integer` must stay signed, or gate exit codes lose their sign. Say "no sign" only for counts.

### Pins today

- tests/py/test_cells.py:21-34 (`integer`, `leading` with `+12abc`, `-3,4`, `1e3`, `\r5`, `optional_number`)
- tests/py/test_plan_check.py:111-113 (`number` with `1e3`, ` 7x`, `-3`, `.5`)
- tests/py/test_reports.py:47 (`above_zero` with `x`, `-1`)
- tests/py/test_citations.py:42 (numbers read as bash test reads them)
- evals/run_cli.py:1580-1582 (23-digit cap)
- No eval exercises `1e3`.

### Decisions / contracts

D26 ("blank means unknown, never zero"): the rule must keep two outputs, "not a number" as None for usage figures and
as 0 for the awk-style adders (`leading`). One reader is fine; two thin wrappers (`number(text) -> int | None`,
`leading = number or 0`) keep D26 true. No contract name is touched (D23).

### Size and risk

Remove `rounds._number` (4), `plan_check.number` (4, plus `number_text` stays), `commands/ledger.number`, `_PREFIX`,
`_STRNUM`, `above_zero` (about 10) after one decision about the ledger string compare; fold `audit_checks.number`
(5) onto the shared reader; `leading`/`optional_number` become one function (about -4). Add about 8. Net about -20.
Risk: medium: nine readers, three behaviours (float, int, strict); the awk-prefix readers feed displayed totals and
`seat_write` writes a file.

### Better rule?

Mostly agree. Corrections: (1) keep sign for JSON ints (`cells.integer`); (2) the limit must be one number, 12 digits,
and `budget_value`'s INTMAX moves to it (that changes the 23-digit scenario on purpose); (3) say what "not a number"
means per caller (None for figures, 0 for sums, "unreadable" for ledger); (4) `rounds._number` and
`plan_check.number` are only ever fed digits on a valid stream/plan, so those two are plain folds onto the shared
reader with no visible change.

---------------------------------------------------------------------------------------------------------------------

## Item 7. The code-root "here" test

### Copies (all read `Listed.code_root`; `Listed` uses "" for a missing field, runs.py:20-43)

| Site | file:line | Test for "this run is on this tree" | Reached by |
|---|---|---|---|
| runs.status | commands/runs.py:34 | `in (tree, "")` | `council run status` |
| resolve.open_runs | commands/resolve.py:84 | `in (tree, "", "-")` | most `--run`-less commands |
| resolve.newest_run | resolve.py:89 | `in (tree, "", "-")` | `council audit` |
| cap.open_here | commands/cap.py:156 | `in (tree, "", "-")` | `council cap` |
| agent_gate.stops | commands/agent_gate.py:140 | `in (here.tree, "", "-")` | the Agent-start hook |
| session_start._runs | commands/session_start.py:78, 167 | line 78 turns every blank cell into "-", then `in ("-", top)` | the SessionStart hook; `_worktree` (:95) uses `not in ("-", wt)` |

### Proof (i7.py: four runs, code-root absent, `-`, this tree, `/elsewhere`)

```
code_roots:            ['/elsewhere', <tree>, '-', '']
runs.py:34   here =     [False, True, False, True]      <- "-" is "elsewhere: -"
resolve.open_runs:      3-review, 2-review, 1-review    (tree, "-", blank all count)
cap.open_here:          same
session_start (through its own blank-to-"-" step): only /elsewhere is "left open in a tree that no longer exists"
```

So five of six sites already treat "", "-" and the tree as "here". `runs.py:34` is the only outlier, and only for a
literal `code-root: -`. Fold, plus a one-line behaviour fix.

### What can a helper-written `code-root:` hold?

- `run_open.py:45, 70-79, 103`: `_code_root(--code-root)` is the realpath of an existing folder, `/` slashes
  (`os.path.realpath(...).replace("\\","/")`), or `where.this_tree()` (git's top level, else the current folder).
  Never "" and never "-".
- Absent (no `code-root:` line): only runs opened before `--code-root` existed (the "0.2 run", run_hook.py:391).
- Blank: only a hand edit (`code-root:` with no value).
- "-": the old bash `list_runs` printed "-" for a blank field; the Python listing never does. The only places a
  literal "-" exists are tests (test_spine.py:18) and a hand edit. The `"-"` in `agent_gate.py:140` and the others is a
  leftover of that bash convention, as is `session_start.py:78`.

### What a user would see under the proposed rule (one shared `here(code_root, tree)` = `in (tree, "", "-")`)

`council run status` prints `here` instead of `elsewhere: -` for a run whose state says `code-root: -`; nothing else. For
helper-written runs nothing changes.

### Pins today

- tests/py/test_spine.py:18 (a state with `code-root: -`, used by the spine tests, not by `runs.status`)
- evals/run_cli.py:3220 ("runs from the main checkout show as elsewhere in a worktree"), :3462-3479
- evals/run_hook.py:391 ("0.2 run with no code-root: treated as this tree's"), :346-419
- No scenario pins `elsewhere: -`.

### Decisions

None. The state field name `code-root` is a frozen name (§6, D23); its test is not.

### Size and risk

Add `runs.here(listed, tree)` (about +3), use it at 6 sites (about -6, since each tuple test becomes a call).
Net about -3. Risk: low (one hand-edit-only behaviour changes).

### Better rule?

Shared test as proposed. Also state in the docstring: "a helper-written code-root is an absolute path with forward
slashes; blank means a run from before `--code-root`; `-` is never written." Optionally drop "-" from the test and from
`session_start`'s normalisation (needs the owner's word: it changes `council run status`/hook output for a run with
`code-root: -`, which only a hand edit makes).

---------------------------------------------------------------------------------------------------------------------

## Same shape, not on the list

1. `state.header` against `runs.listed_fields` (both read session-state.md): `state.header` stops at the first `## `
   heading, keeps a bare CR inside a value, takes the first key; `runs.listed_fields` reads every `key: value` line of
   the whole file (also under headings), deletes every CR, turns tabs to spaces, takes the first key. Proven (i8.py):
   a `status:` line under `## Notes` is the status for `council run status` and for the listing that decides which runs
   are open (`runs.py:61-76`) but not for `state.header`. Bare CR: `{'mode': 'council-reviewstatus: x'}` against
   `{'mode': 'council-review\rstatus: x'}`.
2. Plan rows with a repeated `(kind, id, field)`: first wins in `closing._no_verdicts` (`next(...)`) and
   `audit_checks.Run.size`; last wins in `stages.required`, `plan.keyed`, `plan.budget`, `seat_rows.tool_budget`.
   Proven (i8.py): size solo then full gives stages 10 stages (last) and audit_checks "solo" (first). A checked plan
   cannot repeat a key (plan_check.py:132-133), so it matters only for an unchecked plan.
3. `agent_gate.read_call` (hook words): the LAST repeated word wins (`seat=a seat=b` -> b), pinned by
   tests/py/test_cap.py:104-107. If "first wins" becomes a rule for details, this is a different input (the hook's
   command line) and the test must stay unless the owner says otherwise.
4. `config.memory_path` against `config.memory_line` (both read the config's `- conventions:`): already on the
   "needs the user" list; item 3 row 1 shows they also differ on line splitting. `config.roster` against
   `config.roster_rows` is the same debt (`roster` uses `lines_of`, `roster_rows` uses `bytewise.records`).
5. `evidence.read_file` is the only reader that applies `paths.universal` (bare CR becomes a line break) to a council
   file; every other reader of synthesis.md and verify-*.md keeps a bare CR inside the line.
6. Blank sets: `cells.leading` and `rounds._number` count only space and tab as blanks; `plan_check.NUMBER` and
   `commands/ledger._PREFIX` count all whitespace including CR (`leading("\r5")` is 0 and pinned by
   test_cells.py:29).
7. `memory_draft.py:312` reads a temp file with `Path.read_text` (universal newlines), the only text-mode read in the
   package; it removes CRs itself (`rstrip("\r")`). A bare CR there becomes a line break. Not a council file, so not
   in the list; noted only because it is the same family.

---------------------------------------------------------------------------------------------------------------------

## Summary table

| Item | Real behaviour difference? | Reachable by the helper's own writes? | Size | Risk |
|---|---|---|---|---|
| 1 plan rows | yes (7 trims; 3-cell CRLF row is skipped by `budget`; inner blanks) | no (hand edit / editor CRLF) | ~0 | medium |
| 2 index.records | one corner (Windows, unterminated last line ending in CR); otherwise a plain fold. The `nt` split in `bytewise` is the real difference | no (git output, source files) | -6 (fold); -40 with the rule | low / medium |
| 3 splitlines | yes, and gate output with a bare CR is helper-reachable (repair `output:N`) | gate output yes; ask.md pasted text yes; others no | ~0 | low; medium for repair and evidence |
| 4 first/last | yes only for a skip reason holding `;skipped=`; `was`/`calls`/`basis` have one reader each | no | +2 | low |
| 5 keyed | premise wrong: values, not keys, are lower-cased; differs only on an unchecked plan | no (plan check refuses) | +/-3 | low |
| 6 numbers | yes (nine readers, three behaviours); `rounds._number` and `plan_check.number` are plain folds on valid input | no | -20 | medium |
| 7 code-root | one outlier (`runs.py:34` for a literal `-`); otherwise a plain fold | no (`-` is never written) | -3 | low |

Things not to do: do not drop the sign from `cells.integer` (negative gate exits); do not lower-case plan ids or
seat slugs; do not apply "one CR" to `lines_of` without changing test_plan_check.py:57; do not change
`agent_gate.read_call`'s last-wins with item 4; leave `repair_trail.classify` for last because
`repair check` re-derives the recorded `signal` and would refuse an old trail.
