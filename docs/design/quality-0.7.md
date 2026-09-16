# 0.7 — proof instead of opinion

*Written 2026-09-16, before the build. Design panel: 7 agents (2 scouts, 4 designs, 1 judge); then a
review of 8 agents (80 findings) and an adversarial re-check of 2 (9 more). 17 agents in all, never
more than 8 at once.*

## The question

The author is not a programmer: they cannot read a diff, cannot debug, and cannot judge the code the
council writes for them. "How do we get senior-level quality, or close to it, without spaghetti and
loopholes?" Quality has to arrive through things that don't require reading code.

## What was already true

Four layers here can't be talked around by any model, because a shell script decides them: the
project's own gate commands judged on exit code; `council collect` proving each seat wrote its file
and opened its reference doc; `council check` proving every citation resolves; and the SubagentStop
hook refusing a malformed seat file. On top sits the blind verifier. That is already past "one model
marking its own homework".

## The hole

**The strongest layer only ran commands the project already had.** With none configured,
`council gate --all` printed "no gates configured" and returned 0 — so the baseline passed, every task
passed, the final check passed, and the report read clean while nothing whatsoever was checked. On a
fresh project the plugin quietly degraded into pure opinion and never said so.

## What shipped

1. **Nothing checked is never a pass.** `gate --all` exits 4 with `NOTHING WAS CHECKED` when no gate is
   configured, none runs at the requested stage, or every one was skipped; the verdict line now names
   pass, FAIL and skipped counts (a skipped *required* gate is named, so "all pass · 2 skipped" can't
   hide a suite that never ran); `doctor` treats a config with no gates as an error, unless the user
   declined the offer, which it records; a mode that **changed code** carries a `Checked by machine:`
   line — a plan or a research run doesn't, because an alarm on every run is an alarm nobody reads;
   council-implement asks one question when the baseline is red or empty, records the answer in the
   user's words, and keeps one clause on the receipt until it goes green.
   council-init lists the five checks a project is missing and, on a yes, writes a guardrails plan for
   council-implement to build — it installs nothing itself, so every install gets evidence, a verifier
   and a log row. `references/guardrails.md` holds the per-stack commands and the ratchet.
2. **The receipt.** Six fixed lines after every build, including `Shortcuts I took:` and `Not proved:`,
   where `none` and `nothing` are answers and silence isn't, backed by an enumerated definition of a
   shortcut and a tracked `## Shortcuts and concessions` section in the log that `run close` checks for.
3. **Every fix leaves a test behind.** Before-evidence is a test in the project's suite whenever there
   is a runner; `council check` reads the saved before/after verdicts and reports, per task, whether
   the before-check really failed, whether the after-check really passed, whether the after-check was
   the same command, and whether a real test file was left in the project (one the build just wrote
   counts, before it is committed — a source file or a config file never does). The converge table
   gains a Proof column.

Plus one bug found on the way: the permission rule council-init offered, `Bash(council *)`, also
covered `council gate <name> -- '<any command>'`, which runs through `bash -c` — an allowlist for every
command on the machine. It is now a list of bookkeeping subcommands; gates ask every time.

## The ratchet — why a new check judges only what changed

Fitting a linter to an existing project whole-tree prints hundreds of complaints about code that was
already there, and it gets switched off in week one. Changed-files-only is green on day one and can
only get stricter; the pre-existing count is written down once as "not yours", never as a task list.

The first draft expressed this as `git diff --name-only <base>...HEAD | xargs -r <tool>` written into a
config cell, and the review took it apart: the pipe shifted the Gates row so the gate never ran again;
the diff was blind to the uncommitted work the council had just written; `-r` is GNU-only, so every
fitted gate was permanently red on macOS; paths with spaces and files deleted in the range produced red
gates no code change could fix. It is now a helper verb, `council changed`, tested like everything else
the helper does.

## Deliberately not built

- **Structural metrics** (file length, nesting depth, duplication, import cycles) — ~250 lines of
  fragile new code in a helper that is already long, two of the four measures are proxies that misfire
  on generated code and data tables, and once a real linter and type checker are installed most of what
  they'd catch is caught by a tool that understands the language. What survives is numbers a non-coder
  can't act on.
- **A health dashboard or `council health` trend** — read twice, then never again.
- **A pre-commit hook** — closes a real hole (the council only sees what is routed through it), but a
  blocked commit the author can't read is worse than an unchecked one. Revisit in 0.8, after the fitted
  checks have proved quiet for a release.
- **Launching the app as proof** — the biggest remaining trust gap, and the least portable thing there
  is: it can hang, need a database or secrets, or not exist at all for a library. It survives as the
  receipt's `Works?` line, where "nobody ran it" is a first-class answer.
- **A coverage gate** — the most gameable number in software; 90% of mock theatre reads greener than an
  honest 30%.
- **A separate `/council-guardrails` mode** — nothing here runs automatically, so a tenth thing to
  remember is a tenth thing nobody runs. It belongs in council-init, which already runs once per repo.
- **Installing anything without a yes**, and auto-invoking test-architect from the build path.

## The ceiling, stated plainly

No process turns an agent into a senior engineer. What 0.7 reaches is a careful mid-level engineer who
never tires, never skips the checklist and never lies about what was checked: code that compiles,
type-checks, passes a linter and a dependency scan on every change, bugs that stay fixed because each
leaves a test, and a written record of every shortcut. Taste about what not to build still isn't in the
box.

## Open questions

- **Does the receipt stay honest?** A builder can write "none" reflexively. The enumerated definition,
  the close-time check and the oddness of two months of "none" are the mitigations; drill D26 is the
  test.
- **Saved-test detection is crude.** `pytest tests/test_x.py` is recognised, `npm test -- -t "expired
  token"` isn't, so a real saved test can be reported as unconfirmed. It under-claims on purpose, and
  the wording says "couldn't confirm" rather than "no test".
- **The ratchet's base.** `council changed` falls back to the merge-base with the default branch, and
  on a trunk-only repo that leaves only the uncommitted work — right during a build, thin right after
  a commit. Watch what real projects do with it.
- **A check that matched nothing.** A ratcheted gate on a clean tree passes having looked at no files.
  The helper now says so on the gate line and in the verdict tail, but "pass — nothing to check"
  appearing after every commit may yet become its own wallpaper. Watch it.
- **Two known under-claims in the saved-test check**, both deliberate: a test path with a space in it
  is word-split out of the command and reported as "couldn't confirm"; and a filename git has to quote
  (a quote, a backslash or a newline in the name — Linux and macOS only) is dropped from
  `council changed`'s list without a word. Both fail towards silence rather than a false green.
- **Names, not counts.** `council changed` decides what a file is by its path. A test suite that lives
  somewhere unconventional (`t/`, `features/`) will be missed by the saved-test check, which
  under-claims rather than lies, but says "couldn't confirm" more often than it should.
