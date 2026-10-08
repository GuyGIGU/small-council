# Sharing — the team's council, or just me

The council belongs either to the team or to the user alone. Nobody else installs or uses anything
either way: the plugin, its hooks and its agents live in the user's own Claude Code. The choice
covers only what the council leaves in the shared project.

| | Team (the default) | Just me |
|---|---|---|
| `.council/` (config, memory, map, plans, reviews, logs) | committed with the project | ignored by git through its own exclude list (`.git/info/exclude`), which is never committed or pushed |
| CLAUDE.md / AGENTS.md | a Small Council note points every session at the council | no note |
| `.claude/settings.local.json` (the permission rules setup offers) | personal either way | ignored through the same exclude list, unless git already ignores it |
| Commit messages, PR text, code comments, shared docs | may cite the council's files | never cite council runs, finding ids or `.council/` paths, because teammates can't open them; say the reason in plain words |
| Specs and test specs | `specs/` in the project | `.council/specs/`; the user moves one into the project to share it |

The config records the choice under `## Run preferences`: `- sharing: team` or `- sharing: just me`.
A config with no such line is a team council, which is what every version before 0.19 kept.

## When setup asks

Ask when other people commit here (`git log --since=12.months --format=%ae | sort -u` lists more than
the user), or when the user says the project is shared:

> Just me — the council stays on your machine and teammates never see it — or team, committed with
> the project?

On a solo repo, say "team" in one line. A user who asked for a private council has already answered.

## The helper

- `council sharing` shows the choice. On just me it lists what is done and what is left, each with
  its fix. `council doctor` warns about the same things.
- `council sharing just-me`:
  - adds the council's lines to git's exclude list, as a marked block;
  - takes the Small Council note out of CLAUDE.md and AGENTS.md (in the main checkout and in this
    working tree), keeping every other line;
  - removes a file that held only the note;
  - writes `- sharing: just me` into the config.

  Running it twice changes nothing.
- `council sharing team` takes the block out again and writes `- sharing: team`. Committing
  `.council/` and writing the note back (council-init, Phase F step 1) come next.

**Files already in git stay there.** Git keeps tracking a file even once it is ignored. Taking the
council's files out of the shared project means `git rm -r --cached .council` and a commit, which
teammates will see. The helper prints that command; pass it on to the user, and never run it yourself.
The same goes for a note that was committed: removing it is a change the user commits.

The session-start hook orients the user's own sessions on either setting. On just me it also prints
the rule about commit messages and shared docs, so the missing CLAUDE.md note costs nothing.

**`council check` holds the rule on just me.** It reads the lines the change adds since the run's base
(new untracked files whole), the commit messages since that base, and a PR body drafted for the run as
`<run>/pr-body.md`. Each council reference it finds is a failure line with its place: a `.council/`
path, a run folder's name, `ruling <n>`, `verify-<n>`, and — in comments and prose only, where code
can't mean them — a D-, F-, AP- or EC- id and a task named as the council names it, "(task 4)". A
real build left "(ruling 1)" in a code comment. Say the reason in plain words instead. Draft a PR
body in that file before it goes anywhere, so the check reads it first.
