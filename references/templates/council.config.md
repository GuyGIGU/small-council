# Council config — <project>
<!-- Written by council-init. Hand edits are welcome: any section you add or change is yours and
     council-init never overwrites it (a re-run merges and shows a diff). Paths here must point inside
     the repo or at the plugin's references/ — never at files elsewhere on one machine. -->
last-verified: <YYYY-MM-DD> @ <short-sha>

## Stack
<2–5 lines: languages, frameworks, data stores, surfaces (UI / API / engine / CLI / game), runtime and
deploy target, domain. Name the one thing that must never break.>

## Roster
Chair: John Carmack — always on; the synthesis filter ("a real problem in this codebase at this scale,
or pattern-matching?"). Not a seat.

| Seat | Slug | Lens | Reference | Recast note |
|---|---|---|---|---|
| Troy Hunt | hunt | Security | references/security.md | kept |
| Martin Fowler | fowler | Structure / refactoring | references/refactoring.md | kept — never dropped |
| Kent Beck | beck | Tests | references/quality-testing.md | kept — never dropped |
| <Seat> | <slug> | <lens> | references/<file>.md or .council/refs/<file>.md | <why kept / recast from whom> |

<!-- Dropped seats (and why): <Seat> — <reason>. Recast before you drop: most "no surface" seats have an
     analogous surface (any persistent store → data integrity; any computation engine → numerical
     correctness). -->

## Gates
| Gate | Command | Run at | Mandatory | Checked |
|---|---|---|---|---|
| tests | `<command>` | grounding, verify | yes | ✓ <date> |
| lint | `<command>` | verify | no | ✓ <date> |
| build | `<command>` | verify | yes | ✗ <date>: <why it couldn't run here> |

<!-- Gates are judged by exit code. Never append `| tail`, `| head`, or `| grep` to a gate command. -->

## Hard rules
- <non-negotiables every worker and builder obeys, e.g. "never write to the production database",
  "engine output must stay byte-identical unless a task says otherwise">

## Memory
- conventions: .council/conventions.md
- map: .council/map.md

## Notes
<free-form, owned by the user>
