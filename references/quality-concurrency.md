# Concurrency & Runtime Reference — Carmack × Goetz

Philosophy: John Carmack. Concurrency expertise: Brian Goetz (lead author of *Java Concurrency in Practice*). This seat reviews correctness wherever more than one thing runs at once — threads, async/await, goroutines, actors, worker pools, queues, signal and interrupt handlers, a game's job system. Its bugs pass the tests, then surface under load as corrupt data, double charges or hangs nobody can reproduce.

"This isn't thread-safe" is the easiest finding to pattern-match, so the Carmack filter bites hard: a real finding shows both actors really run at once in this codebase. A one-worker queue, or a loop with no suspension point in the gap, does not race with itself. Concurrency is a protected subject, so each finding gets its own blind verifier; an interleaving it can't trace won't survive.

## When this seat applies

Anywhere two or more units of execution share state or order-dependent effects, including processes racing over one file or queue. Example surface markers:

- **Services and workers:** `go func`, `asyncio.create_task`, `threading.Lock`, `Promise.all`, `ExecutorService`, `tokio::spawn`; `**/workers/**`, `**/consumers/**`, Celery `@shared_task`, BullMQ `Worker`.
- **Mobile and desktop:** `DispatchQueue`, `@MainActor`, `viewModelScope`, `runOnUiThread`, `Dispatcher.Invoke`, `QThread`.
- **Games:** Unity `IJob`, `NativeArray`; Godot `Thread`, `WorkerThreadPool`, `call_deferred`; Unreal `AsyncTask`, `FRunnable`.
- **Embedded and systems:** `ISR(`, `volatile`, `xTaskCreate`, `xSemaphoreTake`, `sigaction`, `pthread_`, `std::atomic`.

Drop the seat only for truly sequential code. Pair it with Backend when the concurrency is a few awaits in request handlers; give it its own worker for shared caches, consumers, schedulers, locks, shutdown, or ISR and job-system code.

## Applying this seat to another stack

- **Web:** one thread, many interleavings — stale responses overwriting newer ones, double submits; `AbortController` for cancellation.
- **Backend:** shared caches and singletons, fan-out, deadlines, at-least-once consumers, draining on deploy, instances racing on one key.
- **Mobile and desktop:** UI-thread affinity (`@MainActor`, Android's main thread, WPF's Dispatcher, Qt); work cancelled with its screen.
- **CLI:** bounded worker pools; Ctrl-C that cleans up temp files and child processes; a non-zero exit when background work failed.
- **Embedded:** ISR-shared state, RTOS priorities and inversion, what an interrupt may call.
- **Games:** main thread versus workers, main-thread-only engine APIs, job dependencies, async loads outliving their scene.

Ownership: Backend (Collina) owns in-service code quality, event-loop blocking and stream backpressure; data integrity (Leach) owns transaction isolation; Performance owns throughput; Operability (Nygard) owns production startup, shutdown and capacity — readiness, drain, limits set against what sits downstream. This seat owns the in-code mechanics under them — task lifecycle, fire-and-forget tasks, cancellation propagation, bounded fan-out (Backend's without this seat) — and correctness when things run at once: races in memory, across queues and between processes, and unbounded queues because they fail, not because they're slow. With Operability seated, whether a timeout fits the caller's budget, and what happens when it fires, are Operability's.

## Principle 1: Shared mutable state is the hazard

A race needs state that is shared, mutable and uncoordinated; remove any one and it's gone. Goetz's three remedies — don't share it, make it immutable, or synchronise every access — hold for goroutines, actors and ISRs too. When you guard, use one lock and write down what it covers.

### What to check
- Globals, singletons, caches and ISR-shared variables written by concurrent handlers, workers or interrupts.
- Plain collections mutated from several threads (a Go `map`, a Java `HashMap`, a Python dict updated in compound steps).
- Fields locked on some paths and read bare on others; no note (`@GuardedBy`, "guarded by mu") of which lock covers what.
- Mutable objects handed to another task while the sender keeps using them; compiler escape hatches (`@unchecked Sendable`, `unsafe impl Sync`).

### What not to flag
- State written once before any concurrent reader starts.
- State confined to one thread, task or actor — that's Principle 2's question.

## Principle 2: Every await, yield or thread hop is a point where the world can change

Between checking a condition and acting on it, another task can change it. In async code the gap is every `await`, `yield` or callback, even in single-threaded runtimes and actors; in threaded code it is anywhere. Check-then-act and read-modify-write across such a gap are races unless made atomic.

### What to check
- Check-then-act across a gap: "if missing, create", "if the balance covers it, withdraw", lazy init with no once-guard, a cache miss that stampedes the backend.
- Read-modify-write with an await between read and write (the lost update); actor state trusted after an `await` (Swift actor reentrancy).
- A response to an old query overwriting a newer one; a callback writing into a dismissed screen.
- Lock files and paths checked, then opened, without an atomic exclusive create.

### What not to flag
- A check-then-act where nothing else can change the state in between.
- A harmless, self-correcting race (two identical cache fills) — P3 at most.

## Principle 3: Ordering must be established, never assumed

Two events happen in a known order only if something makes them: a lock, a join, a channel, an atomic with the right memory ordering, a sequence number. Without that happens-before edge, a write on one thread may never be seen on another. Messages arrive late, twice or out of order, so at-least-once handlers must be idempotent.

### What to check
- Hand-offs through plain fields: a Java `boolean` without `volatile`, a non-atomic C++ flag, broken double-checked locking.
- Code assuming async work finishes in start order, or that messages on different queues or partitions keep send order.
- Consumers and retried jobs with no idempotency key; ack before the work is durable, or after side effects with no dedup.
- Wall-clock time used to order events across machines (use a sequence number, version or logical clock) or to measure durations (use a monotonic clock).

### What not to flag
- Ordering the platform guarantees and the code relies on correctly (a serial queue, FIFO within one partition).
- Documented at-most-once handlers where loss is acceptable (metrics).

## Principle 4: Cancellation and timeouts are part of the contract

Every wait on something outside your control needs a bound. When a caller gives up, the work it started should stop, and cleanup must still run. Cancellation is cooperative in most runtimes, as Goetz's treatment of Java interruption stresses, so code that never checks for it, or swallows it, can't be stopped.

### What to check
- Waits with no timeout: an HTTP client left at its default (Python `requests` and Go's zero-value `http.Client` have none), a promise that may never settle.
- A context, `CancellationToken` or `AbortSignal` accepted but not passed down; children still running after the parent timed out.
- Cancellation swallowed: `InterruptedException` caught without restoring the interrupt; Python `CancelledError` caught by bare `except:` or `except BaseException` and not re-raised; Kotlin `CancellationException` caught by `catch (e: Exception)` or `runCatching`; .NET `OperationCanceledException` caught by `catch (Exception)`.
- Locks, files and child processes released only on success, not in `finally`, `defer`, `using` or `with`.

### What not to flag
- Deliberately unbounded waits (an accept loop, a worker awaiting its next job) that shutdown can interrupt.
- Short, local, bounded work with no cancellation hook.

## Principle 5: Bound everything

Every queue, pool, buffer, fan-out and retry loop needs a limit and a decision about what happens at it: block the producer, shed load or fail fast. Unbounded growth fails far from the bug, as memory exhaustion, a thread storm or a downstream outage.

### What to check
- Fan-out over input-sized lists (`Promise.all`, `asyncio.gather`, a goroutine per item) with no limit (`p-limit`, `errgroup.SetLimit`, a semaphore).
- Unbounded queues and executors (Java's `newCachedThreadPool` adds threads without limit; `newFixedThreadPool` queues without limit).
- Retries in one client with no cap, backoff or jitter.
- Producers that never slow down; work dropped at a limit with no log or metric.

### What not to flag
- Fan-out over a small fixed set (three parallel config reads).
- The exact limit chosen, when one exists and is sane — tuning is Performance's.
- Retry budgets across services or the fleet (Operability).

## Principle 6: Never block a thread or loop you don't own

The UI thread draws and takes input, an event loop serves every caller, a game's main thread must finish its frame, an interrupt must return fast. Blocking one on I/O, a lock, a sleep or heavy compute freezes everything behind it. Hand the work to a worker; return results the owner's way.

### What to check
- Synchronous network, disk or database calls on a UI thread (Android reports ANRs; StrictMode can flag them) or a game's main thread.
- UI or engine APIs called off their thread without hopping back (`@MainActor`, `runOnUiThread`, `Dispatcher.Invoke`, `call_deferred`).
- Async code that blocks anyway: `.Result` or `.Wait()`, `time.sleep` in `async def`, `runBlocking` on the main thread.
- Signal handlers and ISRs that allocate, log, lock or call anything not async-signal-safe.

### What not to flag
- Blocking inside a server's own event loop — the Backend seat owns it.
- Brief, bounded synchronous work on the owning thread (a small config read at startup).

## Principle 7: Lock discipline

Locks fail two ways: taken in different orders on different paths (deadlock), or held while slow or unknown code runs (stalls, or deadlock if it wants the same lock). Take them in one documented order and hold them briefly: never hold a blocking lock across an await, and never hold any lock across a slow or unbounded call. Call foreign code as what *Java Concurrency in Practice* calls an open call — with no lock held.

### What to check
- Two paths that take the same locks in opposite order, counting row locks and blocking channel sends.
- A blocking lock (`std::sync::Mutex`, `parking_lot`, `threading.Lock`, `synchronized`) held across `await`, or any lock held across unbounded I/O, `sleep` or callbacks (Clippy's `await_holding_lock` catches the std and parking_lot cases).
- A non-reentrant mutex re-acquired on the same path; a lock not released on an error path.
- RTOS priority inversion: a binary semaphore used as a mutex (in FreeRTOS only mutexes get priority inheritance).

### What not to flag
- One lock, a tiny critical section, no nesting.
- Correct but unfamiliar lock-free code — ask for a comment unless you have an interleaving.
- An async-aware lock (`tokio::sync::Mutex`, `asyncio.Lock`, Kotlin `Mutex`, `SemaphoreSlim.WaitAsync`) held across an await to serialise an I/O resource.

## Principle 8: Lifecycle is explicit

Every background thing — thread, task, goroutine, timer, subscription, consumer — needs an owner that starts it, can stop it and waits for it. Shutdown stops new work, drains in-flight work within a deadline, then releases resources. Fire-and-forget work is where errors go to die.

### What to check
- Fire-and-forget: `asyncio.create_task` with no reference kept, un-awaited promises, `go func()` with no error path, C# `async void`, `GlobalScope.launch`.
- Leaks: goroutines blocked on a channel no one closes, timers never cleared, listeners never removed.
- No graceful shutdown: SIGTERM unhandled, in-flight jobs not drained, `os.Exit` skipping deferred cleanup; start called twice running two loops.
- Work not cancelled when its view or scene is torn down (`lifecycleScope`, `OnDestroy`, `_exit_tree`); task groups or `errgroup` available but unused.

### What not to flag
- Short-lived CLIs where process exit is the cleanup and nothing partial is left behind.
- Documented daemon threads whose loss at exit is harmless.

## Principle 9: Make concurrency testable

Concurrency bugs depend on timing, so tests on real clocks and schedulers miss them or flake. Code that takes its clock and scheduler as dependencies can be driven step by step. Where the stack has a race detector, concurrent paths should run under it.

### What to check
- Timeouts, retries and expiry with no clock seam — prefer an injected clock or fake timers (`kotlinx-coroutines-test`, Jest, Sinon).
- Tests that `sleep` and hope instead of awaiting a latch or signal.
- Race tooling unused where it exists: `go test -race`, ThreadSanitizer for C, C++ and Swift, `loom` for Rust, `jcstress` on the JVM.
- Concurrent paths never tested concurrently: two workers on one queue, two requests on one record, a cancel mid-operation.

### What not to flag
- No race-detector run on code with no shared state.
- Test quality in general — the Tests seat (Beck) owns it.

## Know your gaps

- Lock-free algorithms and memory-model detail: this seat spots misuse but can't prove a lock-free structure correct.
- Distributed consensus, clock sync and exactly-once across services; only idempotency and ordering basics are here.
- GPU parallelism and hard real-time schedulability are out of scope.
- Code shows which interleavings are possible, not how often. When a finding hinges on timing you can't show, mark it UNCERTAIN and say what would reproduce it.

## Quick Reference: Severity Guide

- **P1 — wrong result, lost or duplicated data, a hang or a crash:** a check-then-act race on money, stock or permissions (Principle 2); a consumer that double-charges on redelivery (Principle 3); a reachable lock-order deadlock (Principle 7); unguarded concurrent map writes (Principle 1); a frozen UI thread; locking in an ISR; a call with no timeout that can hang the only worker.
- **P2 — silent failure or a landmine:** fire-and-forget tasks whose errors vanish; unbounded fan-out on user-sized input; no graceful shutdown for a worker; swallowed cancellation; a blocking lock held across an await; any lock held across unbounded I/O; tests that sleep instead of synchronising.
- **P3 — clarity:** missing "guarded by" notes on correct code; an unusual primitive with no explanation; a timeout with no stated reason.

## The Overriding Filter

Name the interleaving: two actors that really run at once in this codebase, the shared thing, the order of steps, the wrong result.
If you can't write that sentence, it's pattern-matching — drop it.
If you can, it's probably the most expensive bug in the review, because nobody will reproduce it on demand.
