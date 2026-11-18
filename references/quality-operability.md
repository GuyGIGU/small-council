# Operability Reference — Carmack × Nygard

Philosophy: John Carmack. Specifics: Michael T. Nygard, author of *Release It!*, whose stability patterns and antipatterns name how software fails in production. This seat reviews how code behaves where it runs: under partial failure, under load, during deploys, and in front of the people who operate and support it.

The Carmack filter here is scale and blast radius. A hobby CLI needs no circuit breakers; a single-instance internal tool needs no distributed tracing. A finding tells a production story plausible for this system's traffic and fleet: "needs observability" is not a finding; "when the payment provider hangs, every checkout worker blocks and no alert fires" is.

## When this seat applies

Code that must keep running, or be supported, somewhere other than its author's machine: services, jobs, deploys, config, health checks, telemetry, flags, updaters and crash reporting, including apps, games and firmware on machines nobody can log in to. Example surface markers, rewritten in the repo's idioms:

- **Backend service or worker:** `**/clients/**`, `timeout`, `retry`, `healthz`, `SIGTERM`, `**/jobs/**`
- **Web frontend:** `Sentry.init`, `window.onerror`, `**/flags/**`, `serviceWorker`
- **Native mobile:** `RemoteConfig`, `minimumVersion`, `WorkManager`, `BGTaskScheduler`
- **Desktop app or game:** `**/updater/**`, `crashpad`, `minidump`, `SaveVersion`
- **Embedded or firmware:** `watchdog`, `wdt`, `ota`, `bootloader`, `HardFault_Handler`
- **CLI tool:** `sys.exit`, `os.Exit`, `--dry-run`, `stderr`

Drop it for libraries and dev-only tools, though a library's network calls still need timeouts its caller can set. With a thin operational slice (one service's clients and startup code), pair it with Backend in one worker.

## Applying this seat to another stack

- **Backend services and workers:** breakers and fallbacks, bulkheads, readiness and liveness, rolling deploys, watched dead-letter queues, alerts on what users feel.
- **Web frontends:** browser error reporting, version skew (a week-old tab calling a changed API), flags as kill switches.
- **Native mobile:** old versions live for years and can't be rolled back, so the server stays compatible and a minimum-version gate plus remote switches are the rollback path.
- **Desktop apps:** symbols archived per build, logs users can send, a verifying updater that survives interruption.
- **CLI tools:** meaningful exit codes, errors on stderr, `--dry-run` for destructive commands, config checked before work starts.
- **Embedded:** a watchdog fed from proof of main-loop progress, not a timer interrupt; A/B slots with boot-confirm and automatic revert for OTA.
- **Games:** crash reports with build and platform, saves loadable across patches, online services that fall back to offline play.
- **Ownership:** Backend (Collina) owns in-process quality, including structured logging as code hygiene; Performance owns speed; data integrity (Leach) owns migration correctness; Concurrency (Goetz) owns timeouts, cancellation, bounded queues and drain as code mechanics. This seat owns production behaviour and whether an operator can see and act on it: with Concurrency on the roster, a missing timeout is its finding, and whether it fits the caller's budget and what happens when it fires are this seat's; an error swallowed in code is Backend's, one never counted or alerted on is this seat's.

## Principle 1: Every integration point will fail

Every call that leaves the process (HTTP, database, cache, queue, cloud SDK, a device on a bus) will eventually hang, slow down or return garbage; *Release It!* catalogues what follows, from blocked threads to cascading failures. Every outbound call needs a timeout that fits its caller's budget, and a dependency that can hang or flap needs a breaker or a fallback so its failure stays its own.

### What to check

- No timeout, or one that doesn't fit the budget: a 60-second call inside a 30-second request, a connect timeout with no read timeout.
- A dependency that is clearly down still called on every request, each paying the full timeout.
- No cheap fallback: a recommendations call that fails the whole page instead of rendering without it.
- A peripheral polled with no timeout, so one silent device stalls the control loop.

### What not to flag

- In-process calls, or a single-user tool where a hang is plain to the one person waiting.
- Breakers for a dependency with one low-traffic caller, where a timeout is enough.
- A missing timeout when Concurrency is seated — its Principle 4 files it; file the budget mismatch and what happens when it fires.

## Principle 2: Failures must be visible

An error nobody can see hasn't been handled, only hidden. Errors are counted, logs carry the context to act on, work is measured for rate, errors and duration, and a request crossing a boundary carries an ID someone can follow.

### What to check

- Errors logged at debug level or never counted, so a failure rate climbing from 0.1% to 20% goes unnoticed.
- Log lines without request ID, tenant, dependency, status, duration or version.
- No correlation ID across service, queue and job boundaries (W3C Trace Context or OpenTelemetry where available, a request-ID header otherwise).
- Alerts on causes nobody can act on (CPU at 80%) but none on symptoms users feel: errors, latency, a scheduled job that silently stopped.

### What not to flag

- Logger choice, log format and in-process error handling (Backend's lens).
- Missing tracing where one process and one log file really are the whole system.

## Principle 3: Degrade instead of collapsing

When one part fails or is overloaded, the rest keeps working with less. Bulkheads stop one dependency, workload or tenant from taking every thread, connection or slot; load shedding refuses excess work early; kill switches turn a feature off without a deploy.

### What to check

- One pool for everything, so a slow report starves the checkout path.
- Overload met by accepting everything and serving nothing in time, where a 503 or 429 with Retry-After would keep the rest healthy.
- All-or-nothing responses where partial results are fine: a dashboard that dies because one widget timed out.
- Clients that spin when the backend is down instead of showing cached data; firmware with no safe state when a sensor goes silent.

### What not to flag

- Bulkheads or shedding in a single-user tool or a service with nothing to isolate.
- Kill switches for small, low-risk UI changes.

## Principle 4: Configuration is part of the program

Config changes production behaviour as surely as code, and skips review more often. Load it once at startup into a typed value, validate it and fail fast with a clear message; give each setting one source of truth and a safe default (or none, where guessing is dangerous), and keep secrets out of the repository.

### What to check

- Config read lazily deep in the code, so a missing value crashes the first request that needs it, hours after the deploy.
- Unsafe fallbacks when unset: a sandbox or wrong-environment endpoint, a zero or negative limit; the exposure from debug mode or open access is Security's — file the missing fail-fast here.
- One setting defined in several places with unclear precedence, or never validated (milliseconds read as seconds, a negative pool size).

### What not to flag

- Constants that don't vary by deployment.
- Secrets in the repo or a shipped binary (Security).
- A small tool reading a few environment variables directly, if it checks them at startup.

## Principle 5: Every deploy has a way back

Any release can be wrong, so every deploy needs an undo someone has tried. Changes that cross an interface (API, message format, schema, config key, save-file layout) go backward-compatible first and are cleaned up later (expand, then contract), so old and new versions can run side by side; interfaces that outlive a release carry a version.

### What to check

- New code that writes data the previous version can't read, so rollback is impossible.
- Breaking changes shipped in one step (a renamed field, a new enum value) while old clients, workers or queued messages use the old shape.
- Clients in the field that will call old APIs for years, with no version negotiation or minimum-version gate; saves and settings rewritten with no version marker.
- Rollback that exists only on paper, and big-bang releases where a flag or staged rollout would limit the blast radius.

### What not to flag

- Migration internals (locks, backfills, constraints), which are the data-integrity seat's.
- Interfaces private to one deployable that always ship together.

## Principle 6: Startup and shutdown are features

Clean start, stop and restart make deploys, scaling and crash recovery safe. A process reports ready only when it can serve, reports alive on its own health alone, leaves rotation before it drains, and restarts after a mid-operation crash without hand cleanup.

### What to check

- Ready reported before config, connections and caches load, so the first requests fail.
- Liveness that checks shared dependencies: one database blip restarts every instance at once.
- Readiness not withdrawn before draining, so traffic keeps reaching a closing instance; a drain longer than the platform's kill deadline.
- A crash that leaves a lock file or "in progress" flag blocking the next start; once-per-release work run by every instance at once.

### What not to flag

- Task ownership and in-code drain mechanics (Concurrency's lens).
- Separate liveness and readiness where the platform uses neither.

## Principle 7: Capacity is a design input

Every resource has a limit (memory, connections, file handles, disk, a partner's rate limit) and the code must decide what happens at it. Bound what you accept and return at the edge, size pools against what sits downstream, and give retries a budget across the fleet.

### What to check

- Unbounded work at the edge: a list endpoint with no page cap, an export built wholly in memory.
- Pools out of proportion with what they call: 50 instances × 20 connections against a database allowing 100 (*Release It!*'s unbalanced capacities).
- Retry storms with no jitter or budget: clients retrying in lockstep after an outage, or every service in a chain retrying a struggling dependency.
- Self-inflicted spikes: clients polling on the minute, caches expiring together, a push that sends every device to the API at once.

### What not to flag

- Hot-path speed (Performance), the query behind an unbounded result (data integrity), in-process queue and fan-out bounds, and one client's retry cap, backoff and jitter (Concurrency).
- Limits on inputs fixed by the domain, like a list of countries.

## Principle 8: Give operators handles

Something unanticipated will break, and someone will repair it mid-incident. Give them safe tools: rerunnable work, a way to replay failed batches and dead-lettered messages, dry-runs for destructive actions, and admin commands for common repairs, so nobody hand-edits production data.

### What to check

- Duplicated or failed work an operator can't find, replay or reconcile (no dead-letter queue, no failed-jobs record).
- Destructive scripts with no dry-run, confirmation or scope limit; routine fixes that need raw SQL on production.
- Field devices with no way to read the fault log or force recovery without a debugger.

### What not to flag

- Admin tooling where the developer is the operator and the data fits on one screen.
- Rerun safety for read-only work.

## Principle 9: Shipped software must be supportable

On machines you don't control (desktops, phones, consoles, devices in the field) you learn about failures only from what the software reports. It needs crash reports you can symbolicate, logs a user can find and send, the version in every report, and an updater that verifies what it installs and survives a bad release.

### What to check

- No crash reporting, or unreadable reports because the build's symbols (dSYM, PDB, R8 or ProGuard mappings) weren't archived.
- Reports without version, build and platform; logs users can't find, or that hold personal data so users won't send them.
- Updaters that brick on an interrupted download or can't recover from a bad release (signature checks: Untrusted input and Security).
- Silent exits on unhandled errors, and no remote way to disable a crashing feature.

### What not to flag

- Telemetry beyond what diagnosis needs; analytics and privacy are other lenses.
- Crash reporting for an internal tool whose few users can just say so.

## Know your gaps

- Infrastructure-as-code, clusters and CI/CD are in scope only where the reviewed code depends on them (a probe, a resource limit).
- SLO targets and incident process are organisational; this seat can say an alert is missing, not what the target should be.
- Distributed-systems correctness (consensus, exactly-once, clock skew) is beyond what review can prove; flag the assumption.

## Quick Reference: Severity Guide

- **P1 — Fix now:** a plausible outage, data loss or stuck fleet. No timeout on an integration point in a request path (when Concurrency isn't seated), liveness tied to a shared dependency, a release that writes data the old version can't read, a breaking interface change (renamed field, new enum value) shipped while old clients, workers or queued messages still use the old shape, an updater that can brick devices, config that falls back to a sandbox or wrong-environment endpoint, or a zero limit, when unset.
- **P2 — Fix soon:** silent or compounding failures. Errors never counted or alerted on, no correlation ID across a boundary, fleet-wide retries with no jitter or budget, readiness not withdrawn before drain, lazily read config, no fail-fast when an unset value means debug mode or open access, crash symbols not archived, an interface that outlives a release with no version marker or minimum-version gate.
- **P3 — Consider:** hygiene. Log lines missing context, a rarely used script with no dry-run, version missing from support logs.

## The Overriding Filter

Tell the production story: what fails, what users see, how anyone finds out, how they get back. If you can't tell it for this system's real traffic, fleet and history, it's pattern-matching. If you can, ask Carmack's question (a real problem in this codebase at this scale?) and let the blast radius set the severity.
