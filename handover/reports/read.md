# read: the reading-rules builder

Worktree `SP\wt\clean-read`, branch `claude/clean-read`, from main a47fb43. All work is committed, nothing pushed.
I wrote this report early because the machine is shutting down. Some proof was not run; section 5 says which.

## 1. Commits, oldest first

1. d85f57b: Plan rows read one way: LF lines, the first row of a key wins, values trimmed of blanks (item 1)
2. f4e62fb: A file reads the same on every OS: a CR right before LF is dropped (item 2)
3. f6c26b6: Only a newline ends a line of a council file the evidence, audit and repair readers take (item 3, without classify)
4. d30008b: A count or figure is plain ASCII digits, 1 to 12 of them; anything else is not a number (item 4)
5. d849138: One test of "this run is on this tree": its code-root is this tree, blank or '-' (item 5)
6. e1bed72: The run listing reads a state's header only, as state.header does (item 6)
7. (one more): evals/ratchet.json rebuilt with --update (0 numbers went down)

## 2. Lines

`src/council/**/*.py`: 20,286 lines before, 20,220 after (-66).

| Item | src added / removed | whole commit added / removed |
|---|---|---|
| 1 | +33 / -41 | +66 / -46 |
| 2 | +7 / -12 | +25 / -30 |
| 3 | +13 / -25 | +32 / -28 |
| 4 | +40 / -76 | +70 / -94 |
| 5 | +11 / -5 | +25 / -5 |
| 6 | +22 / -33 | +33 / -39 |

## 3. Items

### Item 1: plan rows
- **The rule.** Rows come through the new `cells.tab_rows` (lines from `cells.lines_of`, every trailing CR cut, raw cells). `cells.tsv_rows` also uses it.
- **`plan.keyed` is the one keyed reader:**
  - any row of 3 or more cells counts; the value is the 4th cell, or '' when there is none;
  - the value is trimmed of spaces and tabs only (`bytewise.trim`) and is never lower-cased;
  - keys are exact;
  - the FIRST row of a key wins.
- **The readers on top of it:**
  - `plan.budget(run, field, ident="run")` returns the value if it is plain digits, else ''.
  - `seat_rows.tool_budget` is `plan.budget(run, "tool-calls", slug)`.
  - `stages.required`, `plan.selected` and `seat_rows.is_verifier` read `keyed`.
  - `plan.summary` uses `tab_rows` and is first-wins too. The brief's "every reader" covers it; summary was not on the brief's list, so this is a judgment call.
  - `plan_check` is untouched.
- **Visible differences** (proven in `SP\scratch\read\cases_read.py` `plan_rows`):
  - CRLF plan with `agent-cap " 2 "` then `7`: `council cap` said `0 of 7`, now says `0 of 2`.
  - `budget hunt tool-calls 3` then `30`: the seat note named a tool budget of 30, now 3.
  - `estimated-tokens "1 000"` read as 1000 (the event `run.estimate_passed` was written and the status card said "over estimate"). Now it is no estimate.
  - `run run size solo` then `full`: stages now take solo (first row).
  - A padded ` selected ` now counts as selected.
  - `verification level SELF` is no longer `self`, so evidence no longer treats the run as self-checked.
- **Scenario:** run_cli `agent_stop` block (collect), check "plan rows: a CRLF plan's first agent-cap and tool budget win, trimmed; '1 000' is no estimate". Unit test `test_plan.test_one_rule_for_every_reader`, plus a stages line in `test_spine`.
- **Pinned tests changed:**
  - `test_plan.py` budget: "6" became "8", and the test was renamed `test_budget_takes_the_first_row_trimmed`.
  - `test_plan.py` keyed: level "self" became "SELF", and the agent-cap value "6" became "8".
  - `test_seat_files.py:65`: tool_budget "40" became "30".

### Item 2: one OS rule
- **The rule.** `bytewise.records(fold=True)` drops a CR right before LF on every OS. The `os` import is gone from bytewise and gate_failed.
- `run_events.show` and `gate_failed.indent` lose their `os.name` test.
- **Visible differences on Linux/macOS only; Windows is unchanged:**
  - `council run events show` stdout and a failed gate's excerpt lines lose the CR. These are printed, not written.
  - **A written file differs:** a CRLF `session-state.md` rewritten by `state_write.change` now comes back all LF. Before, only the rewritten line lost its CR.
  - A CRLF seats.tsv `skipped\r` now reads as skipped.
- **Scenario:** run_cli `runs_worktrees_close_and_find`, check "state: a CRLF state file is rewritten with LF line ends, on every OS".
- **Pinned tests changed** (each lost its `os.name` split and now expects the Windows result):
  - `test_earlier_scope.py:30, 48`
  - `test_gate_command.py:108, 297`
  - `test_reports.py:53`
  - `test_seats.py:86`

### Item 3: only LF ends a line
- **Changed:**
  - `evidence.py`: the 4 sites read `lines_of`, and `read_file` no longer calls `paths.universal`.
  - `audit_checks.py:291` reads `cells.jsonl_rows`.
  - `repair_trail.load_ledger` reads `bytewise.records`; `allowances` reads `cells.tab_rows`.
  - `paths.universal` and its test are deleted.
- **Visible differences** (case `lf_only`):
  - A synthesis kept line holding a bare CR, or a verify row holding a form feed, used to be "unreadable kept item" (exit 2). Now it is one claim with its verdict linked.
  - A CRLF claims.jsonl that was hand-converted now reads as stale.
- **Scenario:** run_cli `close_claim_index` (filing), check "evidence build: a bare CR or a form feed does not end a line — one claim, its verdict linked".
- **`repair_trail.classify` is NOT changed** (section 7).

### Item 4: numbers
- **The rule.** `cells.optional_number` is the one reader: ASCII digits, 1 to 12 of them, ends trimmed. `cells.leading` is that number or 0.
- **Folded onto it:**
  - `rounds._number`;
  - `plan_check.number`, `NUMBER` and `DIGITS`. `Value.whole()` is now `optional_number is not None`, and `number_text` accepts ints;
  - the ledger's `_NUMBER`, `_PREFIX`, `_STRNUM`, `number` and `above_zero`. A cell that is not a number is not above zero;
  - `audit_checks.number`.
- **Plan budgets:** `usage.budget_value` and `agent_cap` take 12 digits at most. INTMAX is no longer used there. `cells.integer` and `token_count` are untouched.
- **`cite_origin` is not edited.** It strips the `+` before calling `leading`, so a well-formed `+14,5` header still reads 14 and 5.
- **Visible differences:**
  - A 23-digit agent-cap: `council cap` said `0 of 999…9`, now says `of 10`. The configured cap stands.
  - seats.tsv tokens `5abc` plus a 1000 report: written as 1005, now 1000. **This is a written file.**
  - `council ledger` with cells 1e3, 5abc, +2 or -1: they used to count; now they count 0.
  - The plan check refuses a 13-digit-or-longer value, e.g. estimated-tokens, with "must be a … integer". Before, it was valid.
  - `memory_audit.span("12abc")` is now None.
- **Scenarios:**
  - `agent_stop`: the 23-digit scenario is re-stated. The starter plan's agent-cap row is replaced rather than appended, because first-wins would ignore an appended row. It now checks "1 of 3 agent runs used".
  - run_cli ledger check: "ledger: a cell that is not plain digits counts as nothing".
- **Pinned tests changed:**
  - `test_cells` (leading and optional_number);
  - `test_plan_check.py:111` (the `number` assertions are removed);
  - `test_reports.py:45` (replaced by a Table test).

### Item 5: code-root
- **The rule.** `records/runs.here(code_root, tree)` is `in (tree, "", "-")`. It is used in commands/runs.py, resolve.py (2 sites), cap.py and agent_gate.py:140.
- **Visible difference:** `council run status` used to show `elsewhere: -` for a run whose state says `code-root: -`. It now shows `here`.
- **Scenario:** run_cli "run status: a run whose code-root is '-' is here, as every other reader takes it". Unit test in `test_listing`.

### Item 6: listing reads the header only
- **The rule.** `runs.listed_fields` is `state.header(content, exact_keys=True)`, or None for an empty file. The D34 load pins are not touched, because records imports are not counted.
- The open listing takes a run as open when its header's status matches `(in-progress|paused)`. The byte-wide `OPEN` regex and `KEY` are gone.
- **Visible differences:**
  - A `status:` line below `## ` no longer opens a run (`run status` now says "no open council runs").
  - Tabs in values are no longer turned into spaces.
  - An inner bare CR is kept.
- **Scenario:** run_cli "run status: a status line below the state's first heading does not make a run open".
- **Pinned tests changed:**
  - `test_listing`: the "status anywhere" test became `test_only_the_headers_status_opens_a_run`;
  - `test_fields_as_list_runs_reads_them`: mode is now "a\tb", and `actual` below the header is gone.

## 4. Proposed CHANGELOG lines (### Changed)
- A plan's rows read one way in every reader: the first row of a repeated key wins, a value is trimmed of spaces and tabs only and never lower-cased, and a budget that is not plain digits (for example `1 000`) is unset.
- A CRLF council file reads the same on Linux and macOS as on Windows: the CR before each newline is dropped, and a state file the helper rewrites comes back with LF line ends.
- council evidence reads synthesis.md, verify files and claims.jsonl with only a newline ending a line: a bare CR or a form feed inside a claim is text.
- A count or figure is plain ASCII digits, 1 to 12 of them. A ledger or seats.tsv cell such as 1e3, 5abc or -1 counts as nothing, a plan value past 12 digits fails the plan check, and a plan agent-cap past 12 digits leaves the configured cap in force.
- council run status says `here` for a run whose state says `code-root: -`.
- A status line below a state file's first heading no longer makes a run open.

Architecture §8 wording should change in four places:
- "read a TSV row" should point to `cells.tab_rows` and `plan.keyed`;
- "a number" should point to `cells.optional_number` and `leading`;
- "this tree" should point to `runs.here`;
- the run listing now reads the state header.

## 5. Proof

**Run:**
- quick_validate: pass.
- `run_all.py --fast`: 11 jobs, 0 failed.
- ruff: clean.
- ratchet `--update` and then the ratchet check: pass, "ShellCheck measured".
- tests/py: 438 to 440 tests, OK, at every commit.
- `run_cli --group runs`: 540/540 on the final tree.
- `run_cli --group collect --block agent_stop`: 33/33.
- `run_cli --group filing --block close_claim_index`: 8/8.
- run_evidence.py: 47/47.
- run_repair.py: 39/39.
- My own case file, `SP\scratch\read\cases_read.py` (6 cases, 20 calls): every difference is a stated one, listed in section 3.

**NOT run** (stopped for the shutdown):
- run_cli groups collect (full), citations, gates, requests, filing (full), reports, models;
- `run_hook.py --group main`, run_status.py, run_audit.py, run_memory.py;
- the old-against-new run over the six case sets and hookcmp. It was started and stopped during cases_spine_a, so there are no results.

The merge step must run all of these.

## 6. needs_integration
- **`commands/session_start.py:167`:** `r.code_root in ("-", top)` should become `runs.here(r.code_root, top)`.
- **`commands/session_start.py:95`:** `r.code_root not in ("-", wt)` should become `not runs.here(r.code_root, wt)`.
- **`records/state_write.py:152-154`:** the `raw_lines` docstring is now wrong. It should say "a CR before a newline is dropped on every OS".
- **`commands/memory_draft.py:86`:** `verifier_reason` still uses `splitlines()`. It should use `cells.lines_of`, to count lines the way evidence now does.
- **`commands/run_open.py:107`:** still has an `os.name` CRLF fold on the plan template it writes.

## 7. needs_user
**`repair_trail.classify` was not changed (item 3, row 2).** Two things re-derive the recorded signal and refuse "repair classification changed from saved output" when it differs:
- `council repair check` (`repair_trail.proven`). It runs on closed runs too; `closed.refuse` guards only record and allow.
- `council memory propose repair` (`memory_draft.draft_repair` through `inspect_rows(check=True)`).

A trail the old code recorded for a gate output holding a bare CR or FF has `output:3:` where the new count gives `output:1:`. Changing `classify` would therefore newly fail those checks. It needs the owner's word, for example to accept old signals as well.

## 8. Stops, and what I was tempted to do but did not
- Stopped: `classify`, as above. No other stops.
- Tempted, not done:
  - `evidence show` prints claim text raw: a CR or ESC in a claim reaches the terminal. Control characters already passed through before this change.
  - `records/citations.bash_int` is another number reader, signed and up to INTMAX, and is not in my files.
  - `config.agent_cap` still allows up to INTMAX.
  - `usage.py:218` still uses INTMAX.
