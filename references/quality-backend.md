# Backend Quality Reference — Carmack × Collina × tRPC

Philosophy: John Carmack. Runtime expertise: Matteo Collina (Fastify, Pino, Node.js TSC). Patterns: tRPC community + Next.js App Router.

Every finding must describe the **concrete failure mode** — not just "this is bad practice."
Security patterns are in security.md (Hunt). Performance is in quality-performance.md. Datastore depth is in quality-postgres.md (Brandur). This doc covers: async correctness, error handling discipline, API procedure design, and server-boundary patterns.

---

## Applying this seat to another stack

The examples come from the origin stack: Next.js App Router, TypeScript, tRPC, Prisma, Neon (serverless Postgres) and Clerk, on Node.js.

The numbered principles are the constraint set; framework-specific checks are illustrations. On another stack, find the analogous construct and apply the principle to it. Origin-only detail is at the end.

| In the origin stack | The general idea | Look for it in … |
|---|---|---|
| tRPC procedure + Zod `.input()` / `.output()` | Entry point that validates input and filters output | FastAPI path operation + Pydantic models; Go `http.Handler`; Rails controller + strong parameters |
| `protectedProcedure` | Auth applied once, structurally | FastAPI `Depends()`; Rails `before_action`; ASP.NET Core `[Authorize]` |
| Node.js event loop, promises | What blocks the runtime's concurrency | Blocking calls in Python `async def`; Kotlin coroutines blocking `Dispatchers.Main`; a Netty or Vert.x event-loop thread; a UI main thread (Go: look for unbounded goroutines and lock contention instead) |
| `errorFormatter`, Prisma error codes | Translate internal errors at the edge | FastAPI exception handlers; Go error-to-status mapping; Rails `rescue_from` |
| Node streams, `fetch` bodies, `AbortController` | Resource lifetime, backpressure, cancellation | Python `async with`; Go `defer resp.Body.Close()`; .NET `CancellationToken` |
| TanStack Query cache, `revalidatePath` | Caches each mutation must invalidate, per tenant | HTTP/CDN caches; Redis; a mobile offline store |

---

## Principle 1: Programmer errors are assertion failures — crash, don't recover

*Carmack: assertions are tripwires. When an invariant is violated, halt execution.*
*Collina (via Joyent): "The best way to recover from programmer errors is to crash immediately."*

The Joyent error handling model classifies errors into two categories:

**Operational errors** — run-time problems experienced by correctly-written programs: network timeout, invalid user input, 503 from a dependency. Action: handle, retry with backoff, or propagate to the caller.

**Programmer errors** — bugs: reading property of `undefined`, wrong argument types, missing required fields. Action: crash immediately. The process is in an unknown state.

The argument for crashing is devastating and directly relevant to any service holding database connections. From the Joyent guide: continuing after a programmer error risks *"(1) Some piece of state shared by requests may be left null, undefined, or otherwise invalid. (2) A database connection may be leaked. (3) Worse, a postgres connection may be left inside an open transaction. This causes postgres to 'hang on' to old versions of rows in the table because they may be visible to that transaction. This can stay open for weeks, resulting in a table whose effective size grows without bound — causing subsequent queries to slow down by orders of magnitude."*

Anything that outlives a request — a process-wide pool, a long-running worker, a warm serverless container — carries a leaked connection into the next one.

### What to check

**Swallowed errors**
- Empty catch blocks: `.catch(() => {})`, `catch (e) { /* ignore */ }`, Python's `except: pass`.
- Global handlers for unhandled errors that only log — this disables the tripwire (Node: `process.on('unhandledRejection', console.error)`).
- Collina: **"The biggest problem is knowing that somebody will catch your errors. Especially with long promise chains and long async await, you need to know there is somebody at the end catching your things."**
- Concrete rule: never add a catch-all to suppress an error you don't understand. If you can't explain what the rejection means and what state the process is in after catching it, let it crash.
- Severity: **P1** when the swallowed error involves database connections or shared state. **P2** for other cases.

**Mixed delivery mechanisms**
- Functions that throw synchronously in some code paths and reject asynchronously in others. Joyent: **"A given function should deliver operational errors either synchronously (with throw) or asynchronously (with a callback or event emitter), but not both."** Callers can't catch errors reliably when delivery is mixed.
- Severity: **P2**

**Retry storms**
- Every layer retrying independently. Joyent: **"If every layer of the stack thinks it needs to retry on errors, the user can end up waiting much longer than they should because each layer didn't realize that the underlying layer was also retrying."**
- If the API layer, the database client AND the frontend's data fetcher all retry, a single transient failure triggers exponential retry amplification (origin: tRPC middleware, Prisma, TanStack Query).
- Severity: **P2** when retries aren't documented/coordinated across layers.

**Async functions as event handlers**
- Passing an `async` function to a callback API that ignores the promise it returns (in Node, `.on('data')` or any EventEmitter). Collina (JS Party #103): **"An async function can throw, and the promise will reject. But the problem is that nobody right now is catching that rejection for you."** The rejection goes unhandled, the resource is never cleaned up.
- Severity: **P1** — this is a memory leak and an unhandled rejection in one.

---

## Principle 2: Never hide what the runtime is doing — the event loop and every hidden cost

*Carmack: if you can't see the cost, you can't reason about correctness.*
*Collina: built Fastify because Express hides the runtime. Built Pino because logging shouldn't be opaque. Built Clinic.js because manual debugging is unreliable.*

### What to check

**Event loop blocking**
- Blocking work on the loop or thread that serves requests: parsing large payloads, synchronous file I/O, synchronous crypto, CPU-bound loops (in Python, a blocking call inside `async def`).
- Collina (USENIX SREcon 2023): **"The most common problem is an exhaustion of resources that allows the application to denial of service itself."** With 100 requests each requiring 30ms of synchronous work, the last request waits the accumulated time of all prior.
- In serverless: each invocation is isolated, so one blocked invocation doesn't block others. But **cold start time compounds with blocking** — 200ms of synchronous module initialisation adds to every cold request.
- Severity: **P1** for synchronous I/O in request paths. **P2** for CPU-bound work that could be deferred.

**Assuming `await` yields to other work**
- The most dangerous async misconception. Know what actually lets I/O run in your runtime — in Node.js, `await` does NOT yield to the event loop.
- CPU-bound async loops over unbounded input need an explicit yield point.
- Recursive self-scheduling on a queue that drains before I/O starves the loop the same way.
- Severity: **P2** when the loop processes unbounded input. **P3** for small bounded loops. **P1** for recursive scheduling that starves I/O.

**Hidden middleware costs**
- A one-line handler can hide several middleware functions; if one calls the auth provider over the network, that latency is invisible at the call site. Know what each middleware costs.
- Severity: **P3** — this is transparency, not a bug. Escalate to **P2** if middleware makes external calls without the team knowing.

**Logging that hides its cost**
- Collina created Pino because logging was a throughput bottleneck.
- Collina: **"You should not have very expensive logging because if you have very expensive logging, then you will be inclined to log less and not more."**
- Core Pino principles, true of any logger: JSON only in production (machines consume logs, not humans). Log to stdout, ship elsewhere off the request path. Child loggers per request for context. Never format in-process.
- Severity: **P2** for a known-slow or synchronous logger in production. **P3** for logging without structured JSON.

---

## Principle 3: Validate at the boundary, sanitise at the exit

*Carmack: deploy assertions as tripwires — catch assumption violations before they propagate.*
*Collina + tRPC: Zod schemas at procedure boundaries ARE the tripwires.*

### What to check

**Loose input schemas**
- A plain string type where an email, UUID, URL or length bound is needed (Zod: `.string()` vs `.email()`, `.uuid()`, `.url()`, `.min()`, `.max()`). Cost: a typo in the client sends `"undefined"` (the string) as a user ID, which queries the DB and returns null instead of failing fast at validation.
- Every state-changing entry point MUST validate its input against a runtime schema. Every parameterised read likewise. Compile-time types don't exist at runtime.
- Severity: **P2** for mutations without input validation. **P3** for queries with overly loose schemas.

**Data-layer errors leaking to the client**
- **This is a critical finding.** When a database or ORM error escapes unhandled, the framework may wrap it as a generic internal error but **still send the original message to the client** — stack traces stripped in production, messages not (tRPC does).
- Concrete leak: a unique-constraint error names the schema's fields; a create call with wrong fields describes the expected schema shape.
- Fix: sanitise every internal-error message at the edge (replace it with a generic string) AND translate known data-layer errors into domain errors (unique violation → conflict, missing record → not found).
- Severity: **P1** — this is information disclosure. Cross-reference with security.md.

**Missing output validation on sensitive procedures**
- A procedure returning a full data-layer user model without output validation includes every field — including any sensitive ones the client shouldn't see.
- Pass responses through an explicit output schema, so a mismatch fails on the server instead of leaking data.
- Use sparingly (adds runtime overhead) but mandate for procedures that return user data, billing data, or anything with PII.
- Severity: **P2** for procedures returning user/billing models without output filtering.

**Framework-generated endpoints without validation**
- Anything the framework exposes over HTTP on your behalf — server actions, RPC stubs, generated routes — is a public endpoint anyone can call with arbitrary payloads.
- Always validate inputs server-side. Always check auth inside each one — don't assume it's only callable from an authenticated page.
- Severity: **P1** for mutations without server-side validation. **P2** for missing auth checks in actions.

---

## Principle 4: Auth as a type constraint — make the unauthenticated path unrepresentable

*Carmack: make the wrong thing impossible rather than trusting humans to do the right thing.*
*tRPC: middleware narrows context types, converting runtime checks into compile-time constraints.*

Auth logic lives in shared middleware or a protected base handler, not in individual handler bodies (tRPC's `protectedProcedure`).

### What to check

**Auth enforced ad hoc instead of via middleware**
- Handlers that check the user inside their own body instead of inheriting a protected base. Cost: one developer forgets the check, one endpoint is unprotected.
- The protected base should hand the handler a non-null user, so an unprotected handler that reaches for it fails to compile — or, in a dynamic language, fails closed.
- Severity: **P1** for unprotected procedures that should require auth. **P2** for ad hoc checks that work but aren't enforced by the type system.

**Missing org-scoped middleware for multi-tenant B2B**
- Authentication confirms the user exists but doesn't confirm they have access to the requested organisation's data. A tenant-scoped layer that extends the authenticated one with an org check is needed.
- Without this: every procedure that touches org-scoped data must manually verify org membership. One miss = IDOR.
- Severity: **P1** if org-scoped data is accessible without org verification.

**Middleware ordering bugs**
- Middleware executes in declared order. If the org check runs before the auth check, the user is still nullable — causing runtime errors or redundant null checks.
- Swallowed errors in middleware: if middleware catches an error and doesn't re-throw, the client receives a success response with undefined data. This is the middleware equivalent of an empty catch block.
- Severity: **P2**

---

## Principle 5: Resource management — connections, streams, cleanup

*Carmack: understand the lifecycle of every resource you allocate.*
*Collina: every unconsumed body, unclosed stream, and leaked listener is a resource that compounds.*

### What to check

**Unconsumed response bodies**
- HTTP calls to external services where the response body is never read or closed (in Go, a missing `resp.Body.Close()`). Collina (Node Congress 2024): **"Something very important to remember is whenever you get a body, please consume the body."** Unconsumed bodies hold connections open, exhausting the connection pool.
- In any middleware that makes HTTP calls: consume or close the body even if you only need the status code.
- Severity: **P2** — connection pool exhaustion is a slow leak that manifests under load.

**Missing backpressure handling**
- Writing to a stream, queue or channel without honouring its signal to wait. Ignoring this is the most common backpressure bug.
- The failure mode is a GC death spiral: more memory allocated → longer GC pauses → event loop blocked during GC → more memory accumulates.
- Concrete risk: CSV file upload processing, database result streaming, any producer-consumer pipeline.
- Fix: use the runtime's pipeline primitive, which handles backpressure, error propagation and cleanup, rather than hand-wired piping that drops errors.
- Severity: **P1** for file upload/download paths without backpressure. **P2** for internal pipelines.

**Event listener leaks**
- Subscribing a listener, observer or callback without a matching unsubscribe. Over time, listeners accumulate, each holding references to closed-over scope.
- Use one-shot subscriptions for one-shot handlers. Unsubscribe in `finally` or the equivalent cleanup path.
- Severity: **P2**

**Cancellation**
- Long-running operations without cancellation support. A cancellation signal (Go: `context.Context`) allows cleanup when a request is terminated by the client or a timeout fires.
- In serverless: background work after `return` may be killed when the function terminates. `waitUntil()` (where available) extends lifetime for cleanup — but this is platform-specific.
- Severity: **P3** — good practice but not a correctness bug unless resources are leaked.

---

## Principle 6: API architecture — routing, cache invalidation, and the server boundary

*Carmack: architecture earns its boundaries through demonstrated need, not speculative design.*
*tRPC: type safety justifies the abstraction — but know what it hides.*

### What to check

**Router organisation**
- Domain-driven sub-routers: one router or module per entity, namespaced (`user.list`, `post.create`).
- Route composition where two routes with the same name or path **silently overwrite each other** — no compile error, no runtime error, just lost functionality. Prefer composition that makes a collision an error.
- Severity: **P1** for silent route collisions (silent data loss). **P3** for disorganised routers.

**Cache invalidation bugs (correctness, not performance)**
- Forgetting to invalidate related queries after mutation: creating a post invalidates `post.list` but not `post.count` or dashboard summaries. The user sees stale counts.
- Optimistic updates that don't cancel in-flight refetches — the refetch overwrites the optimistic update.
- Optimistic updates with no invalidation once the mutation settles — on error, the UI stays in the optimistic state permanently.
- For apps displaying invoice status, subscription state, or team membership: stale data is a correctness bug, not a performance tradeoff.
- Severity: **P2** when stale data affects business-critical state. **P3** for cosmetic staleness.

**Wrong boundary choice**
- Reads sent through an uncacheable mutation mechanism invisible to monitoring, or a heavyweight API layer for a simple form post.
- Severity: **P3** — wrong choice adds complexity but isn't a correctness bug.

**Edge or gateway middleware misuse**
- Auth only in middleware in front of the app: it can be bypassed. Always validate auth at the data access layer too.
- Middleware in a restricted runtime asked to hold a database connection, or consuming the request body the handler still needs.
- Severity: **P1** for auth only in middleware with no data-layer check. **P2** for database calls in middleware that can't hold connections (will error). **P3** for body consumption issues.

**Multi-tenant cache safety**
- Cache keys that don't incorporate tenant ID. If User A's cached data is served to User B, this is a data leak, not a performance issue.
- Permission changes: user's role is downgraded but cached data still shows admin-level content.
- Severity: **P1** for cross-tenant cache leaks. **P2** for stale permission data.

---

## Principle 7: Structured logging — observability as correctness

*Carmack: automate what can be checked mechanically.*
*Collina: "If you have very expensive logging, then you will be inclined to log less."*

### What to check

**Logging architecture**
- Collina: **"Just send to standard output, and then somebody else will pick those things up and ship it where it needs to be shipped. Which is the philosophy of cloud-based logging anyway."**
- Child loggers per request with pre-populated metadata (request ID, user ID, org ID). All subsequent logs from that child include the context automatically.
- Severity: **P3** for non-structured logging. **P2** for logging that blocks request handling (synchronous transports in production).

**The mechanical verification stack**
- Strict types + a protected base handler: auth enforced at compile time.
- Input schemas: validation is mechanical. A UUID type catches what a plain string passes.
- Output validation: mechanical check that procedures don't leak unexpected fields.
- Edge error sanitisation: mechanical check that internal-error messages never reach the client with raw data-layer details.
- Lint or compiler rules that flag un-awaited async calls, and async functions that never await.
- Severity: **P2** for no mechanical check on un-awaited async calls. **P3** for other missing mechanical checks.

---

## Gaps: What This Doc Doesn't Cover

- **Security patterns**: SQL injection, XSS, CSRF, access control, secrets management. Covered by **security.md (Hunt)**.
- **Performance optimisation**: bundle size, re-renders, caching strategy, Suspense streaming, auto-scaling. Covered by **quality-performance.md**.
- **Datastore depth**: transaction safety, migration patterns, schema design, connection pooling configuration. Covered by **quality-postgres.md (Brandur)**.
- **Frontend patterns**: component architecture, testing, state management. Covered by **quality-frontend.md (Dodds)**.
- **Concurrency depth**: cancellation propagation, fire-and-forget tasks, bounded fan-out and task lifecycle go to **quality-concurrency.md (Goetz)** when seated; this doc keeps event-loop blocking and stream backpressure.
- **WebSocket and SSE subscriptions at scale**: at early stage this is manageable. If subscription count grows significantly, revisit resource monitoring.
- **Framework internals** (Fastify's plugin system, decorators, lifecycle hooks, and the like): only Collina's runtime principles apply.
- **DevOps/infrastructure**: Docker, CI/CD, deployment strategies. Out of scope.

---

## Quick Reference: Severity Guide

| Severity | Pattern | Examples |
|----------|---------|----------|
| **P1 — Fix Now** | Errors that corrupt state, leak data, or crash silently | Swallowed errors on DB operations, data-layer errors leaking schema to the client, unprotected endpoints, auth only in middleware, async event handlers, missing backpressure on file uploads, silent route collisions, cross-tenant cache leaks, framework-generated endpoints without validation |
| **P2 — Fix Soon** | Patterns that hide runtime behaviour or compound | Blocking the event loop or request thread, awaits that don't yield, ad hoc auth checks, middleware ordering bugs, unconsumed response bodies, listener leaks, stale business-critical cache, output validation missing on sensitive data, retry storms, a slow or synchronous logger in production, no check for un-awaited async calls |
| **P3 — Consider** | Transparency and hygiene | Hidden middleware costs, non-structured logging, disorganised routers, wrong boundary choice, unnecessary `async` wrappers, missing cancellation |

### The Overriding Filter

Before writing any finding, apply the Collina-Carmack synthesis:

1. **Is this error handled or swallowed?** If swallowed, flag it. (Both: failing silently is worse than crashing.)
2. **Is the runtime behaviour visible?** If the event loop cost, middleware cost, or logging cost is hidden, flag it. (Collina: make the runtime transparent.)
3. **Is validation mechanical?** If a human must remember to validate, flag it. If the type system or a runtime schema enforces it, it's correct. (Both: automate what can be checked.)
4. **Is auth enforced by types?** If a developer can forget to check auth without a type error, the architecture is wrong. (Carmack: make the wrong thing impossible.)
5. **Can this leak across tenants?** Cache keys, connection state, error messages — anything shared must be tenant-scoped. (Both: if it's possible, it will happen.)

---

## Origin-stack examples (Next.js / TypeScript / tRPC / Prisma / Neon / Clerk)

### Principle 1 — crash, don't recover
- In serverless, each invocation dies after execution — "let it crash" is the default.
- Serverless: pool state persists across warm invocations on the same container, so a leaked Prisma connection poisons later warm starts.
- Since Node.js v15, unhandled rejections crash the process by default. That's correct.

### Principle 2 — the Node.js event loop
- Collina (Fosstodon, November 2024): **"Contrary to popular belief, in Node.js promises (and async/await) would not yield to the event loop."** `await` yields to the microtask queue, which is drained completely *before* the event loop proceeds to timers, I/O, or any other phase.
- Hidden cost: `orgProcedure.input(…).mutation(…)` hides that three middleware functions run before the resolver.
- Concrete failure: a tRPC procedure awaiting synchronously-resolving transforms over a large array blocks the entire event loop. Fix: `await new Promise(resolve => setImmediate(resolve))` periodically.
- Recursive `process.nextTick` starves the event loop: its queue drains between every phase, before microtasks. Yield with `setImmediate` (the "check" phase) instead. **P1** for recursive `nextTick`; **P3** for single use.
- Blocking calls: `JSON.parse` on large payloads, `fs.readFileSync`. Clerk's `currentUser()` in middleware is an HTTP call — use `auth()` (reads the JWT locally) unless you need the full user.
- Logging: Bunyan cuts throughput by ~70%, Winston by ~50%; Pino beats express-winston by 40%. **P2** for Winston/Bunyan in production.

### Principle 3 — Zod, tRPC errors, Server Actions
- Every tRPC mutation MUST have an `.input()` with a Zod schema; every query with parameters likewise.
- tRPC wraps an unhandled Prisma error as `INTERNAL_SERVER_ERROR` but still sends its message, e.g. `"Unique constraint failed on the fields: (email)"`. Fix: sanitise in `errorFormatter` AND translate Prisma codes in middleware (P2002 → `CONFLICT`, P2025 → `NOT_FOUND`).
- tRPC `.output()` returns `INTERNAL_SERVER_ERROR` instead of leaking data when output validation fails.
- Every `'use server'` function compiles into a public HTTP POST endpoint whose action ID is visible in client bundles — anyone can `curl` it. Validate with Zod; consider `next-safe-action` (auth, rate limiting, structured results).

### Principle 4 — `protectedProcedure`
- THE auth pattern for this stack: the resolver gets `ctx.auth.userId` as `string`, not `string | null`, so a `publicProcedure` used by mistake is a type error. An `orgProcedure` extends it with an `orgId` check.
- Middleware runs in `.use()` chain order: `orgMiddleware` before `authMiddleware` leaves `ctx.user` nullable.
- **tRPC v10+ design note:** Router-level middleware was deliberately removed. All auth enforcement is via procedure composition, not router configuration — more composable, and auth is visible at the procedure definition.

### Principle 5 — Node streams and emitters
- `fetch` / `undici` response bodies must be consumed even when only the status matters.
- When `.write()` returns `false`, stop and wait for `drain`. Use `stream.pipeline()` (backpressure, error propagation, cleanup), not `.pipe()` (doesn't propagate errors); iterate with `for await...of` and error handling.
- Node.js warns at >10 listeners on one event. Use `emitter.once()` for one-shot handlers and `emitter.off()` in `finally`. Cancel with `AbortController`.

### Principle 6 — tRPC routers, TanStack Query, Next.js
- Nested routers merged into `appRouter` map to TanStack Query keys (`utils.user.invalidate()`). With `t.mergeRouters`, a same-named procedure silently overwrites another — no TypeScript error — so prefer nested routers. Optimistic updates need `await utils.cancel()` first and `onSettled` invalidation after.
- tRPC for Client Component fetching that needs TanStack Query's caching, polling and invalidation; Server Actions for form mutations with progressive enhancement and `revalidatePath`/`revalidateTag`. Server Actions used for fetching are non-cacheable POSTs invisible in APM tools; Documenso moved back to tRPC over monitoring difficulty and build corruption.
- Next.js middleware: the Edge runtime can't maintain persistent connections (no Prisma); consuming `request.json()` without cloning leaves the route handler nothing; CVE-2025-29927 bypassed middleware via the `x-middleware-subrequest` header.

### Principle 7 — Pino and the TypeScript verification stack
- Use Pino; transports run in worker threads (Pino v7+); `pino-pretty` in dev only.
- The stack: TypeScript strict mode + `protectedProcedure` (auth), Zod `.uuid()` over `.string()` (input), `errorFormatter` (no raw Prisma details in `INTERNAL_SERVER_ERROR`), ESLint `no-floating-promises` and `require-await`. **P2** for a missing `no-floating-promises` rule.
