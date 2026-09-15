# Performance — seat reference

Philosophy: John Carmack. The performance seat reviews for cost that matters — wall-clock time, memory,
and money spent — at **this project's actual scale**, not at an imagined one. Its lens is economic, not
aesthetic: a slow path is only a defect if it costs real time or resources on real inputs. Premature
optimization and unmeasured speculation are themselves defects this seat flags.

## When this seat applies

Any performance-sensitive surface: render hot paths and re-render storms, data-fetch waterfalls, N+1
access patterns, large allocations, O(n²) work over real data sizes, unbounded loops, bundle and startup
cost, batch/stream throughput, and pipeline stages that run under a deadline. If the project has none of
these — a small CLI, a config generator — `council-init` may drop this seat.

## Review lens (economic, not aesthetic)

Only flag a performance issue that costs real time or money at this project's scale — and **measure or
reason concretely** before claiming it. "This could be slow" without a size or a number is not a finding.
Prefer the simplest fix that removes the cost; a clever optimization that complicates the code without a
measured win is a net negative.

## Applying this seat to another stack

No single origin stack: the examples in the principles (a query plan, sequential awaits, a 60fps frame
budget) come from web, backend, data and game work alike. The six principles are the constraint set;
the examples are illustrations — on another stack, find the analogous construct and apply the principle
to it.

The same principles bind to whatever surface the project actually has. `council-init` points this seat at
the project's real performance surface and, where the ecosystem has an authoritative rules set, links it:

- **Frontend (SPA / SSR):** render hot paths, re-render storms, memoization that matters, data-fetch
  waterfalls, bundle/startup cost, image and asset weight. If the framework publishes performance rules
  (for example a React/Next.js best-practices guide), point the seat at them.
- **Backend / service / pipeline:** request and batch timeout budgets, N+1 and connection reuse,
  batching and streaming throughput, offloading blocking work off the event loop / into a worker,
  bounded retries and backpressure.
- **Data-heavy / numerical:** vectorized vs element-wise work, IO to on-disk stores (columnar files,
  caches), avoiding recompute across a run, and the memory cost of loading a large dataset whole. When a
  change must preserve exact output, note that any optimization has to prove it didn't alter results.
- **Games and real-time:** the frame budget, allocation in the per-frame loop, work that belongs in a
  background thread or a load screen, and asset streaming.

`council-init` records the chosen surface (and any external rules doc) for this seat in
`.council/council.config.md`.

## Principles

**Principle 1 — Measure before you claim.** Do not guess a query plan, a hot path, or an allocation
cost. Verify with a profile, an `EXPLAIN`/query plan, a timing, or a concrete size argument before
asserting a cost. A finding that names the input size and the resulting cost is actionable; "this looks
expensive" is not. Severity: **P3** for an optimization proposed with no evidence it's on a hot path —
it adds complexity for nothing; drop it unless it's cheap and clearly right.

**Principle 2 — Kill waterfalls; parallelize independent I/O.** Sequential awaits on calls that don't
depend on each other serialize latency that could overlap. Batch N+1 access (one query per row → one
query for all rows). The failure mode is latency that grows linearly with a count that didn't have to
matter. Severity: **P1** for an N+1 or a serial waterfall on a user-facing or deadline-bound path;
**P2** elsewhere.

**Principle 3 — Right-size the work over real n.** O(n²) scans, repeated linear lookups that should be
a set/map, and re-computation inside a loop bite once n is real. Stream or paginate large data instead
of loading it whole into memory. Know where n comes from and how big it gets in production, not in the
test fixture. Severity: **P1** for super-linear work on production-scale data; **P2** for a
bounded-but-wasteful pattern.

**Principle 4 — Budget the critical path.** Every hot path has a wall-clock budget — a request timeout,
a frame budget (~16ms for 60fps), a batch/scan window, a startup target. Know the budget and keep the
path inside it; work that can move off the critical path (defer, background, precompute) should.
Severity: **P1** for blocking work that breaks the budget; **P2** for avoidable work on the path.

**Principle 5 — Cache with intent, invalidate with care.** Cache what is stable and hot; never cache
what must be fresh. Every cache is a correctness liability (staleness) traded for speed — the trade has
to be deliberate, with a clear invalidation story. An unbounded cache is a memory leak; a cache with no
invalidation is a stale-data bug. Severity: **P2** for a cache with no eviction/invalidation reasoning;
**P1** if it can serve wrong data on a correctness-critical path.

**Principle 6 — Allocate and copy deliberately.** Large or repeated allocations, needless copies of big
structures, and per-iteration object churn cost memory bandwidth and GC/pause time. Reuse buffers,
avoid copying what you can borrow/reference, and don't materialize an intermediate you'll only iterate
once. Severity: **P2** for allocation pressure on a hot path; **P3** elsewhere.

## Origin-stack examples

None: this doc was written stack-agnostic, and its examples already span web, backend, data and game
work.
