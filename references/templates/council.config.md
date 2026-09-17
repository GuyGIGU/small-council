# Council config — <project>
<!-- Written by council-init. Hand edits are welcome: any section you add or change is yours and
     council-init never overwrites it (a re-run merges and shows a diff). Paths here must point inside
     the repo or at the plugin's references/ — never at files elsewhere on one machine. -->
last-verified: <YYYY-MM-DD> @ <short-sha>
<!-- Replace the next line with the whole line `council fingerprint` prints; never edit it by hand. -->
stack-fingerprint: <hash> — manifests: <…> · languages: <…>

## Stack
<2–5 lines: languages, frameworks, data stores, surfaces (UI / API / engine / CLI / game), runtime and
deploy target, domain. Name the one thing that must never break.>

## Run preferences
- approve without asking: up to squad
- agent cap: 10
<!-- "approve without asking": solo | squad | full — a /command starts runs up to this size without a
     second question; bigger runs always ask. "agent cap": agents per run, verifiers included. Yours to change. -->

## Roster
Chair: John Carmack — always on; the synthesis filter ("a real problem in this codebase at this scale,
or pattern-matching?"). Not a seat.

| Seat | Slug | Lens | Surface | Reference | Recast note |
|---|---|---|---|---|---|
| Troy Hunt | hunt | Security | `**/auth/**`, `token`, `subprocess`, `open(` | references/security.md | kept |
| Martin Fowler | fowler | Structure / refactoring | whatever no other seat claims | references/refactoring.md | kept — never dropped |
| Kent Beck | beck | Tests | `tests/**`, `*_test.*`, `*.spec.*` | references/quality-testing.md | kept — never dropped |
| <Seat> | <slug> | <lens> | <2–6 globs or words in this repo's idioms> | references/<file>.md or .council/refs/<file>.md | <why kept, or recast from whom> |

<!-- Surface: where this seat's lens lives in THIS repo — assignment matches it against the change.
     No "|" inside a cell (it's a table); list alternatives separately.
     Dropped seats (and why): <Seat> — <reason>. Recast before you drop: most "no surface" seats have an
     analogous surface (any persistent store → data integrity; any computation engine → numerical
     correctness). -->

## Gates
| Gate | Command | Run at | Mandatory | Checked | Probe | Needs | Side effects |
|---|---|---|---|---|---|---|---|
| tests | `<command>` | grounding, verify | yes | ✓ <date> | `<its fast dry-run, e.g. --collect-only>` | <tools, env vars, services> | none |
| lint | `<command>` | verify | no | ✓ <date> | `<command> --version` | — | none |
| build | `<command>` | verify | yes | ✗ <date>: <why it couldn't run here> | `<probe>` | <an SDK, a device> | writes the tree |

<!-- The council helper runs these (`council gate <name>`, `council gate --all --at verify`) and judges
     them by exit code. Never put `| tail`, `| head` or `| grep` in a gate command.
     Probe: the exact dry-run council-init ran. Needs: tools, env vars, credentials, hardware.
     Run at: grounding · verify · both · manual (by name only). Mandatory: yes · no.
     Checked: ✓ <date> · ✗ <date>: <why it can't run here> · ✗ not probed: <why> (init didn't dry-run it).
     The helper names any other word in these three cells rather than guessing what it means.
     Side effects: none · writes the tree · network · cost · hardware · deploy · credentials.
     `council gate --all` skips a gate marked ✗ and any gate whose side effects or needs involve
     cost, hardware, deploys or credentials — those run only by name, with the user's go-ahead. -->

## Hard rules
- <non-negotiables every worker and builder obeys, e.g. "never write to the production database",
  "engine output must stay byte-identical unless a task says otherwise">

## Memory
- conventions: .council/conventions.md
- map: .council/map.md
- cards: .council/cards/ (one per seat slug)
- ledger: .council/ledger.tsv (each completed run adds a row per seat)

## Notes
<free-form, owned by the user>
