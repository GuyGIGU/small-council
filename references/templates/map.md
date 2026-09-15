# Codebase map — <project>
map-commit: <full sha>
updated: <YYYY-MM-DD>
<!-- Small Council orientation map: read this BEFORE exploring the code. It is an index, not
     documentation — keep it under ~250 lines. Refresh incrementally: `git diff --stat <map-commit>..HEAD`,
     re-survey only the changed areas, patch those sections, bump map-commit. -->

## Shape
<One paragraph: what the system is, its main runtime pieces, and how they talk to each other.>

## Where things live
| Area | Path | Responsibility | Entry points |
|---|---|---|---|

## Flows that matter
<3–6 numbered flows, one line each: trigger → module → module → store or output.>

## Data & state
<Stores, schemas and migrations, caches, generated files, config — and which code writes each.>

## Tests & gates
<Where tests live, fast vs full runs, slow or flaky areas, regression harnesses.>

## Hot spots
<Where bugs cluster, the riskiest or most complex modules, known debt — with paths.>

## Vocabulary
| Term | Meaning | Where in code |
|---|---|---|

## Conventions in the code
<Naming, error handling, and patterns new code must match. Point at AP/EC entries instead of repeating them.>
