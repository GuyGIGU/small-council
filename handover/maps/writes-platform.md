# Map: writes, platform, legacy (read-only)

Tree read: `...\scratchpad\wt\cut-views` (HEAD 56e5560, after the cut D40). Python 3.14.10, Windows 11, Git Bash. Snippets are in
`...\scratchpad\maps-clean\scratch-c\` (a1.py appends, a2.py replaces, a3.py native, a4.py absolute tests, a5.py stamp, a6*.py search, a8.py CR).
Nothing in the tree was changed. Proofs below were run on Windows only; where a result depends on POSIX (file modes) I say "read from code, not run".

Short answers first:

| # | Item | Verdict |
|---|------|---------|
| 1 | `_append_start` vs `append_row` | Plain fold of the bytes, plus three things the caller must keep (seed row, tab strip, swallow OSError per D20). Differs only on unreadable-but-writable files and on a transient write failure. |
| 2 | `state_write.replace` vs `atomic_write(keep_mode=True)` | Nearly a plain fold. Real differences: temp-file name, and file mode on POSIX (only if the user chmod'd the state file). |
| 3 | The two `cygpath` calls | There is only ONE call left in the tree (the other went with the tui cut). Nothing to fold. |
| 4 | "Is this path absolute" | Real behaviour differences, in three families. One helper is right, but pick its rule on purpose. |
| 5 | `hygiene.stamp` | Plain fold for the helper's own format; one real bug fixed (minute-only `opened:`); `os.utime` is the wrong tool (it SETS times; the job is parsing). `clock.local_moment` replaces it. |
| 6 | `memory_tree._search` | Dead code in every supported environment, never exercised by any check. Real differences from grep exist (proved). A pure-Python search over `Tree.files` is simpler and was not slower in a test. |
| 7 | 0.1/0.2 readers | Four on-disk shapes in group A; only open runs (and one long-lived file: a root `conventions.md`). Details in section 7. |
| 8 | Same kind | A fourth/fifth torn-line appender, a CR-strip done 5 ways, `WINDOWS_BASH` vs `os.name`, drive-letter conversions done 6 ways. |

---------------------------------------------------------------------------------------------------

## 1. `agent_gate._append_start` against `paths.append_row`

### Copies

- A: `src/council/commands/agent_gate.py:182` `_append_start(file, seed, tool, session)`, with helpers `_filled` (:197), `_ends_line` (:204), `_write` (:213). About 40 lines in all (182-218).
  Only caller: `count_start` (:163, line 176), under the file's `.lock` (`locks.acquire(lock, 50)`). `count_start` is reached from `agent_gate.check` (:156), which is `council cap check` (`cap.py:38-39`), which is the PreToolUse hook `hooks/agent-gate.sh:133` (`set -- cap check --session ...`). So it is a hook path: D20 (a hook lets the call through on its own fault) applies.
- B: `src/council/records/paths.py:159` `append_row(file, head, cells)`. Callers: `commands/cap.py:72` (`_file_go`, `council cap allow`; it turns OSError into `Refusal "the go was not recorded: cannot write ..."`) and `records/repairs.py:19` (`allow`, `council gate`/`repair` allowance).

### What each does (run, a1.py; B's `T` is the timestamp I passed)

Input file -> output, both ways, identical except the timestamp cell:

- missing / empty: `at\ttool\tsession\n` + row. Same.
- torn last line (`...T\tx\ts` no newline): `...T\tx\ts\n` + row. Same ("never join a torn line").
- CRLF file: new row ends `\n`, old CRLF rows untouched. Same.
- file with no header and content (`junk\n`): row appended, header not added. Same.
- non-UTF-8 byte `\udcff` in the file: preserved as `\xff`. Same.

Differences (these are the only ones):

| Case | A (`_append_start`) | B (`append_row`) |
|---|---|---|
| Seed row: new file and `seed > 0` writes `<stamp>\tbefore:<n>\t-` first | yes (`before:5` row proved) | no such feature; two calls would do it |
| Tab in session id | replaced by a space (`s\t1` -> `s 1`) | cells written as given; a tab would add a column. The other two callers pass `clock` stamps, numbers and redacted words, not a free-form session id |
| Any OSError | swallowed per write (`_write` has `except OSError: pass`) | raised. Proved: a path that is a directory -> `PermissionError`; missing parent -> `FileNotFoundError`; read-only file -> `PermissionError`. A: no raise in all three |
| File exists but cannot be read (stat fails) and is writable | header re-written with `wb` (would truncate), then row | `read_bytes()` raises, nothing written |
| Torn-line test | reads only the last byte (`seek(-1, END)`) | reads the whole file every time |
| Writes per row | up to 4 separate opens (head, seed, newline, row); a failure between them leaves a header-only or seed-only file | one `write` of lead+row, all or nothing |

Everything else (bytes, newline, final-newline repair, file creation, utf-8 + surrogateescape) is the same.

### What a user would see if A used B

Normal use: nothing. Only a start where the starts file cannot be written would differ: today the start is silently uncounted (D20 hold); with B the hook must still catch OSError (one `try/except OSError: pass` around the two calls) to keep D20. On the unreadable-but-writable file, one start would go uncounted instead of being counted (A's behaviour there is also the dangerous one: it truncates). No platform difference.

### Pins

- `tests/py/test_cap.py:150-163` `test_a_start_is_counted_once_with_a_seed_and_never_joins_a_torn_line`: exact bytes (`at\ttool\tsession\nNOW\tbefore:2\t-\nNOW\tAgent\ts 1\n`, torn line, tab -> space, refused start not counted, 5 lines).
- `evals/run_cli.py:6866-6872` (starts file read, one `\tAgent\t`), `evals/run_hook.py:1281, 1494, 1734` (count of `\tAgent\t`), `evals/run_audit.py:770, 777` and `tests/py/test_usage.py:95`, `test_seats.py:22,46` (read seeded files; they do not call the writer).
- Not pinned: any failure to write (D20 fault case for the starts file) — I found no scenario that makes `agent-starts.tsv` unwritable. `append_row` has no direct test either (callers: `run_cli.py:1477, 1554, 5288` read `cap-allowances.tsv`, `repair-allowances.tsv`).
- `docs/architecture.md` §8 row "Write a shared TSV row: under the run's lock; never join a torn line" names no function; `append_row` is the natural owner. §6 freezes the file name and columns `at/tool/session` (D23) — unchanged by the fold.

### Size / risk

About -30 lines (`_filled`, `_ends_line`, `_write`, most of `_append_start`), +8 (a try/except and two `append_row` calls). Better: let `append_row` read only the last byte (as A does) so it stops reading the whole file: +3 lines. Risk: low. It is a hook path, so keep the swallow (D20) and the tab strip in the caller; `commands/agent_gate.py` is in the ratchet (322 lines), a drop must be recorded with `run_ratchet.py --update`.

---------------------------------------------------------------------------------------------------

## 2. `state_write.replace` against `paths.atomic_write(keep_mode=True)`

### Copies

- A: `src/council/records/state_write.py:174` `replace(file, content: str)`. Callers: `state_write.py:80` (inside `_locked`, which is `change()`, i.e. `council state`, run open/close/resume, `ask save`, seat/cap/gate/repair/turn-end through `change` and `clear_waiting`), and `commands/run_resume.py:70` (`_unclose`). All under the state lock.
- B: `src/council/records/paths.py:179` `atomic_write(path, data: bytes, prefix, suffix="", keep_mode=False, refuse_link=False)`. 9 users with keep_mode (`gate.py:237`, `run_events.py:81`, `audit_file.py:78`, `ledger.py:114`, `memory.py:202`, `seat_write.py:90`) and 3 with refuse_link (`evidence.py:450`, `repair_trail.py:138`).
- Both end in `paths.swap_in` (os.replace, retried ~1 s on Windows PermissionError). So the Windows "reader holds the file" behaviour is already shared.

### Differences (a2.py)

| | A `replace` | B `atomic_write(keep_mode=True)` |
|---|---|---|
| Temp name | `<file>.tmp<pid>` e.g. `session-state.md.tmp15288` (seen in a spy on swap_in) | random, hidden: `.state.h56sqsjv` (prefix is the caller's) |
| Place | beside the file | beside the file (`dir=path.parent`) |
| Mode of result | the temp's own mode: `0666 & ~umask`. An existing file's chmod is lost. | existing file's mode kept; a new file gets `0666 & ~umask`. Read from code (`paths.py:187-196`); NOT provable on Windows (chmod only toggles read-only: all three modes I tried came out 0o666 on both) |
| Content type | `str`, utf-8 + surrogateescape inside | `bytes`; the two call sites would add `.encode("utf-8", "surrogateescape")` |
| fsync | none | none |
| Failure after the temp is written (swap_in raised OSError) | OSError raised, temp unlinked, original untouched (proved: nothing left behind, content `o`) | the same (proved) |
| Missing parent | `FileNotFoundError` | `FileNotFoundError` |
| Read-only target (Windows) | `PermissionError` | `PermissionError` (after the 1 s retry) |
| Killed mid-write | leaves `session-state.md.tmp<pid>`; the next write by a process with the same pid overwrites it, otherwise it stays | leaves `.state.XXXXXXXX`, never overwritten, accumulates |
| Symlink target | replaced by a regular file | same (`refuse_link` is off by default) |

Callers catch OSError and turn it into `StateError("cannot update <file>")` (state_write.py:81) or `Refusal("cannot update ...")` (run_resume.py:75): that stays.

### What a user would see

Nothing in normal use. Only a state file that the user chmod'd (say 0600 or group-writable) on macOS/Linux: today each `council state` resets it to the umask default; after the fold it keeps the mode. That was the reason the shared builder marked this `needs_user` (`reports-s11/shared.md:42,110`). With "old quirks need not survive" this is the cleaner behaviour. A stray temp after a hard kill changes from `session-state.md.tmp123` to `.state.xxxx` (hidden, not overwritten). I found nothing that scans for either name (grep `.tmp` in src/evals/hooks/docs: only the owners themselves and `tests/py/test_paths.py:91,98`, which build their own temp names for `swap_in`).

### Pins

`tests/py/test_paths.py:70-87` (atomic_write replaces, leaves no temp; keep_mode keeps permissions; refuse_link), `:90-101` (swap_in). Nothing pins state_write.replace by name or temp name. Behaviour of `council state` is pinned wholesale by `evals/run_cli.py` (state, run resume `:3614-3640`) and `tests/py/test_state.py`.
Docs: `architecture.md` §8 "Swap a file in" already lists State among the users of `swap_in`/`atomic_write`. D23 not touched (the temp name is not a contract name).

### Size / risk

-8 lines in `state_write.py` (the function and its docstring) and +2 at the call sites for the encode; one fewer way. Risk: low (same swap, same failure result). Do NOT drop `keep_mode` (without it the state file becomes owner-only 0600: mkstemp default).

---------------------------------------------------------------------------------------------------

## 3. The `cygpath` calls

Search of `src/`, `bin/`, `hooks/`, `scripts/`, `evals/*.py`, `tests/`, `docs/`: four hits, ONE call.

- `src/council/records/home.py:95` `native(value)`: `cygpath -m <value>`, `stdout=PIPE, stderr=DEVNULL, encoding="utf-8", errors="replace", timeout=10`; result `.strip()`, used only when the exit code is 0 and the text is not empty; on OSError, timeout, failure it returns the input unchanged. It runs only when `os.name == "nt"`, the value starts with `/`, is not `//...`, and is not the one-letter-drive shape (`/c`, `/c/...`, handled in pure Python at :92-93).
- `src/council/commands/script_cmds.py:61` and `commands/run_open.py:71` only mention cygpath in a docstring; both call `where.native`.
- `bin/council` has no cygpath. Its launcher does the same job in bash: `/[a-zA-Z]/*` -> `X:` (line 18) and `pwd -W` (line 19). It must stay bash (it runs before Python).
- The second call the earlier builder meant was in `commands/shell.py` (`helper_bash_mixed`: `cygpath -m` of the bash.exe path). It was removed with the tui cut: `git grep cygpath e68896f^` shows it; at HEAD `shell.py` has no cygpath.

Form asked: always `-m` (mixed: `C:/Users/x`). `-w` and `-u` are never used. Proved (a3.py): `/c/x` -> `C:/x` (fast path, 0.00 s), `/tmp/x` -> `<home>/AppData/Local/Temp/x` and `/usr/bin` -> `C:/Program Files/Git/usr/bin` (cygpath, 0.02 s), `//server/x`, `C:/x`, `C:\x`, `\x`, `c:x`, `~`, `x` returned untouched, `/1/x` goes to cygpath. Edge: `/c:/x` -> `C:/Program Files/Git/c\uf03a/x` (garbage; nobody passes this).

`native` already serves every caller (120 `where.native` uses). The "timeout 10 s against none, decoding and strip" difference is gone with the second call. Nothing to fold; plain no-op for this item. Do not "improve" by dropping the fast path: it avoids a process for the common `/c/...` MSYS form, and the launcher cannot share it.

Pins: none by name (`evals/run_cli.py:4360` uses `/tmp/run` as a run path on Git Bash, which crosses `native`). `docs/architecture.md` has no cygpath row.

---------------------------------------------------------------------------------------------------

## 4. "Is this path absolute": every site in `src/council/`

Run a4.py (Windows, Python 3.14). Y = counted absolute (not joined to a root). The tests are copied from the sites.

Test families (names are mine):

- **S1** `p.startswith("/") or re.match(r"[A-Za-z]:", p)` (and the same set as `re.match("/|[A-Za-z]:", p)`). Accepts `/x`, `//x`, `C:x`, `C:/x`, `C:\x`. Does NOT accept `\x` or `\\srv\x`.
- **S1n** S1 after `p.replace("\\", "/")`. Also accepts `\x`, `\\srv\x`.
- **S2** `startswith("/") or re.match(r"[A-Za-z]:/")`: drive must be followed by `/` (after `\`->`/`): so `c:x` is relative.
- **D** `os.path.isabs`; **P** `Path.is_absolute()`. These follow the machine: on Windows (3.13+) `C:/x`, `C:\x`, `//server/x`, `\\srv\sh\x` are absolute but `/c/x`, `/x`, `\x`, `c:x` are not; on POSIX `/c/x`, `//server/x` are absolute and `C:/x`, `C:\x` are not. (Python 3.8-3.12 on Windows treat a lone-slash `/x` as absolute for `os.path.isabs`; 3.13 changed that. I ran 3.14 only; this is from the CPython changelog. D24 says 3.8+.)

Matrix (a4.py output; Y/-):

| input | S1 | S1n | S2 | S2n | `^/` only | isabs win | isabs posix | Path win | Path posix |
|---|---|---|---|---|---|---|---|---|---|
| `C:/x` | Y | Y | Y | Y | - | Y | - | Y | - |
| `C:\x` | Y | Y | - | Y | - | Y | - | Y | - |
| `/c/x` | Y | Y | Y | Y | Y | - | Y | - | Y |
| `//server/x` | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| `\x` | - | Y | - | Y | - | - | - | - | - |
| `c:x` | Y | Y | - | - | - | - | - | - | - |
| `~`, `~/x`, `x`, `./x`, `` | - | - | - | - | - | - | - | - | - |
| `\\srv\sh\x` | - | Y | - | Y | - | Y | - | Y | - |

`~` is absolute nowhere (no site expands it). `proof_reach.py:152` treats `~` and `$` as "not a relative program" — a different question, leave it.

### The sites

S1 (no backslash normalising first):

1. `commands/cite_check.py:44-45` `absolute(path)` — the only existing helper; used at :51, :70, :90.
2. `commands/check.py:159` (deliverable of a post-game, prepends `dirname(home)`).
3. `commands/doctor.py:91` (roster/card ref -> file path).
4. `commands/doctor.py:226` (inside `active_run`: the pointer's first line).
5. `commands/memory_tree.py:39` (`Tree.path`) and `:130` (`line_counts`).
6. `commands/proof_reach.py:87` (token) and `:91` (`landed.startswith(("/", "../")) or re.match(...)`).
7. `commands/sharing.py:265` (git's `info/exclude` path).
8. `records/citations.py:211` (a citation's place).
9. `records/memory_audit.py:157` (memory anchor path; `shown` was `\`->`/` before? not at this line).
10. `commands/run_close.py:113` (`re.match("/|[A-Za-z]:", named)`, active-run pointer).
11. `commands/session_start.py:264` (`re.match(r"/|[A-Za-z]:", run)`, active-run pointer).
12. `records/seat_files.py:85` (`out:` of a seat, `re.match("/|[A-Za-z]:", out)`).
13. `commands/ask.py:86` — S1 after `cur.replace("\\", "/")` (so S1n).

S1n / variants:

14. `records/memory.py:41-43` `absolute(root, p)`: after `\`->`/`: `C:` -> returned as is; `/x` is the repo's root unless that absolute file exists (`root + p`); everything else relative. This one has its own MEANING of a leading slash; not a plain absolute test.
15. `commands/memory_draft.py:73-74`: after `\`->`/`, rejects `startswith("/")` only (a citation may not be absolute); `C:/x` is rejected by the separate `[*?<>|\"`:]` check (`:` in the path).
16. `commands/audit_checks.py:265` `os.path.isabs(recorded)` then `:267 recorded.replace("\\","/").startswith(".council/")` (a mix of D and normalise).

S2:

17. `commands/resolve.py:63` `absolute = folder.startswith("/") or re.match(r"[A-Za-z]:/", folder)`, after `\`->`/`, trailing slashes cut.

D (`os.path.isabs`):

18. `git.py:62` (`rev-parse --git-path index` result: git prints `C:/...` or a relative path; fine on every platform).
19. `commands/memory_draft.py:124` (`deliverable`).
20. `commands/audit_checks.py:265` (same as 16).

P (`Path.is_absolute`):

21. `commands/patch.py:139` (`input=`), 22. `commands/plan_tasks.py:34` (`deliverable`), 23. `records/request.py:56` (`is_absolute() or re.match(r"[A-Za-z]:")`, so a Windows drive path on POSIX counts), 24. `views/snapshot.py:169`, 25. `views/status.py:195`, 26. `views/status_closing.py:30`, 27. `commands/evidence.py:59` (rejects a proof path that is absolute: `Path(value.replace("\\","/")).is_absolute() or re.match(r"^[A-Za-z]:", value)`).

Neighbours that convert a drive form rather than test absoluteness (item 3's "forms"): `records/home.py:90-93` (`/c/x` -> `C:/x`), `commands/cite_check.py:55-59` (same, for a tree top), `commands/memory_select.py:70` (`/c/` -> `C:`), `commands/home.py:27` (`C:/x` -> `/c/x`, reverse, for an Edit rule), `commands/session_start.py:67-68` (`C:\x` -> `C:/x`), `bin/council:18` (bash). `records/citations.py:167` (`[A-Za-z]:[/\\]` means "a drive letter, not a line number"), and `records/home.py:72` (`logical.startswith("/")` on POSIX only) are not absolute tests of user input.

That is 27 test sites in 4 shapes, plus 6 conversion sites — more than the "about 16" counted before; the S1 family alone is 13.

### Where they disagree (real effects)

- **Windows Git Bash user types `/c/Users/me/x.md`** (very natural in Git Bash). S1 sites say absolute, then `where.native` turns it into `C:/Users/...`. P sites (21-26) say relative (Path win: `/c/x` -> `-`) and join it to the root: `deliverable=/c/Users/me/plan.md` -> `<root>/c/Users/me/plan.md`, not found. So `plan_tasks.py:34`, `patch.py:139`, `status.py:195`, `snapshot.py:169`, `status_closing.py:30` disagree with the S1 sites on this input. (They do not call `native` either.)
- **`C:/x` on POSIX** (a state file copied from Windows): S1/S2 say absolute; P/D say relative. `request.py:56` has the extra regex so it says absolute.
- **`\x`, `\\server\x`**: S1 says relative (and then adds `root/`), S1n/S2 and isabs-win say absolute.
- **`c:x`** (drive-relative): S1, request, evidence say absolute; S2, isabs, Path say relative.
- **`~`**: all relative (nothing expands it), consistent.

### One helper

Propose `records/home.absolute(p) -> bool` = `bool(re.match(r"[/\\]|[A-Za-z]:", p))` ("rooted, or has a drive"). It treats every form in the matrix except `~`, `x`, `./x` as "do not prefix the root", which is what each caller needs; it is independent of `os.name`, so state written on one platform reads the same on another. Callers that need an OS path then go through `where.native` (existing). Where a site wants "reject absolute" (evidence:59, memory_draft:74, proof_reach:91) the same helper serves.
Do NOT use `os.path.isabs`/`Path.is_absolute` for values that arrive as text from a state file or a user: their answer depends on the OS and Python version (proved above).
Keep as separate: `records/memory.py:41-43` (its leading `/` has the repo-root meaning), `resolve.py:63` (could use the helper; then `c:x` becomes absolute there too — harmless), `memory_draft.py:74`.

User-visible change if all sites used it: only for the inputs in the disagreement list: `\x`/`\\srv\x` (rare), `/c/x` on the P sites (now found instead of "not found"), `C:\x` on POSIX. Same refusal texts. Windows Git Bash gains; macOS/Linux unchanged except `C:/x` in P sites.

Size: the 13 S1 lines each become a call (same length); remove `cite_check.absolute`'s body; most `re` imports in those files go unused (check with ruff before removing). Net about -10 to -20 lines plus the helper (+4). Risk: low for S1, medium for P sites (the helper plus `where.native` must be applied together or a `/c/x` string reaches `Path.read_bytes` unconverted; do those six as a second step).

Pins: `evals/run_hook.py` / `run_cli.py` pass relative and `C:/` forms throughout; nothing pins `\x` or `c:x`. Specific: `tests/py/test_paths.py:112-120` (`home_from`), `tests/py/test_memory_audit.py`, `test_seat_files.py`, `test_plan_tasks.py`, `test_citations.py` run the S1 sites on POSIX-style inputs. `evals/run_cli.py:3667` (`--run .council\runs\<name>\` from a worktree) pins backslash normalising in `resolve`. Decision touched: D23 (none: no contract name), architecture §8 has no row for this; a new row would be added.

---------------------------------------------------------------------------------------------------

## 5. `hygiene.stamp`

`src/council/commands/hygiene.py:101` `stamp(opened) -> float | None`. Only caller: `hygiene._read` :189 `untracked(top, stamp(opened) if opened else None)`; reached from `council check` (`check.py` imports hygiene) in a just-me build. `opened` is the state's `opened:` field.

"`touch -t` forms": there was ONE command in the old bash, `touch -t "$(printf '%s' "$since" | tr -d ' :-' | sed 's/\(..\)$/.\1/')" "$ref"` (bash `bin/council` before commit b0d3ff3, line 3675: "touch -t [[CC]YY]MMDDhhmm[.SS]: BSD, GNU and Git Bash alike"). The 8-, 10- and 12-digit branches in `stamp` (lines 110-115) are touch's grammar (MMDDhhmm; YYMMDDhhmm with the 69 century rule; CCYYMMDDhhmm), not platform forms. All three touch implementations accept the same grammar. The helper only ever writes `opened:` as `%Y-%m-%d %H:%M:%S` (`clock.now_sec`, `run_open.py:102`), i.e. 14 digits -> the 12-digit + `.SS` form. The 8/10-digit branches are dead for helper-written values.

`os.utime` is not a replacement: it sets file times; here the job is to PARSE a time to a float, and the old `touch` was only a way to get a reference time. The in-Python replacement is `clock.local_moment(opened).timestamp()` (`clock.py:37`, which takes `YYYY-MM-DD HH:MM[:SS]`, local time).

Proof (a5.py, `stamp` vs `clock.local_moment(...).timestamp()`):

- Same: `2026-11-15 10:30:45`, with padding, `1999-01-02 03:04:05`, DST-gap `2026-03-29 02:30:00` and DST-overlap `2026-10-25 02:30:00` (equal floats), invalid dates (`2026-02-30`, hour 24), `` , `x`, `T..Z` forms (both None).
- DIFF: `2026-11-15 10:30` (minute only): `stamp` -> None (digits `202611151030` become `2026111510.30`, read as YYMMDDhhmm + `.30` s: month 26, rejected); `local_moment` -> 1794731400.0. So today a minute-only `opened:` makes `untracked` count EVERY untracked file (since=None), after the fold only those newer than the run. The old bash had the same bug (its `touch -t` also failed for this). Only runs opened by old helpers can have a minute-only `opened:`.
- DIFF: `20261115103045` (no separators; stamp accepts, local_moment None), `...10:30:61` (stamp rolls to the next minute, local_moment None), `...+02:00` and `...10:30:45.123` (stamp None, local_moment takes the first 19 chars).  None of these is ever written by the helper.

User sees: `council check` on a just-me build opened with a minute-only `opened:` stops naming council references in untracked files that predate the run. Nothing else. Same on every platform (both use the local zone).

Pins: `tests/py/test_check_parts.py:115-117` (`stamp("2026-01-02 03:04:05")` and `stamp("not a time")` is None: these two lines would be re-pointed at `local_moment`), `evals/run_cli.py:5752` (sleep 1.1: files newer than opened) and `:5793` (earlier work not the build's). No other check.
Decisions: none (D23: `opened:` is a frozen state key; its format is unchanged).
Size: -17 lines (function) +1 at the call site (`m = clock.local_moment(opened)`, `m.timestamp() if m else None`); risk low. Already marked `needs_user` (`trim-commands.md:92`) because it drops the forms; with the owner's word that is settled.

---------------------------------------------------------------------------------------------------

## 6. `memory_tree._search` (the grep fallback)

### Chain (src/council/commands/memory_tree.py)

- `Tree.find(names)` :57: `git grep -h -o -w -F -f <names> --untracked -- . ":(exclude).council"` inside a repo, or `git grep --no-index ...` outside; if git's exit code is > 1 (git missing returns 127 via `git.run`, 128 on a git error) -> `_grep(["-r","-h","-o","-w","-F","-f",pat,"--exclude-dir=.git","--exclude-dir=.council","."], top)`.
- `Tree.find_in(names, files)` :72: always `_grep(["-H","-o","-w","-F","-f",pat,"--", <files>...])` in batches of 100 (no git grep).
- `_grep` :164: `grep` from PATH (`shutil.which`), else `_search`. `_search` :170 is the pure-Python version: reads each file, skips files with a NUL, finds each name as a whole word with `(?<![A-Za-z0-9_])name(?![A-Za-z0-9_])`.

Callers: `commands/memory_check.py:63-64` (`council memory check`) only. `Tree.orphans` and `line_counts` use `files`, not a search.

### When is `_search` reached

Only when `grep` is not on PATH. `git grep` itself does not fall to `_search`; it falls to system `grep -r` first (no git, git erroring: exit > 1). `find_in` has no git step, so with no grep it goes straight to `_search`. Git for Windows ships grep in `usr/bin`; the hooks and `bin/council` run under bash on every platform. In the supported environments `_search` is never reached. No eval removes grep from PATH: grep of `_search`, "no grep", `whole word` in evals/tests finds nothing about it (CLAUDE.md: every path needs a scenario; this one has none). The scenario for "outside git" is `evals/run_cli.py:1896` (git is present, so `git grep --no-index` runs).

### What differs (a6.py, a6b.py: names `a.b`, `a.b.c`, `foo`, `bar`, ...)

| Search | Result for the test tree |
|---|---|
| `git grep` (git repo) | `a.b.c`, `foo`, junk line `Binary file bin.dat matches` (counted as a "name"), honours `.gitignore` (did not find `ignored_name`), top-level `.council` excluded but `sub/.council/c` NOT excluded (found `nested_council_name`), nested `.git` not scanned |
| system `grep -r` | `a.b.c`, `foo`, `Binary file ./bin.dat matches`; ignores `.gitignore` (found `ignored_name`); excludes `.git` and `.council` at any depth (no nested names) |
| `_search` (pure Python) | `a.b` AND `a.b.c`, `foo`; skips binary files silently; no `.gitignore`; `_walk` excludes only the top-level `.git`/`.council` (found `nested_git_name`, `nested_council_name`, `ignored_name`) |

So the three paths give three different answers today. In `a.b.c` the two greps print only the longest match (leftmost-longest with `-o`), so name `a.b` is reported missing although `a.b` is a whole word there; Python reports both. A `Binary file ... matches` line is a junk name, and a name that appears ONLY in a binary file is lost by both greps (the Python search also skips it). In a UTF-8 locale GNU grep's `-w` also treats é as a word character; Python's `[A-Za-z0-9_]` does not (not testable here; the Git Bash grep here agreed with Python on `xéfoo`).

`find_in` differences are the same family (proved: grep lacks `a.txt:a.b`; Python has it).

### What a pure-Python search would change

Replace `find`, `find_in`, `_grep`, `_run`, `_search`, `_walk` use and the `_patterns` temp file with one search over `Tree.files` (which already is `git ls-files -co --exclude-standard`, minus `.council/`, or `_walk` outside git) using one compiled alternation regex (longest name first). Result: one answer for git and non-git trees, honours `.gitignore` in git trees (as `git grep` does now), no `Binary file` junk, `a.b` found inside `a.b.c`. About -55 lines in a 203-line file, +20. Speed: a measure on this tree (487 files, 3.9 MB, 110 names, a6c.py): `Tree.find` with git grep took 1.57 s (mostly process start-up on Windows), Python 0.88 s with the same 9 names found. A large repo will favour git grep (index, threads); I did not measure one. `Tree.files` also skips nothing by size: add a size cap if a repo has big generated files (that would be a visible change, so say it in CHANGELOG).
A git-only search is worse: it needs git (no-git trees go through `--no-index`, which a git-less machine lacks) and keeps the junk-line behaviour.
If the fallback is simply deleted with no replacement, a machine with no grep would report every `name in path` anchor stale (empty search output) — a false alarm, so give `_grep` a D19 refusal ("memory check needs grep") instead. I do not recommend that: option "pure Python" is cleaner.

Pins: `evals/run_cli.py:1699-1705, 1884-1919` (memory check: stale anchors, a.b/f()/path::name forms, outside git). These run with grep present, so they pin the grep path's answers (e.g. longest-match). Switching to Python must keep their expected output; the `a.b` inside `a.b.c` case is the one to look at. `evals/ratchet.json:327` holds `memory_tree.py` at 203 lines. Decisions: none (D32 stdlib only: fine; D24 new logic in Python: favours Python). Risk: medium (the code is small but the answers move in the edge cases above, and the only pins run through grep).

---------------------------------------------------------------------------------------------------

## 7. Readers of the 0.1/0.2 layouts

Searched `src/`, `bin/council`, `hooks/*.sh`. `bin/council` and the hooks (shell) have NO reader of any legacy layout; everything is in Python. (`hooks/session-start.sh` just runs `council run session-start`.)

### Group A: how 0.1/0.2 marked and shaped the open run

| # | Reader | file:line | On-disk shape that triggers it | Open run only? |
|---|---|---|---|---|
| A1 | SessionStart hook: the old pointer | `commands/session_start.py:258-300` `_active_run`, called :85 | `.council/active-run` non-empty; first line (CR cut) names a folder, relative to the repo root or absolute. Skipped when the folder is under `<home>/runs/` (the normal scan already reports it: eval `run_hook.py:395-397`, "reported once"). Acts when the folder is elsewhere (e.g. `.council/review-output/2026-09-07-1200`) and has a `session-state.md` whose `status:` is not `complete`/`abandoned` | Yes: only a run left OPEN in the old place. Says "UNFINISHED COUNCIL RUN" or, after a compaction, "Also open (an older run layout)", names `FINAL-*.md`/`PLAN-*.md` as "probably finished", infers the mode from `<mode>-output/` (":268-272") |
| A2 | `council run close` empties the pointer | `commands/run_close.py:71, 107-117` `_empty_pointer` | `active-run` first line names the run being closed (relative form joined to the repo root) | Open run, at close; also a CLOSED run's stale pointer stays if this goes (A1 then ignores it because status is complete; only A3 mentions it) |
| A3 | `council doctor` | `commands/doctor.py:21, 74, 217-234` `active_run` | `active-run` non-empty: warns "an older run is still marked open", "active-run still points at a closed run (empty it)", or "points at a folder that no longer exists" | Open or stale-closed pointer; read-only |
| A4 | `.gitignore` line | `records/ignores.py:14` `KEPT_OUT = ("runs/","asks/","active-run")`, used at :41-57; `run open` adds missing lines | the home's `.gitignore` lacks an `active-run` line | WRITER, not reader: `council run open` appends `active-run` to a home's `.gitignore`. Long-lived user file. |
| A5 | A 0.2 run with no `code-root:` | `agent_gate.py:140`, `cap.py:156`, `resolve.py:84,89`, `session_start.py:167`, `commands/runs.py:34` (`code_root in (tree, "", "-")`), `records/runs.py:42` | `session-state.md` without `code-root:` | Open run: counted as this tree's. (A closed run's listing too, but nothing acts on it.) Eval header `run_hook.py:17`. |
| A6 | Short mode names | `records/runs.py:79-86` `skill()` ("0.2 runs sometimes wrote the short name") | `mode: review` instead of `council-review` | Any run read through `skill`: open (resume, status) and closed (history of the run) |
| A7 | 0.1 council inside a worktree | `records/home.py:42-45` `home_from`: `main` has no `.council` but the linked worktree does -> use the worktree's | `.council/` exists only in a linked worktree | Long-lived: it decides WHERE the whole home is (config, memory, ledger). Not only for 0.1: it also serves a user who ran `council-init` inside a linked worktree. |
| A8 | Root-level memory | `records/memory.py:46-67` `locate`: `alt` = `home/conventions.md` or `<root>/conventions.md`; `views/status.py:196` (`root / "conventions.md"`) | memory file at the repo root instead of `.council/conventions.md` (and no usable config path) | Long-lived: the project's MEMORY. Remove and an old project's memory entries stop being served at run start (session-start `_memory`, `council memory`, doctor), silently. |

### What stops working if each reader goes

- A1 gone: a run left open under `<mode>-output/` (no `runs/` entry) gets no SessionStart line and no compaction line. It is invisible to everything else too (`runs.listing` scans `<home>/runs/` only), so the user would not be told it is unfinished; `council run close --run <folder>` still works if they know the folder (`resolve.is_run` needs only the state file, `resolve.py:76-78`). A pointer into `runs/` already works through the normal scan.
- A2 gone: a stale pointer is left naming a closed run; with A1/A3 gone nothing reads it. If A1 stays, it ignores a closed run's pointer. No loss.
- A3 gone: the three doctor warnings. I found NO eval for `doctor.active_run` (grep for "still marked open", "points at a closed", "no longer exists:" finds only the session-start line in `run_hook.py:547`). So it is unpinned.
- A4 gone: new homes get no `active-run` ignore line; existing lines stay. The written bytes change, so `run_cli.py:5914-5970` and `tests/py/test_ignores.py:23-38` change (they pin `runs/\nasks/\nactive-run\n`). A home that still has an `active-run` FILE would show it as untracked in a team repo. Also the doctor text "covers runs/ and asks/" (`run_cli.py:5958-5970`) is unaffected.
- A5 gone: a run with no `code-root:` would no longer count as this tree's open run; `cap check`, `resolve`, SessionStart would skip it. Only 0.2 runs lack it. (Pre-0.3 runs.)
- A6 gone: `mode: review` maps to `context-core`.
- A7 gone: a project whose only `.council/` sits in a linked worktree loses its config/memory/ledger there (council would see "no home" in that worktree and use the main checkout's). Pinned by `tests/py/test_paths.py:112-120`.
- A8 gone: see above; `doctor_memory` today even warns when both exist (`doctor_memory.py:60`).

### Group B (not 0.1/0.2; these are 0.14-0.21 shapes; D26 and D8 are involved)

- No `plan-schema:` -> "legacy run": no run plan needed (`plan.py:17-24, 54`, `agent_gate.py:221-283 Planned.legacy`, `cap.py:83,124`, `records/state.py:52`, `doctor.py:186`). Open runs only. `run_cli.py:725-732`.
- No `events-schema:`/no `events.tsv` -> no event stream (`events.py:136,198`, `run_events.py:61`, `closing.py:22`, `audit_checks.py:104,140,178`). Open AND closed runs (audit of a closed run says "no event stream"). `tests/py/test_events.py:155`.
- Seat rows without the accounting columns -> basis "older" (`usage.py:26-54`, `usage_gaps.py`, `views/status_usage.py:38`; word frozen by D26). Closed runs too. `ledger.py:133` text "0.14+ or corrected" (ledger.tsv is long-lived).
- D40: `tuning.md` is read by nothing already (gone).

Other evals/tests for group A: `evals/run_hook.py:17-18` (header), `:391-397` (0.2 run, pointer into runs/), `:559-590` (legacy: no status line, CRLF, `<mode>-output`, mode inferred, "never claims an old one after a compaction", build log vs `FINAL-*.md`), `evals/run_cli.py:3329-3332` (close empties the pointer), `:5908` (a "0.1 layout" home gets the ignore lines), `tests/py/test_ignores.py`, `tests/py/test_paths.py:112-120`.

Contract: `active-run` is a file name in the council home (architecture §4 lists the home's files but not `active-run`; §6 "the council home's file and folder names (§4)" and D23 freeze listed names; `active-run` is not in §4, so removing the readers is not a rename — but its ignore line is written into user files (A4), so remove that last, with a CHANGELOG line). `docs/design/doctrine-0.3.md:384,531` and `skills/council-init/SKILL.md:188` ("`active-run`, for older runs") name it in prose.

Suggested order if the owner says go: A3 (unpinned doctor) and A2 are free; A1 plus its eval block (run_hook 559-590) is the real loss and needs the owner's word that a 0.1/0.2 run left open is not worth a banner; A5/A6/A7/A8 are NOT layout-only (A7 and A8 serve current users): keep unless asked.

---------------------------------------------------------------------------------------------------

## 8. Other things of the same kind

1. **More than two torn-line appenders.** "Never join a torn line" is done in `paths.append_row`, `agent_gate._append_start`, `records/ignores.py:51-54` (`lead = cr+"\n"` if the file lacks a final newline, CR style copied from the file) and `commands/sharing.py:164-168` (same with `cr`). Writers with NO torn-line guard: `records/seat_write.py:23` (`add`: header when empty, rows appended; used for seats.tsv/usage.tsv), `records/events.py:121` (row appended after `_next_seq`), `commands/correct.py:101` (corrections.jsonl), `commands/index.py:83`. `seat_write.add` and `events._write` could use `append_row` semantics for the TSV ones; ignores/sharing are text with CR matching (a different job). Decision D (architecture §8 "Write a shared TSV row ... never join a torn line") says it for TSV rows.
2. **CR handling "Git Bash's awk reads in text mode", done five ways, Windows only** (each says `os.name == "nt"`): `records/bytewise.py:43` (`records(fold=True)`: `\r\n` -> `\n` once), `commands/hygiene.py:76` (`_file_lines`: cut ONE final CR per line, bytes), `commands/index.py:29` (same cut, on str), `commands/run_events.py:50` (`replace("\r\n","\n")` on a whole file), `commands/gate_failed.py:63` (cut a final CR on output), plus `run_open.py:107` (template CRLF -> LF). Proved (a8.py): `"a\r\nb\rc\r"` -> bytewise `['a','b\rc\r']`, index `['a','b\rc']`; on Windows the three disagree on a bare CR. The question for the owner: strip CR on all platforms or none. macOS/Linux read CRLF files with the CR kept today, Windows without it: the same file prints differently. Pins: run_cli reports/runs, `test_cells`, `test_listing`; `trim-records` skipped it.
3. **Windows test done two ways**: `commands/gate_run.py:26` `WINDOWS_BASH = os.name == "nt" or sys.platform.startswith(("cygwin","msys"))` against `os.name == "nt"` at `gate_exec.py:51,117,151`, `owners.py`, `paths.py:52`, `home.py`, `bytewise.py` and 6 more. Under a Cygwin/MSYS2 Python (`os.name` is `posix`) only `gate_run` treats it as Windows. `bin/council:15` uses a third test (`/proc/$$/winpid`). A single `records/paths` constant would serve; D34 pins the launcher's own test (it must run before Python).
4. **Drive-letter conversions**, six copies (item 4 neighbours): `home.native`, `cite_check.rel`, `memory_select`, `commands/home.rule`, `session_start:67`, `bin/council:18`. They convert in different directions; not one fold.
5. **Directly-written whole files beside `atomic_write`**: `check.py:47`, `patches.py:67-75`, `run_open.py:128`, `index.py:57`, `nudges.py:56`, `sharing.py:114,208` use `write_bytes` (non-atomic, truncates first). They are single-writer scratch or new files; flagging only. `ask.py:160` opens `r+b` in place.
6. **Two grep users**: `index_symbols._grep` (`index_symbols.py:97`, `git grep` only, no fallback, 80-search budget) beside `memory_tree` (item 6). `index_symbols` simply returns [] when git fails; a different policy.
7. `memory_tree._patterns` and `git.files_tree` both call `tempfile.mkstemp` directly (patterns file; index copy). Different jobs, no overlap with `atomic_write`.

---------------------------------------------------------------------------------------------------

## Should anything NOT be done

- Do not replace `hygiene.stamp` by `os.utime` (wrong tool); use `clock.local_moment`.
- Do not drop `keep_mode` when folding `replace` (the state file would become 0600).
- Do not use `os.path.isabs`/`Path.is_absolute` as the one helper (answer depends on OS and Python 3.13 vs older).
- Do not touch the `/c/x` fast path or `pwd -W` in `bin/council` and `home.native`; no second cygpath exists to fold.
- Do not remove A5-A8 (items 7) as "legacy": A7 and A8 move where a current user's home and memory are found; A5 only matters for a 0.2 run.
- Folding `_append_start` must keep the `try/except OSError` (D20); with `append_row` raising, an unwritable starts file would otherwise block an agent start.
- Do not delete `_search` without a replacement or a D19 refusal: with no grep the anchors would all read stale.
