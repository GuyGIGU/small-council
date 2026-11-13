# Adaptive routing foundation

`council route recommend` proposes a council shape before a run is opened. It is an advisory,
deterministic policy, not a dispatcher. It writes nothing, starts no agents, selects no model, and
does not replace the project's roster or the checked `run-plan.tsv` contract. The Chair reviews the
recommendation against the actual request, repository and user constraints, then records the final
decision and its reasons in the run plan.

## Interface

```text
council route recommend --task TEXT [--risk low|medium|high]
  [--complexity 1..10] [--uncertainty low|medium|high]
  [--surface NAME ...] [--agent-cap N] [--budget-tokens N] [--classic]
```

The command prints tab-separated rows with the same five-column header as a run plan:
`kind`, `id`, `field`, `value`, `reason`. These are **recommendation** rows, not a ready-to-use
`run-plan.tsv`: they have a policy marker, assessments, size and status, cap and budget estimate,
verification level and status, and dispositions for generic seat archetypes. Each consequential
choice has a short reason.
The complexity score is on a 1–10 scale; its low/medium/high band is supplied for the v1 run plan.
Use the project roster's actual slugs when writing that plan; an archetype is not a new seat.

The CLI infers a first pass from words in the task and optional named surfaces. It recognizes
coarse security, persistent-data, frontend, architecture and performance signals; it does not
inspect files. Explicit assessment flags override the corresponding inferred values. A
`--surface` is a free-form hint, not proof that a file or dependency is affected. Check the real
change and the roster's Surface markers before dispatch. `--classic` holds the size at the static
Squad baseline where caps allow, with implementation, testing and verification archetypes but no
adaptive specialist additions. It still prints the assessments for comparison. It is reduced to
Solo when a cap cannot fit Squad. This is a ceremony baseline, not a reproduction of every
historical Chair decision.

## Decision boundaries

- **Complexity** describes the amount of coordinated work, not the seriousness of failure. A
  small security fix can be simple but high-risk.
- **Risk** describes potential harm, reversibility and exposure. It governs how much independent
  challenge is warranted; it is not a prediction that a defect exists.
- **Uncertainty** describes missing information about intent, code or behavior. It can justify
  deeper discovery without assuming that more workers will resolve the ambiguity.
- **Size** is Solo, Squad or Full, the sizes the run plan already understands. The policy should
  recommend the smallest useful size and reserve room for verification. An agent cap is a ceiling,
  not a target; the Chair is not counted, while workers and verifiers are.
- **Budget** is an estimate and optional ceiling expressed in tokens. It does not meter provider
  use, reserve tokens or force unused budget to be spent. Tool-call budgets for selected seats are
  still set in the run plan at Assign.

The current policy starts at complexity 2, adds one point per named surface, two for an
architecture signal, one each for security and persistent data, and two for wording that indicates
cross-module or end-to-end work; the score is capped at 10. Scores 1–3 map to low, 4–6 to medium,
and 7–10 to high in the v1 plan. Risk is high for security, persistent data or destructive/public
changes; medium for other recognized specialist surfaces; low otherwise. Uncertainty defaults to
medium because task wording alone cannot establish what is known. These rules are transparent
starting points, not repository impact analysis.

Adaptive sizing starts Solo and adds workers and independent verification as signals warrant.
The planning estimate is 20,000 tokens for Chair work plus 80,000 per selected agent, including
verifiers. This is an explicit heuristic anchored to the earlier 60–100k-per-worker planning range,
not measured consumption. `--budget-tokens` supplies a separate ceiling; it must not turn an
unaffordable estimate into a pretend cheaper one. It does not raise the project's configured agent
cap, and `--agent-cap` may only lower that cap. If a cap cannot support the verification a high-risk
task needs, the tool must make that limitation explicit rather than present a cheap Solo run as
equally safe.

Full needs at least four agent slots and a 340,000-token planning ceiling; Squad needs at least
three slots and 260,000 tokens. With no explicit ceiling, these checks do not restrict size. A
constraint can lower the tier, but the final estimate is calculated from the selected agents,
never clipped to fit the ceiling. `run/route/status` is `ready`, `constrained` when a tier was
reduced or a relevant lens was omitted for the cap, or `needs-rescope` when the estimate still
exceeds the ceiling or required verification cannot fit. `verification/route/status` is
`available`, `constrained`, or `unavailable` accordingly.
High risk retains an `adversarial` verification recommendation; medium risk, complexity 4–10 or
high uncertainty requires at least `independent`. A cap never silently changes that level to
`self`. The command still exits successfully for `needs-rescope` so its explanation can be read.
Convene must resolve this status with the user before opening or dispatching a run; it cannot
treat the proposal as approval to skip required verification.

For a multi-agent recommendation the policy starts with implementation and testing archetypes,
reserves a verifier slot, then adds relevant specialist lenses in a fixed order while space remains.
Every omitted archetype has a reason. Because the output uses generic archetypes, the Chair must
map, pair or decline them against the project's real roster. When a cap or budget is insufficient,
the Chair must explain the tradeoff and resolve the needed scope or resources with the user before
opening or dispatching the run.

The recommendation is deliberately coarse. It uses no impact graph, symbol analysis, per-task
outcome model or historical seat-learning signal. Repository-specific facts, project hard rules,
missing checks and the user's explicit preferences can override it. Record any changed decision in
the plan's `reason` column and validate with `council run plan check` before Brief or dispatch.
The keyword signals currently recognize English terms; other languages or project-specific names
may be missed, so provide explicit assessment and surface inputs when that matters.

## Compatibility and limits

Existing manual sizing and static council behavior remain available. A run only changes when the
Chair adopts a recommendation in its plan. Older runs require no migration. The output is suitable
for inspection and comparison; it is not evidence that the selected seats, verification level or
budget are optimal.

Earlier project docs give a no-history estimate of roughly 60–100k tokens per worker, with past
runs described as averaging around 100k. The route estimate uses that range for planning; it is
not a measured Phase 3 efficiency gain. Reliable per-task cost and effectiveness data are not yet
available, so the routing policy is heuristic. The one measured input it takes is an `estimate per
worker` line in `council.config.md`, which `council tune` proposes once five completed runs
measure tokens per agent and the user approves; only a ceiling the user gives shrinks a run.
Outcome-based tuning of the policy itself waits for the benchmark (`evals/bench/`).
