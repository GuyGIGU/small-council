# examples/

Illustrative outputs of `council-init` — what the `.council/council.config.md` it writes looks like for
a given kind of repo, in the current template's schema. They show how seats get recast and how gates
are detected and dry-run. They are not live configuration, and nothing in `skills/`, `agents/`, or
`references/` depends on them.

- `chrollo/council.config.md` — a deterministic numerical Python service with a FastAPI backend and a
  small React UI: five recast seats, a regression-harness gate, and memory kept at a legacy root path.
