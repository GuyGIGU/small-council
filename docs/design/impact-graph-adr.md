# ADR: bounded run-local impact graph

## Problem

The change index names changed files and gives heuristic callers/tests, but downstream tools need
structured evidence that distinguishes a changed path from a directly affected consumer. A
repository-wide call graph would be costly and language-dependent.

## Constraints

- Keep the existing Bash/Git index and old runs working without Python.
- Include committed and working-tree changes, renames and deletions.
- Never present a text match as proven runtime or test coverage.
- Bound repository scanning and preserve a stable, inspectable artifact.

## Options

1. Keep Markdown only. Smallest change, but later context/routing phases would have to parse prose.
2. Require Tree-sitter/LSP or a graph database. Richer analysis, but new setup and uneven language
   support would make ordinary runs fragile.
3. Add a run-local TSV graph with optional standard-library Python and narrow static providers.

## Decision

Choose option 3. The Git delta is the source of changed paths. Python AST resolves static imports
and enclosing definitions; a bounded JS/TS lexical provider resolves literal relative imports and
nearby declarations. The graph records direct dependencies, reverse importers, test hints, surfaces
and provider limits with confidence labels. `council index` refreshes it when Python is available;
the existing index succeeds independently.

## Tradeoffs

The artifact is deterministic and cheap enough for a run, but incomplete by design. A reverse
import is a potential impact edge, not proof of execution. Large repositories and dynamic language
features can leave gaps; the graph exposes its scan limits rather than silently claiming coverage.

## Alternatives rejected

Do not introduce mandatory parsers, network services, a database or automatic seat/verification
selection in this phase. Those would conflate evidence gathering with routing and add setup cost
before representative outcome benchmarks exist.

## Revisit when

Real project fixtures show missing high-value dependencies, or benchmarks justify an optional
Tree-sitter/LSP provider. Preserve the v1 row meaning and version any incompatible change.
