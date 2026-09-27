# ADR: bounded, seat-specific context packs

## Problem

The shared brief is authoritative, but sending every worker the whole change index and impact
graph repeats unrelated material. The run plan already chooses a context level per selected seat;
until now that choice did not produce an inspectable artifact.

## Constraints

- Never replace the user's stable `CLAUDE.md` or the Chair's `brief.md`.
- Keep the worker's objective, references, request pointer and hard constraints visible at every level.
- Use the seat's explicit slice and evidence-labelled impact edges, not autonomous routing.
- Work without the optional impact graph and without a network service or new dependency.
- Make reductions and omissions inspectable; reject expansion paths outside the code root.

## Decision

Build one run-local Markdown pack per selected seat, at the plan's `minimal`, `focused` or `full`
level. The pack draws shared essentials and that seat's block from `brief.md`, then ranks bounded
index and impact entries by slice relevance. Explicit expansion adds a requested path without
changing the plan's routing or any source artifact. A deterministic metrics sidecar records input
and output byte counts, reduction and path selection/omission. This is an optional *delivery aid*:
the brief, source files and graph remain available for the worker to inspect.

## Measurement

Input-to-pack byte reduction is a reproducible context-volume proxy, not a token-cost claim.
Focused fixtures also test retention of the assigned path, linked importer/test and a critical
constraint while excluding another seat's unrelated details. Those checks are outcome *proxies*,
not proof of better real-world findings. Actual finding quality, missed issues and agent cost need
paired runs on representative repositories before adaptive depth or savings claims are justified.

## Tradeoffs

Slice globs and direct import edges are incomplete. A small pack can omit an unexpected but useful
relationship; workers can expand a path or inspect the authoritative files. The metrics describe
what was included, not whether the worker understood or used it. A reproducible pack is preferable
to an opaque summary that silently invents context.

## Revisit when

Real runs show systematic misses, expansion patterns or clear quality/cost changes. Broader
transitive relationships or learned ranking require measured benefit and explicit provenance.
