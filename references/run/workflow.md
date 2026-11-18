# Seats run through the Workflow tool

Read this when you plan a seat to run through the Workflow tool instead of the Agent tool (Assign),
and again when you dispatch it (Work, or Challenge for verifiers). The stage doctrine holds as it is;
these are the rules only a Workflow adds.

## Assign

A seat you will run as a Workflow counts every agent it starts — give it `budget/<slug>/agent-runs`
in the plan. Give each of its agents a group of small, same-kind parts (files, tasks, items), never
one small part each.

## Work

- If dispatching through Workflow, pass a seat's `seat/<slug>/model` value to its `agent()` call.
- **Whatever dispatches the workers** (Agent tool, Workflow, background agents), the file contract
  holds: one file per seat in `seats/`. The seat-check hook covers only
  `council-worker` and `council-verifier` agents, never a Workflow's (their type is
  `workflow-subagent`), so give a Workflow's agents the worker's file rules in their prompt;
  `council collect` then checks every file in `seats/`, named in the brief or not.
- A Workflow's notification is recorded with `agents=<agent_count>` (Work, While they work).

## Challenge

A Workflow of verifiers is one seat `verify-<n>` recorded with `agents=N`, and planned with
`budget/verify-<n>/agent-runs` — each of its agents counts against the cap, and takes items the same
way a verifier does (Challenge, step 2). Where each agent writes its file, and why the files are
never merged: Challenge, step 2. The seat-check hook never sees a Workflow's agents: give them the
file rules in their prompt (line 1 `# Verification — <run title>`, the verdict table, under 16 KB;
write the file first).
