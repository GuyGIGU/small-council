# evals/

Four automated layers, an advisory one, and hand-run drills. A skill isn't done until it's tested.

## 1. Validation — will the plugin load?

```bash
python scripts/quick_validate.py
```

Checks:
- the plugin and marketplace manifests;
- every skill's and agent's frontmatter;
- hook commands pointing at real scripts;
- every `${CLAUDE_PLUGIN_ROOT}/…` and `references/…` path a skill names existing on disk;
- the helper and hook scripts being bash with LF endings;
- the ten stage doctrine files;
- seat docs opening with the `# Title` that workers echo, and numbering principles "Principle N";
- the helper and hook scripts tracked in git as executable.

## 2. Structural evals — is the design intact? (blocking)

```bash
python evals/run_structural.py
```

Checks:
- the kernel's eleven laws and its stage index;
- each stage's doctrine handing off to the next;
- every `council …` command a text mentions existing in the helper;
- the modes' `## At <Stage>` sections and deliverable paths;
- the agents' contracts and the hooks' wiring;
- the templates' schemas and the catalog;
- size budgets that keep skills whole after compaction;
- bash 3.2 portability;
- the rename;
- version agreement across plugin.json, the CHANGELOG and the helper.

## 3. Helper evals — does `bin/council` do its job?

```bash
python evals/run_cli.py        # needs bash + git
```

Runs the helper against scaffolded git repos:
- the council home, from the main checkout, a worktree, and outside git;
- opening, updating and closing runs: a second in-progress run refused without `--alongside`,
  commands that never guess between runs, paused runs, session ids, init creating the home;
- the change index: files, symbols (code only), callers, tests;
- gates judged by exit code (optional vs mandatory), with commands passed intact;
- seat-file collection: `ref:` proof of reading (paired seats too), item caps, broken citations,
  empty or unreadable indexes, failed and re-dispatched workers;
- citation and origin checks (introduced vs pre-existing);
- map status and the drift doctor.

## 4. Hook evals — do the hooks behave?

```bash
python evals/run_hook.py       # needs bash + git
```

**SessionStart:**
- silent outside council projects;
- orients council projects;
- finds several open runs by scanning;
- after a compaction, says "resume, don't restart" for this session's run only;
- handles paused runs, runs in other worktrees, legacy runs, stale maps and garbage input.

**SubagentStop seat check:**
- valid files pass;
- a missing, malformed, empty or oversized file is blocked, but only once;
- other agents are never touched.

## 5. Phrase checks — advisory

```bash
python evals/run_phrases.py
```

Looks for the wording of the field-tested rules and warns if one is missing. It never fails: a
reworded rule shouldn't break the build, and a phrase proves nothing about behaviour.

## 6. Behavioral drills — run in Claude Code

See `behavioral-drills.md` (D1–D14). They need a live agent and subagents, so they can't be scripted
here. `fixtures/` holds the seeds for D3, D4 and D9.
