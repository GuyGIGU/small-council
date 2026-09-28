# Phase 5.5 — context delivery pilot

## Decision and scope

Phase 5's pack builder is mechanically tested, but its value to real workers is unproven. This
pilot separates two questions: (1) does a pack preserve known relevant evidence while excluding
unrelated seat material, and (2) does sending it alongside the authoritative brief actually
reduce initial material? Neither answers whether a worker finds more defects or spends fewer
tokens. Routing is held out of the context comparison so a changed roster cannot masquerade as a
context improvement.

## Local reproducible measurement

Run `python evals/run_context_pilot.py`. The script creates three disposable fixture repositories:
an isolated edit without an impact graph, a changed function with a direct importer and test, and
an auth change linked to a test and migration. Each has an unrelated UI surface and a second seat.
The control is the brief alone; the treatment is the same brief plus the seat-specific pack, as
Stage 5 currently instructs. All counts below are UTF-8 file bytes **referenced for dispatch**,
not tokens actually read by an agent. No model was run.

| Fixture | Control: brief | Treatment: brief + pack | Change | Known paths, hard rule, seat isolation |
|---|---:|---:|---:|---|
| Isolated edit (`minimal`) | 747 B | 1,872 B | +151% | Pass |
| Cross-module (`focused`) | 739 B | 2,075 B | +181% | Pass |
| Risky auth (`full`) | 746 B | 2,339 B | +214% | Pass |

The pack alone was 32% *larger* than the complete brief/index/graph input for the isolated edit,
and 33% and 23% smaller for the two larger fixtures. That comparison is not the dispatch
comparison: workers are still pointed at the brief. The local result supports selective relevance
on these fixtures, **not** a token saving. The additive delivery can be costly, particularly on
small tasks. The fixture links are deliberately known in advance; they cannot detect surprising
dependencies or measure whether an agent notices a bug.

The advisory router was also probed on the same three task descriptions using
`council route recommend --task TEXT` and the same command with `--classic`. These are policy
outputs, not observed agent usage or verified outcomes:

| Task wording | Adaptive size / agents / estimated tokens | Classic size / agents / estimated tokens |
|---|---|---|
| README typo | Solo / 0 / 20k | Squad / 3 / 260k |
| Cross-module report refactor | Squad / 4 / 340k | Squad / 3 / 260k |
| Auth change with database migration | Full / 6 / 500k | Squad / 3 / 260k |

The router differentiates these examples in a plausible direction, but it sees task wording,
not the repository's actual impact. Its token figures are planning assumptions, not savings or
spend. The adaptive high-risk arm adds security/data/architecture lenses; both arms request
adversarial verification. Whether the added lenses justify their cost requires the live
comparison below.

## Live paired-run protocol (not yet executed)

Use the same Claude model, effort/settings, task wording, clean repository snapshot, seat roster,
gates, and approval conditions in both arms. Run each arm in its own disposable worktree and
alternate arm order across tasks. Do not let one arm see the other's output. Pin the plugin
source revisions: `7776d20` (immediately before Phase 5, brief-only control) and `fbf9bc9`
(Phase 5 pack treatment). For the *context* comparison only, hold the Chair's routing and seat
assignment fixed, so the material delivered to workers is the meaningful change. Assess an isolated edit, a
cross-module bug, and an auth-sensitive change; the existing seeded-review and squad-review
fixtures provide two starting answer keys. Run at least two repetitions per arm before treating
small differences as directional. A separate routing comparison can hold context delivery fixed
while using classic versus advisory sizing.

Record per run: seeded issues found and missed; false findings; whether the saved deliverable and
machine gates are correct; verifier corrections; human interventions; actual input/output tokens
and wall time where the runtime exposes them; seats dispatched; pack expansions; and failures or
stalls. Score correctness and missed high-risk issues first. A cost or speed improvement counts
only if quality is not worse. A missed critical issue or false completion is a stop-and-investigate
signal, not something an average score should hide. Save raw traces and the rubric/answer key, and
label missing token accounting as unavailable rather than estimating it from bytes.

## Current status and next decision (2026-09-24)

This machine has Python and Git, but no `claude` command or usable Claude evaluation credential in
the current environment. The only saved smoke result (`evals/suite/results/smoke-triggering.json`)
is partial with `auth_failed` and zero cost; it is not a baseline. Therefore no live agent outcome
or cost comparison has been made. Keep context packs as an optional aid, do not advertise savings,
and do not make context-depth decisions self-tuning. Once a paid comparison is approved,
run the paired protocol before deciding whether packs should be default, conditional, simplified,
or removed. Phase 6's evidence model can proceed independently, but should not be justified by
unmeasured Phase 5 gains.

**Updated decision (2026-09-28):** the WSL evaluation runner has worked since 2026-09-25.
The paired run is now deferred for cost: the owner declined the benchmark on 2026-09-27.
The earlier authentication failure is historical, not the current blocker. Until it runs, packs are
**opt-in**: the Chair builds them only when the project config says `context packs: on` or the
user asks in a run. Brief-only dispatch is the default. The protocol above is unchanged and is the
path to reconsidering the default.
