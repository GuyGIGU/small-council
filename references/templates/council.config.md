# Council config — <project>
<!-- Written by council-init. Hand edits are welcome: any section you add or change is yours and
     council-init never overwrites it (a re-run merges and shows a diff). Paths here must point inside
     the repo or at the plugin's references/ — never at files elsewhere on one machine. -->
last-verified: <YYYY-MM-DD> @ <short-sha>
<!-- Replace the next line with the whole line `council fingerprint` prints; never edit it by hand. -->
stack-fingerprint: <hash> — manifests: <…> · languages: <…>

## Stack
<2–5 lines: languages, frameworks, data stores, surfaces (UI / API / engine / CLI / game), runtime and
deploy target, domain. Name the one thing that must never break. Each part's reason and watch lists
go on the book's stack page, not here.>

## Run preferences
- approve without asking: up to squad
- agent cap: 10
- models: builder=inherit, review=inherit, verifier=inherit
- build tier: light
- checking: one per batch
- pushes: on
- sharing: team
<!-- Add `- notifications: off` here to suppress `council status --line` and council phone alerts.
     Without that line, four owner-facing moments may notify when PushNotification is available:
     a blocking question, a stopped build, a cap/ceiling stop, and run completion. -->
<!-- "approve without asking": solo | squad | full — a /command or instruction to proceed without
     further confirmation approves up to this size. Full needs explicit size-and-cost approval;
     approval already given carries forward. "agent cap": agents per run, verifiers included.
     "build tier": light | full — how much proof a build records (references/build-proof.md, Tiers):
     light records a before/after pair for risky tasks only; full records one for every task.
     Missing means light. Yours to change.
     "checking": one per batch | per task — only the blind verifier a build starts for a finding on
     a protected subject (authorization, data loss, secrets …). One per batch: the agent gate lets a
     build start one and refuses a second without your go. Per task: no such limit. Every build is
     checked once, by a reader and a runner on the whole change, whatever this line says. Missing
     means one per batch.
     "open items": ask | fix now — an older config's line, still read, and it changes nothing: a
     build fixes the problems its check at the end confirms in the change in one round, without
     asking, and never starts a second (references/run/build-receipt.md, Open items). What is still
     wrong is in the report, under Does not work and Your decisions, for you to rule on. Smaller
     things it noticed go to known problems. Commit, push and PR stay questions.
     "pushes": on | off | off until <YYYY-MM-DD> — off holds push and PR (a team freeze): a build
     commits and stops, and the bash gate refuses git push and gh pr create (COUNCIL_ALLOW_PUSH=1 git
     push … on your word). From the date on it reads as on. Missing means on. `council pushes` shows it.
     "models": builder=, verifier= — inherit (the session's model), fable, opus, sonnet or haiku for
     a build's builders and for every verifier; a role left out, or no line, means inherit.
     Every other agent (the reader, the runner, the designer, a mapping worker) runs on the session's
     model; an older config's `- seat models:` line is no longer read (D74).
     council-init proposes a split from its own model (references/run/models.md); a verifier is
     never on a weaker model than the builder it checks. review= is still read and changes nothing:
     the Chair, the reader and the runner (a review's, a build's, a health pass's) and a plan's
     designer always run on the session's model.
     "sharing": team | just me — team commits .council/ with the project; just me keeps it on this
     machine (git's own exclude list ignores it, and CLAUDE.md gets no note), so teammates never meet
     the council. `council sharing just-me` / `council sharing team` switches it; missing means team.
     "estimates": `- estimates: builder=450k` — the tokens one builder costs in this project, yours
     to set by hand. A build's quote is that figure per task, plus 500k for the two agents that check
     the whole change. Without it each builder is quoted at 500k: a default until this project's own
     builds are measured (the Cost line of a build's report shows what they took). verifier= prices
     a post-game's checker (else `- estimate per worker:`, else 80k). review=, plan= and converge=
     are still read without complaint and price nothing: a review, a plan and a health pass have
     fixed figures, and a build has no converge verifier.
     "checks take": `- checks take: <n> min (measured <YYYY-MM-DD>)` — how long the project's checks
     took a review's runner; `council gates timed <n>` writes it, and a review's estimate uses it.
     Missing means not measured yet. -->

## Gates
| Gate | Command | Run at | Mandatory | Checked | Probe | Needs | Side effects |
|---|---|---|---|---|---|---|---|
| tests | `<command>` | grounding, verify | yes | ✓ <date> | `<its fast dry-run, e.g. --collect-only>` · broken: fail, exit <n> | <tools, env vars, services> | none |
| lint | `<command>` | verify | no | ✓ <date> | `<command> --version` | — | none |
| build | `<command>` | verify | yes | ✗ <date>: <why it couldn't run here> | `<probe>` | <an SDK, a device> | writes the tree |

<!-- The council helper runs these (`council gate <name>`, `council gate --all --at verify`) and judges
     them by exit code. Never put `| tail`, `| head` or `| grep` in a gate command.
     Commands run under bash (Git Bash on Windows), as written: bash drops a \ outside quotes, so
     write paths with / or quote them (cmd /c ".\run.bat").
     Probe: the exact dry-run council-init ran — for a mandatory gate, also its run with the tool
     deliberately broken, which must fail (a gate that passes without its tool fakes a green).
     Needs: tools, env vars, credentials, hardware.
     Covers (an optional column): the paths the gate checks, as git pathspecs from the code root,
     comma separated — e.g. a row `| ui | ... | none | app/ui/, *.kt |` under a `| Covers |` header.
     Empty means the whole tree. `council gate --all` doesn't rerun a gate when nothing under its paths
     changed since its last green in the run; the receipt lists it as not rerun.
     Run at: grounding · verify · both · manual (by name only). Mandatory: yes · no.
     Checked: ✓ <date> · ✗ <date>: <why it can't run here> · ✗ not probed: <why> (init didn't dry-run it).
     The helper names any other word in these three cells rather than guessing what it means.
     Side effects: none · writes the tree · network · cost · hardware · deploy · credentials.
     `council gate --all` skips a gate marked ✗ and any gate whose side effects or needs involve
     cost, hardware, deploys or credentials — those run only by name, with the user's go-ahead.
     Every gate runs under a time limit: the largest of three times its green baseline time in the
     run, `- gate time limit: <time>` (e.g. 20m) under Run preferences, and 120 s; with neither, 9
     minutes for a command given after --, 30 for a configured gate. A gate past it is stopped and
     recorded as TIMED OUT; add or raise the line when a check is slower — it counts from the next
     call on, mid-run too. -->

## Hard rules
- <non-negotiables every worker and builder obeys, e.g. "never write to the production database",
  "engine output must stay byte-identical unless a task says otherwise">

## Book
- design: .council/design.md
- stack: .council/stack.md
- decisions: memory
- known problems: .council/known-problems.md
<!-- The project's book (references/run/book.md): every agent reads the design page, the stack page and the
     decisions log before anything else, and a review reads known problems. Where the project keeps its own such
     file, setup names it here in place of the default, and never writes a second one. `decisions: memory` is the
     memory file's ## Decisions (D) section. `council book` prints where each page is, and the watch lists the
     stack page's rows name: the checklist pages for each part of the stack (references/watch-lists.md), which a
     brief names for the parts its work touches. There is no roster of expert seats. -->

## Memory
- conventions: .council/conventions.md
- map: .council/map.md
<!-- Add `- memory budget: <n> KB` here (a whole number from 1 to 1024; 25 KB when it is left out): past it,
     run open, a complete close, council status and council doctor say the memory has grown past what every
     run should read, and council memory tidy lists the merges and retirements it can find. -->

## Notes
<free-form, owned by the user>
