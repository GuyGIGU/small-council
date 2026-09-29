# ADR: opt-in model routing for mapping and survey seats

## Decision

Record an optional `seat/<slug>/model` choice in the run plan: `inherit`, `sonnet`, or `haiku`.
Missing rows mean `inherit`. Overrides are rejected unless `council.config.md` says
`- seat models: on`. Only selected worker seats may use an override; the Chair and verifier stay on
`inherit`. Assign/Work limits the choice to mapping and survey workers. Routing is off by default.

When dispatching, the Chair passes an override as the Agent call's per-invocation `model` parameter.
Claude Code documents that this parameter takes precedence over agent frontmatter and the
`CLAUDE_CODE_SUBAGENT_MODEL` setting; a force setting can still override it. An `inherit` choice uses
the conversation model. See [Claude Code subagent model selection](https://code.claude.com/docs/en/sub-agents#choose-a-model).

## Rationale and limits

Mapping and survey are the initial candidates because they gather and organize evidence. Judgment
and verification retain the conversation model. The dispatch prompt remains the operational handoff;
the plan records what was requested so history can group exact recorded tokens by planned model.

Token counts are not money and do not have a common price across models. For `inherit`, history cannot
know which actual model was used. A plan choice also cannot prove the host honored it. There is no paid
quality benchmark: future evidence is indirect, from later finding outcomes and verifier refutations,
and is weak evidence. Keep routing disabled until the owner chooses to enable it.

## Consequences

- Existing plans stay valid; no model row means `inherit`.
- History reports planned-model token totals alongside a plain caveat, not comparative cost savings.
- No per-seat model is hard-coded in the worker or verifier agent definitions, because the choice is
  run-specific.
