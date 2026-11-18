# Contributing to Small Council

Thanks for wanting to extend the council. Every part of the design has one owner; read this before
you change anything.

## Who owns what

- **The kernel and the stage doctrine own the method.** `skills/context-core/SKILL.md` holds the laws,
  the stage index, the helper table, the file layout, the limits and resume. `references/doctrine/`
  holds one file per stage. Improvements to *how work is handled* go there, once, and every mode
  inherits them.
- **Modes are thin.** A mode invokes `context-core` and adds only its specifics, under
  `## At <Stage>` headings named after real stages: target resolution, the per-item format, owner
  rules, the deliverable. Copy `skills/council-review/SKILL.md` for shape, brevity and voice.
- **The helper does the mechanics.** If a step can be done or checked by a script — opening and
  closing runs, gates, the change index, checking seat files or citations — it belongs in the
  helper (`src/council/commands/`), not in prose the model has to remember.
- **The agents carry the contracts.** The seat worker's rules live in `agents/council-worker.md`, the
  verifier's in `agents/council-verifier.md`, the builder's in `agents/council-builder.md`. Dispatch
  messages point at the brief and never restate a contract. A step of the build loop goes in
  `references/run/builder-loop.md`, which the builder follows, not in council-implement.
- **The hooks enforce what prose can't.** SessionStart handles orientation and resume, and marks the
  session so `council run open` can tell its hooks run; PreToolUse stops new agents at a run's limit
  and refuses a council command piped into head, tail or grep (that Bash hook marks the session too);
  SubagentStop checks the seat file.

If you find yourself writing map, dispatch or aggregate logic inside a mode, stop: it belongs in the
doctrine or the helper.

## Adding a mode

1. Create `skills/<mode>/SKILL.md`.
   - Frontmatter: `name` equal to the folder (kebab-case).
   - `description`: at most 600 characters, key use case first. If the mode fans out, it says to
     propose the run with its size and cost.
2. Invoke `context-core`, then add `## At <Stage>` sections only where the mode differs. Name a tracked
   deliverable path under `<home>/`, and give a per-item format that starts with an index line:
   `<n> · <severity> · <principle> · <path:line> · <title>`.
3. Write reference docs as `${CLAUDE_PLUGIN_ROOT}/references/<file>.md`, never as a bare relative path
   a worker can't open.
4. Keep the file whole after compaction: at most 20,000 characters and 500 lines.
5. Keep it generic. No specific project's stack, seats or commands; those come from the project's
   config.
6. Add its invariants to `evals/run_structural.py` and a drill to `evals/behavioral-drills.md`.

## Changing the stage doctrine

- **Title and hand-off.** Each file's first line is `# Stage N — <name>`. Each ends with its hand-off:
  `council state phase=<next stage>`.
- **Size.** Stay under 6,000 characters. The Chair reads the file when it enters the stage, so every
  line competes for attention.
- **Commands.** Name helper commands in backticks. The structural eval checks that each one exists.

## Changing the helper

- **Every command is Python** ([decision D24](docs/decisions.md)): a module in `src/council/commands/`
  with its row in `dispatch.COMMANDS`, reading run files through `src/council/records/`.
  `bin/council` only finds a Python and starts it; it takes no command logic.
  [`docs/architecture.md`](docs/architecture.md) says where new code goes and the one way each
  recurring job is done.
- **The bash that stays** (the launcher and the hooks) is bash 3.2 compatible — macOS ships it. No
  associative arrays, no `mapfile`, no `${var,,}`; paths go to awk through `ENVIRON`, never `-v`,
  which eats the backslashes in Windows paths.
- **Short, plain output**, meant for the Chair to read. A refusal is `cli.Refusal`: stderr, exit
  code 2, and the next step named (D19). A gate returns its own exit code.
- **Every command is covered in `evals/run_cli.py`** (or a hook's path in `evals/run_hook.py`).

## Adding a seat

Seats live in `references/roster/expert-catalog.md`, not in skills.
- Add a row: practitioner, slug, lens, reference doc, "applies when", and the recast/drop rule.
- Add the doc under `references/`:
  - its first line is a single `# Title` (workers echo it as proof of reading);
  - its principles are numbered `Principle 1…N`. P1–P3 are severities, and the two must never look
    alike;
  - it has an `## Applying this seat to another stack` section.
- Add the doc to `SEAT_DOCS` in `scripts/quick_validate.py` and update the seat count in
  `evals/run_structural.py`.
- John Carmack chairs; he is never a seat.

## Running the gates

```bash
python scripts/quick_validate.py   # will it load?
python evals/run_structural.py     # is the design intact?
python evals/run_ratchet.py        # did a size or structure number go up?
python evals/run_cli.py            # does the helper work?   (bash + git)
python evals/run_hook.py           # do the hooks behave?    (bash + git)
python evals/run_phrases.py        # advisory wording checks — never fails
python evals/run_all.py --fast     # the fast tier, about a minute: a first look while you work
python evals/run_all.py            # every suite CI runs, several at a time, then a summary
```

These are selected local checks. [CI](.github/workflows/ci.yml) runs, on Ubuntu, Windows and macOS,
ruff with [`ruff.toml`](ruff.toml) on the whole tree, the ratchet, the fast tier, and then every suite
with `evals/run_all.py`; [evals/README.md](evals/README.md) lists them. A new `evals/run_*.py` goes
into `run_all.py`'s list. Automatic checks do not replace real-use validation.

**The fast tier** (`--fast`; `--list` marks its jobs) is validation, the structural evals, the
ratchet and its self-test, the unit tests in `tests/py/` and the quickest scenario suites. It is a
first look. Run it and the groups your change touches before you push; CI's full run on all three
systems is the gate before merge.

**The ratchet** (`evals/run_ratchet.py`, baseline `evals/ratchet.json`) measures `bin/council`,
`hooks/*.sh`, `scripts/*.py` and `src/**/*.py`: each file's lines and longest function, its ShellCheck
warnings (only where `shellcheck` is on PATH; otherwise reported as skipped), the files outside
`src/council/records/` that parse a council file, the `council.config.md` readers outside one
`configured_*` reader, and the scripts that run `bin/council` back. A number may only go down; a
regression is one line naming the file, the measure, the baseline and the new value. A Python file
the baseline doesn't list is held to 60-line functions and 500-line modules; so is every file in
`src/council/`, which may grow up to those limits rather than being frozen at its size.
`bin/council`, the hooks and `scripts/` stay frozen. Any
import outside the standard library in `scripts/` or `src/` fails (D32). Run `python evals/run_ratchet.py --update`
in the branch that lowers a number, so every later branch inherits the gain; it refuses to raise
one, so a limit is never loosened by hand. `--show` prints the files each count names.

**ruff** is pinned in CI with ShellCheck, since the baseline and the rule set are fitted to those
versions. `ruff.toml` turns on the widest set today's Python passes, and a stricter one for
`src/council/` and `tests/py/`. To widen it, fix a rule's last failures and delete it from its list.

**Releasing.** What a user installs is the `release` branch, never this tree (D45).
`scripts/build_release.py` writes the files that run (its `SHIPPED` list says which, and why);
`scripts/publish_release.py <remote> <branch>` builds that tree from a clean checkout, runs
`evals/run_release.py` on it, and only if the eval passes commits it to the branch. It refuses a
version that is not newer than the branch's (an installed copy updates only when `version` rises)
and does nothing when the branch already holds the same tree. main's marketplace entry names
`release`, so the branch must exist before main does.
1. Bump `version` in `.claude-plugin/plugin.json` — installed users only get an update when it
   changes.
2. Bump `COUNCIL_VERSION` in `src/council/commands/help.py`.
3. Add the matching `CHANGELOG.md` entry. An eval checks that all three agree.
4. Run the behavioral drills and, with the Claude Code CLI, `claude plugin validate <folder> --strict`
   on a tree the script built (on the checkout it fails over the root `CLAUDE.md`, which doesn't ship).
5. Before the merge, check that `release` exists on GitHub and holds the version being released or
   the one before (`git fetch origin release && git show FETCH_HEAD:.claude-plugin/plugin.json`).
   If it doesn't (the first release), publish it now, by hand, from the release commit (below).
6. After green CI and owner approval, merge with a merge commit only; do not squash or rebase.
7. Create an annotated `vX.Y.Z` tag on that merge commit and push it with owner approval.
   `.github/workflows/release.yml` checks the tag is the version and runs
   `python scripts/publish_release.py origin release`. Check that it passed: it says what it
   published, or that `release` already holds this tree.
8. Fast-forward the live main folder only after green CI and owner approval; verify it matches the tested tree.
9. GitHub Release objects are optional.

**Publishing by hand** (step 5, or when the workflow can't run), in Git Bash with Python 3.8+ and
git on PATH, from a checkout of the commit to release whose shipped files have no uncommitted changes
(the build refuses them):

```bash
git checkout <the release commit>      # a normal checkout: the tag, or the PR's last commit
python scripts/publish_release.py origin release
```

That one command is the whole publish. It stops at the first step that fails, with nothing pushed:
a build refused, a release eval that fails, a tree that changed after the build, or a version not
newer than `release`'s. It writes nothing into this checkout's `.git`; it pushes with your own git
credentials, never forced. A later tag's workflow, finding the same tree, adds nothing.

**Running the plugin from a clone.** main's marketplace entry installs the published `release`
branch, so adding a clone as a marketplace gives you the release, not your checkout. Build your
checkout's tree instead (`python scripts/build_release.py --worktree <folder>`, edits included): it
carries its own `marketplace.json` with `"source": "./"`, so `claude plugin marketplace add <folder>`,
then `claude plugin install small-council@small-council`, installs exactly what a user would get. Its
marketplace is named `small-council` too: `claude plugin marketplace remove small-council` first.
An installed copy changes only when `version` does; to try new edits, build a new folder and add
it again.

## The rule

**No change ships without green evals.** A new or changed mode also needs its behavioral drills run by
hand at least once. A green build with a mode that has never actually run is not done.

## Style

- **Generic.** Skills, doctrine, agents, hooks, the helper and references stay stack-agnostic. A
  specific project's config belongs only under `examples/`.
- **Plain language** in anything shown to the user, with no invented jargon. Say what a seat checks
  before its name.
- **Simplest wiring.** Choose the simplest design that works. A thin mode and a small script are
  easier to keep correct than clever prose.
