# Postgres Quality Reference — Carmack × Brandur × Prisma × Neon

Philosophy: John Carmack. Postgres expertise: Brandur Leach (Crunchy Data, ex-Stripe). ORM layer: Prisma documentation + community. Serverless Postgres: Neon documentation.

Every finding must describe the **concrete failure mode** — not just "this is bad practice."
Security patterns are in security.md (Hunt). Backend error handling is in quality-backend.md (Collina). Performance tuning is in quality-performance.md. This doc covers: data integrity, transaction safety, migration correctness, schema design, query correctness, and connection management.

---

## Applying this seat to another stack

The examples come from the origin stack: Prisma on Neon (serverless Postgres behind PgBouncer), called from Next.js / TypeScript / tRPC.

The numbered principles are the constraint set; framework-specific checks are illustrations. On another stack, find the analogous construct and apply the principle to it. Postgres detail stays in the principles (it holds on any Postgres project); Prisma and Neon detail is at the end.

| In the origin stack | The general idea | Look for it in … |
|---|---|---|
| `prisma migrate` | Generated migrations, reviewed before they run | Django or Alembic migrations; Rails migrations; EF Core migrations |
| Postgres CHECK / UNIQUE / FK | Invariants the store enforces | SQLite constraints (FKs need `PRAGMA foreign_keys = ON`); MongoDB `$jsonSchema` validators; a versioned save-file format |
| `$transaction` + isolation level | The atomic unit, and what concurrent writers see | SQLite `BEGIN IMMEDIATE`; MySQL InnoDB (REPEATABLE READ default); write-temp-then-rename |
| Postgres DDL lock levels | What a schema change blocks, for how long | MySQL online DDL; SQLite's table rebuild for `ALTER TABLE`; upgrading save files on load |
| Neon pooler, `connection_limit` | A scarce, bounded shared resource | SQLAlchemy `pool_size`; Go `SetMaxOpenConns`; SQLite's single writer |

Carrying the principles to SQLite, MySQL, document stores, embedded key-value stores, save files and caches:
- **1** Enforce what the store can (CHECK in SQLite and MySQL 8.0.16+, document validators); where it can't, validate every read and write in one place.
- **2** Find the real atomic unit (transaction, single-document write, write batch, temp-file rename); check-then-act races hit processes sharing a file or cache too.
- **3** Any change to stored shape is a migration — DDL, or a format version plus upgrade code. Old data must load; old readers must survive new data mid-rollout.
- **4** Whole-file loads and "load every key" are unbounded reads; NULL traps become missing-field and zero-value confusion.
- **5** Timezones, IDs, blobs, soft deletes and enum evolution apply to any format (renumbering a serialized enum corrupts old saves).
- **6** Pools, file handles, locks and cache clients are bounded; SQLite allows one writer at a time.
- **7** Write the override list for the project's own ORM, driver and store.

---

## Principle 1: Constraints are assertions — the database is the last line of defence

*Carmack: assertions catch assumption violations before they cause corruption.*
*Brandur: "Your database can and should act as a foundational substrate that offers your application profound leverage for fast and correct operation."*

Database constraints are the only safety layer that cannot be bypassed by any code path — not by raw SQL, not by other applications, not by future developers who don't read the docs, not by ORM bugs. The type system catches type errors at compile time. The ORM validates at the client. But only the database enforces invariants at the point of data entry.

Brandur: **"You can get away without constraints and schemas, but only by internalizing a nihilistic understanding that your production data isn't cohesive."**

### What to check

**Missing CHECK constraints**
- Prices that should be positive, quantities that should be non-negative, string lengths that have business limits. Without CHECK constraints, the database accepts any value the type allows.
- If the ORM can't declare CHECKs, add them by hand in the migration SQL: `ALTER TABLE "product" ADD CONSTRAINT "price_positive" CHECK (price > 0)`. Translate violation errors at the edge alongside other data-layer errors (see quality-backend.md).
- Severity: **P2** for business-critical fields (prices, quantities, statuses). **P3** for advisory constraints.

**Missing compound unique constraints**
- If `(tenantId, email)` isn't a compound UNIQUE, duplicate registrations are possible. No code path intends to create them, but under concurrent requests, they happen. This is the isolation level race that Brandur demonstrates — two transactions both check, both get empty, both insert.
- Severity: **P1** for business identity fields (tenant + email, user + workspace, org + slug). **P2** for non-critical uniqueness.

**Missing foreign key indexes**
- Postgres does NOT automatically index foreign key columns, and an ORM may create the FK without the index (Prisma's `@relation` does). Without the index, `DELETE` on a parent row triggers a sequential scan of the entire child table to verify no references exist. Real-world case: deleting 50k records took ~100ms with an index, ~30 minutes without — 10,000× slower.
- Fix: index every foreign key column.
- Severity: **P2** — works fine at small scale, catastrophic at production scale.

**NOT NULL discipline**
- Brandur: **"Nullable columns are literally the default in DDL — you'll get one unless you're really thinking about what you're doing and explicitly use NOT NULL."**
- Review every nullable field for a business reason. Every nullable column is unstructured state — NULL obeys three-valued logic that violates human intuition.
- Severity: **P3** for unnecessary nullable fields. **P2** if nullable fields are used in WHERE clauses or JOINs without NULL handling.

**Constraints as defence-in-depth for isolation level races**
- Even with SERIALIZABLE isolation, add UNIQUE constraints. Brandur: **"Although SERIALIZABLE will protect you from a duplicate insert, an added UNIQUE will act as one more check to protect your application against incorrectly invoked transactions or buggy code."**
- Two independent safety layers are always better than one.
- Severity: **P2** for relying solely on application logic for uniqueness.

---

## Principle 2: Transactions are the unit of correctness — understand what isolation buys you

*Carmack: if a race condition is syntactically possible, it will happen in production.*
*Brandur: "Transactions are really just a really good idea. Maybe the best idea in robust service design."*

### What to check

**Check-then-act patterns under READ COMMITTED**
- Postgres defaults to READ COMMITTED (so do Prisma's interactive transactions). Under this isolation, two interleaved transactions can both SELECT to check a condition, both see the same state, both proceed — violating the invariant that neither violated individually. This is write skew.
- Concrete example: two transactions both check if a user email exists, both get empty results, both INSERT — creating a duplicate even though each transaction correctly checked first.
- For check-then-act operations, escalate to SERIALIZABLE.
- SERIALIZABLE raises `ERROR: could not serialize access` on conflict. The application MUST catch and retry. Without retry logic, SERIALIZABLE transactions just fail.
- Severity: **P1** for financial operations, access control decisions, or any check-then-act on shared state. **P2** for other check-then-act patterns.

**Interactive transactions holding connections**
- A transaction wrapped around application code holds a connection for the whole callback. With a pool of one, all other queries are blocked.
- **The deadlock bug:** using the root client instead of the transaction handle inside the callback. It asks the pool for a connection while the transaction holds the only one — deadlock until the timeout.
- Rules: no network requests or slow processing inside a transaction. Always use the transaction handle. Prefer batched statements when no conditional logic is needed.
- Severity: **P1** for using the root client inside a transaction (guaranteed deadlock with a pool of one). **P2** for slow operations inside transactions.

**Side effects inside transactions — the outbox problem**
- Enqueueing a job INSIDE a transaction: the job may execute before the transaction commits, failing on data that doesn't exist yet.
- Enqueueing AFTER a transaction: the process may crash between commit and enqueue — data persists but the job is lost. Brandur: **"It's a problem that's far more nefarious; you almost certainly won't notice when it happens."**
- Fix: the transactionally staged job drain (outbox pattern). Insert a job record into a `staged_jobs` table within the same transaction as the data change. A separate enqueuer polls and forwards. Transactional isolation means the enqueuer can't see uncommitted jobs. Rollbacks discard the job with the data.
- Severity: **P2** for side effects (emails, webhooks, queue jobs) triggered inside or immediately after transactions. **P1** if the side effect involves money or external API mutations.

**Transaction duration**
- Long transactions prevent VACUUM from cleaning dead tuples. Dead rows accumulate, table bloat grows, all queries slow down. Brandur describes a production incident where an analytical query caused a job queue spike to 10,000+ jobs because dead rows couldn't be cleaned.
- Behind a transaction-mode pooler (Neon's PgBouncer), connections return only when a transaction ends. Long transactions hold scarce connections.
- Set `idle_in_transaction_session_timeout` to 10s and `statement_timeout` to 10s to kill zombie transactions.
- Severity: **P2** for transactions that could exceed a few seconds. **P1** for unbounded transaction duration (e.g., processing a file inside a transaction).

**Idempotency for foreign state mutations**
- When a request handler calls an external API (payment processor, email provider, webhook) inside a flow that also writes to the database, the external call is outside the ACID boundary. Brandur: **"Once we make our first foreign state mutation, we're committed one way or another. We've pushed data into a system beyond our own boundaries and we shouldn't lose track of it."**
- Even internal services count: **"It's tempting to treat emitting records to Kafka as part of atomic operations because they have such a high success rate that they feel like they are. They're not."**
- The idempotency key pattern: client sends a unique key, server records key + response, retries return the stored response. For the full atomic-phase pattern, you need raw SQL with SERIALIZABLE isolation.
- Severity: **P2** for external API calls without idempotency protection. **P1** for payment or financial mutations without idempotency.

---

## Principle 3: Migrations are production operations — every DDL has a lock cost

*Carmack: if it CAN lock a table, it WILL lock in production.*
*strong_migrations: classify operations as dangerous if they block reads/writes for more than a few seconds.*

Every schema change acquires a lock. The question is: which lock, and for how long?

### The lock reference

| Operation | Lock | Blocks reads? | Blocks writes? |
|---|---|---|---|
| `CREATE INDEX` (standard) | SHARE | No | **Yes** |
| `CREATE INDEX CONCURRENTLY` | SHARE UPDATE EXCLUSIVE | No | No |
| `ALTER TABLE ... SET NOT NULL` | ACCESS EXCLUSIVE | **Yes** | **Yes** |
| `ADD COLUMN ... DEFAULT` (Pg 11+, non-volatile) | ACCESS EXCLUSIVE (brief, metadata only) | Brief | Brief |
| `ALTER COLUMN TYPE` (rewrite) | ACCESS EXCLUSIVE | **Yes** | **Yes** |
| `DROP TABLE` / `TRUNCATE` | ACCESS EXCLUSIVE | **Yes** | **Yes** |
| `ADD FOREIGN KEY` (validating) | SHARE ROW EXCLUSIVE | No | **Yes (both tables)** |

### What to check

**Indexes created without CONCURRENTLY**
- A generated migration may use plain `CREATE INDEX` (Prisma's does), which blocks all writes for the duration of the index build. On a large table, this is minutes to hours of write downtime.
- Fix: rewrite it with `CONCURRENTLY`, alone in its migration — it can't run inside a transaction.
- Severity: **P1** on any table with significant data. **P3** on small reference tables.

**SET NOT NULL on existing columns**
- Making an existing column required generates `ALTER COLUMN ... SET NOT NULL`. This requires a full table scan with ACCESS EXCLUSIVE lock — blocks all reads AND writes while scanning every row to verify the constraint.
- Safe pattern: (1) add CHECK constraint without validation (`NOT VALID` — brief metadata lock), (2) validate separately (SHARE UPDATE EXCLUSIVE — allows reads and writes), (3) on Postgres 12+, `SET NOT NULL` skips the scan if a validated CHECK already proves it, (4) drop the CHECK.
- Severity: **P1** on tables with >100k rows. **P3** on small tables.

**Column drops without two-phase deploy**
- Removing a field from the schema can generate an immediate `ALTER TABLE DROP COLUMN`. During a rolling deploy, old instances still reference the column — runtime exceptions.
- Safe pattern: Phase 1 — remove the field from the ORM schema, deploy code that doesn't use the column. Phase 2 — after all instances run the new code, create and run the drop migration.
- Severity: **P2** in rolling deploy environments. **P3** if deploys are atomic (all instances swap simultaneously).

**Column renames — the generated-migration data loss trap**
- A schema-diffing tool may turn a rename into `DROP COLUMN` + `ADD COLUMN` — this DESTROYS the data in the column. Rewrite it to `ALTER TABLE RENAME COLUMN`.
- Brandur's alternative for table renames: rename the table, create an updatable view with the old name, deploy code using the new name, drop the view.
- Severity: **P1** — data loss.

**Type changes that cause table rewrites**
- Safe (metadata-only): `varchar(100)` → `varchar(200)`, `varchar(n)` → `text`, increasing decimal precision.
- Dangerous (full rewrite with ACCESS EXCLUSIVE): `integer` → `bigint` (4→8 bytes physical size change), `varchar` → `integer`, `text` → `integer`, `timestamp` → `date`.
- Generated migrations often emit a straight `ALTER COLUMN ... TYPE` — full rewrite for dangerous changes. Manual intervention required for large tables.
- Severity: **P1** for type changes on large tables. Check the Postgres docs for whether a specific conversion is metadata-only or requires a rewrite.

**Adding foreign keys without NOT VALID**
- Standard `ADD FOREIGN KEY` blocks writes on BOTH the source and target tables while validating all existing rows. Fix: add with `NOT VALID` (brief lock, no validation), then `VALIDATE CONSTRAINT` separately (allows reads and writes during validation).
- Severity: **P2** — blocks two tables simultaneously.

**Large backfills in a single statement**
- A single `UPDATE users SET col = 'default'` on a large table acquires row locks on all affected rows, generates massive WAL, and can cause replication lag.
- Fix: batch in groups of 1,000-10,000 rows with pauses between batches. Use `WHERE col IS NULL` for idempotency. Run outside a transaction.
- If the ORM has no built-in batching, batch by hand in raw SQL.
- Severity: **P2** for backfills on tables with >100k rows.

---

## Principle 4: Queries must be bounded, correct under NULL, and explicit about what they fetch

*Carmack: if an unbounded query is possible, someone will call it on a table with 500k rows.*
*Brandur: every SELECT * and every missing LIMIT is a ticking time bomb.*

### What to check

**Unbounded queries**
- A list query with no limit returns every row. Works with 100 rows in dev, causes OOM or timeout with 100k+ rows in production.
- Enforce a default limit centrally in the data layer, not per call site.
- Severity: **P2** for any unbounded list query on a table that could grow. **P1** on tables that already have significant data.

**SELECT * by default**
- An ORM read with no field list returns every column — including passwords, PII, large text/jsonb columns. Select what you need, or exclude sensitive fields.
- Cross-reference with quality-backend.md: output validation at the API provides a second layer against PII leaks.
- Severity: **P2** for queries returning user/billing models to the client without field filtering.

**NULL handling — three-valued logic traps**
- The NOT-with-NULL trap: `WHERE sentiment != 'NEGATIVE'`. In SQL, `NULL != 'NEGATIVE'` evaluates to `NULL` (not `TRUE`) — NULL rows are silently excluded from results.
- Know how the query builder treats a missing filter value versus an explicit null — one may silently drop the filter. This distinction is critical and non-obvious.
- `NOT IN` with NULLs: `WHERE id NOT IN (SELECT col FROM t)` returns NO rows if any subquery value is NULL. Use `NOT EXISTS` instead.
- Aggregation: `SUM` of no rows returns `NULL`, not `0`. Use `COALESCE(SUM(amount), 0)`.
- Severity: **P2** for NULL-related logic bugs in business queries. **P3** for cosmetic NULL issues.

**N+1 queries**
- The classic: a list query, then a per-row query in a loop. Fix: eager-load or join.
- Detection: enable query logging and look for repeated SELECT patterns.
- Severity: **P2** — performance degrades linearly with data size.

**Offset pagination under concurrent writes**
- Offset-based (`skip`/`take`): if a row is inserted before the current page, you see a duplicate on the next page. If deleted, you miss one. Offset also scans and discards all skipped rows.
- Cursor-based (Prisma's `cursor` API) uses `WHERE id > cursor` — consistent results, efficient at any depth.
- Severity: **P3** for admin/internal pages. **P2** for customer-facing paginated lists where duplicates or missing items are visible.

**Upsert race conditions**
- An ORM upsert may fall back to SELECT + INSERT/UPDATE — which is NOT atomic. Concurrent callers both attempt the INSERT; one hits a unique violation.
- Fix: for contended keys, use the native `INSERT...ON CONFLICT DO UPDATE`.
- Severity: **P2** for upserts on high-contention keys. **P3** for low-contention.

---

## Principle 5: Schema design choices compound — get them right from day one

*Carmack: minimise unstructured state. Every optional field, JSON blob, and soft delete is a liability.*
*Brandur: "For services that run in production, the better defined the schema and the more self-consistent the data, the easier life is going to be."*

### What to check

**Timestamps without timezone — the silent default**
- A timestamp WITHOUT time zone (an ORM's default type may be one). During DST transitions, the same wall clock time occurs twice. Without timezone info, it's ambiguous which one you meant.
- Fix: `TIMESTAMPTZ` for every timestamp from day one — it converts to UTC on storage, unambiguous. A store with no such type: store UTC and write the convention down.
- An ORM that converts to UTC before writing only partly helps: other tools reading the database directly won't know the values are UTC.
- Severity: **P2** — insidious. Works fine until you have users across timezones or hit a DST transition.

**IDs generated at ORM level instead of database level**
- IDs generated in the ORM client, not the database, leave the column with no DEFAULT. Inserts via raw SQL, other tools, or database migrations produce no ID.
- UUIDs stored as TEXT take 36 chars. UUIDv4 inserts at random B-tree positions — index bloat 26-27% larger than sequential inserts. Inserting 50M rows: UUIDv4 took 20 minutes vs UUIDv7's 1:46 minutes.
- Fix: generate IDs in the database and store them as native `uuid` (16 bytes); prefer sequential UUIDv7 where available.
- Severity: **P3** for ID generation location (advisory). **P2** for UUIDs stored as TEXT instead of native UUID type (storage and performance impact at scale).

**JSON columns for structured domain data**
- JSON fields have no constraints, no foreign keys, no type enforcement. (Prisma's `Json` is effectively `any` in TypeScript.) Brandur describes Heroku storing a JSON config blob: customers stored multi-megabyte payloads in a field with no size limit.
- Appropriate for: webhook payloads, user preferences, audit metadata — truly unstructured data.
- A schema design failure when: the data has a known shape, needs querying/joining/constraining, or represents core domain entities.
- Severity: **P2** for JSON columns storing structured domain data that should be relational. **P3** for JSON used appropriately.

**Soft delete — the invisible tax**
- Brandur: **"Soft deletion logic bleeds out into all parts of your code. Forgetting that extra predicate on deleted_at can have dangerous consequences."** And: **"As far as I'm aware, never once, in ten plus years, did anyone at any of these places ever actually use soft deletion to undelete something."** (Heroku, Stripe, Crunchy Data.)
- Soft-deleted records still occupy UNIQUE constraints — a user who deletes their account can't re-register with the same email. Partial unique indexes (`WHERE deleted_at IS NULL`) work, if the ORM lets you declare and use them.
- Foreign keys become advisory with soft delete — a "deleted" parent can still be referenced.
- Brandur's alternative: hard delete + a `deleted_record` archive table. Atomic delete-and-archive via CTE. Normal queries need no `deleted_at IS NULL` filter. FKs still work. GDPR purging is trivial.
- Severity: **P3** — this is architectural advice, not a bug. Escalate to **P2** if soft delete is causing query correctness issues (missing `WHERE deleted_at IS NULL` predicates).

**Enum types — adding is safe, removing is dangerous**
- `ALTER TYPE ... ADD VALUE` is safe but cannot run inside a transaction block. Removing or renaming enum values requires recreating the entire type — Prisma generates a complex sequence that has been a source of migration bugs (multiple GitHub issues).
- Alternative: lookup tables with FK constraints. Adding/removing values is INSERT/DELETE. Can add metadata. FK ensures validity. Easier migrations.
- Severity: **P3** — use enums for truly stable value sets (status codes, roles). Use lookup tables for values that change.

---

## Principle 6: Connections are scarce — pool, bound and release them

*Carmack: understand the lifecycle of every resource you allocate.*
*Neon: PgBouncer in transaction mode, connection limits are hard constraints.*

### What to check

**Not using the connection pooler**
- Without a pooler, every client connection is a Postgres backend capped by `max_connections`. With many short-lived processes, connection exhaustion is guaranteed at any meaningful scale.
- Migrations and admin tools use the direct (non-pooled) connection. Application code uses the pooled connection.
- Severity: **P1** for serverless or many-process application code connecting directly without the pooler.

**Pool size not set for serverless**
- Every instance gets its own client pool, typically several connections. 200 concurrent functions × 5 connections = 1,000 connections, exceeding Postgres limits.
- Fix: one connection per serverless instance. Error symptoms: pool-acquire timeouts, "too many connections for role".
- Severity: **P1** for serverless deployments with a multi-connection pool per instance.

**Timeouts not configured for cold starts**
- A database that scales to zero takes time to wake, and a default connect timeout may be shorter. Fix: raise the connect and pool timeouts to cover it.
- Severity: **P2** — affects first requests after idle periods. At moderate scale the database likely stays active during business hours.

**Session-level features through the pooler**
- Behind a transaction-mode pooler (Neon's PgBouncer), session-level features don't work: `SET`, `LISTEN/NOTIFY`, temporary tables, `WITH HOLD CURSOR`, and session-level advisory locks (`pg_advisory_lock`).
- Use transaction-level advisory locks (`pg_advisory_xact_lock`) instead — they release when the transaction ends.
- Severity: **P1** for session-level advisory locks through the pooler (silently broken). **P2** for other session features.

---

## Principle 7: Know your data layer's defaults — ORM and driver defaults are rarely production-safe

*Carmack: if the default is dangerous and changing it requires manual intervention, every new developer will hit the default.*

Keep a master checklist of every ORM, driver and store default that needs a manual override for production correctness: timestamp types, index creation mode, FK indexes, CHECK support, NOT NULL changes, drops and renames, pool size, connect timeout, unbounded reads, field selection, ID type, partial unique indexes, upsert atomicity. The origin checklist (Prisma on Neon) is at the end.

Severity follows the damage: **P1** when the default loses data, locks a large table, or exhausts connections; **P2** when it degrades correctness at scale; **P3** for hygiene.

### The overriding migration review rule

Every generated migration must be reviewed before deployment. For any migration that touches an existing table with data, generate it without applying it (Prisma: `--create-only`) and read the SQL. Check against the lock reference table in Principle 3. If the migration acquires ACCESS EXCLUSIVE or SHARE locks on a table with significant data, rewrite it.

---

## Gaps: What This Doc Doesn't Cover

- **Security patterns**: SQL injection, access control, IDOR, secrets. Covered by **security.md (Hunt)**.
- **Backend error handling**: data-layer error leakage to clients, error formatting, retry logic. Covered by **quality-backend.md (Collina)**.
- **Performance tuning**: `EXPLAIN ANALYZE`, index type selection (B-tree, GIN, GiST), partitioning, VACUUM tuning, query planner statistics. This is a correctness doc, not a DBA guide.
- **Enterprise scale**: Read replicas, sharding, multi-region, logical replication. At early stage, premature.
- **Postgres administration**: `pg_stat_statements`, backup strategies, user/role management, `pg_repack`. Out of scope for code review.
- **ORM comparisons**: The doc works with the project's ORM, not against it.

---

## Quick Reference: Severity Guide

| Severity | Pattern | Examples |
|----------|---------|----------|
| **P1 — Fix Now** | Data loss, data corruption, guaranteed production incidents | Column renames via DROP+ADD, `SET NOT NULL` on large tables, non-concurrent index creation on large tables, the root client instead of the transaction handle inside a transaction, missing pooler connection, multi-connection pools per serverless instance, session advisory locks through a transaction-mode pooler, missing compound uniques on business identity fields |
| **P2 — Fix Soon** | Correctness bugs that compound or manifest at scale | READ COMMITTED for check-then-act, side effects inside transactions, long transaction duration, unbounded queries, SELECT * returning PII, NULL logic bugs, timestamps without timezone, missing FK indexes, missing CHECK constraints, upsert race conditions, soft delete correctness issues, offset pagination on customer-facing lists |
| **P3 — Consider** | Schema hygiene and architectural guidance | ORM-level ID generation, JSON for appropriate use cases, enum vs lookup table choice, unnecessary nullable fields, cursor pagination on internal pages, CUID deprecation |

### The Overriding Filter

Before writing any finding, apply the Carmack-Brandur synthesis:

1. **Is there a database constraint that could enforce this invariant?** If yes and it's missing, flag it. The constraint is the assertion. (Brandur: the database is the foundational substrate.)
2. **Can this migration lock a production table?** If yes, check the lock type and table size. If ACCESS EXCLUSIVE on a table with data, the migration must be rewritten. (Carmack: if it CAN lock, it WILL.)
3. **Is this query bounded?** No limit on a list query, no field list on sensitive data, no NULL handling in WHERE clauses — flag it. (Both: unbounded operations are ticking time bombs.)
4. **Does this transaction hold a scarce connection?** With a pool of one (Neon with `connection_limit=1`), every interactive transaction blocks all other queries. Keep transactions short. (Both: understand the lifecycle of every resource.)
5. **Is the ORM's default safe here?** ORM defaults (Prisma's included) are optimised for developer experience, not production correctness. Check the override list (Principle 7). (Carmack: if the default is wrong and requires manual intervention, every new developer will hit the default.)

---

## Origin-stack examples (Prisma / Neon / Next.js / TypeScript / tRPC)

### Principle 1 — Prisma constraints
- No native CHECK constraints (GitHub #3388, 286+ upvotes): add them with `prisma migrate dev --create-only` and edit the SQL. Violations surface as `PrismaClientUnknownRequestError`, not a typed code — translate them in tRPC middleware.
- `@@unique` declares compound uniques; named ones enable `findUnique` with compound keys: `@@unique(fields: [userId, workspaceId], name: "membership_key")`.
- Fields without `?` are NOT NULL — Prisma gets this right; review every `?`.

### Principle 2 — Prisma transactions on Neon
- Escalating to SERIALIZABLE:
  ```typescript
  await prisma.$transaction(async (tx) => { /* ... */ }, {
    isolationLevel: Prisma.TransactionIsolationLevel.Serializable,
  });
  ```
- `$transaction(async (tx) => {})` holds a connection for the whole callback; with a one-connection pool on Neon (`connection_limit=1` in Prisma 6, the adapter's `max: 1` in 7), all other queries wait. Using `prisma` instead of `tx` inside it deadlocks until the 5s timeout, then `P2028: Transaction already closed`. Batch transactions (`$transaction([q1, q2])`) don't hold a connection. The atomic-phase idempotency pattern needs `$queryRaw`.

### Principle 3 — Prisma migrations
- No `CREATE INDEX CONCURRENTLY` by default (GitHub #14456): `npx prisma migrate dev --create-only`, add `CONCURRENTLY`, and keep it the ONLY statement in the file — Prisma wraps multi-statement migrations in a transaction.
- Removing `?` generates `SET NOT NULL`; a type change generates a straight `ALTER COLUMN ... TYPE`; backfills need `$executeRaw` with manual batching.

### Principle 4 — Prisma queries
- A default `take` via Client Extension:
  ```typescript
  const prisma = new PrismaClient().$extends({
    query: {
      $allModels: {
        findMany({ args, query }) {
          args.take = args.take ?? 100;
          return query(args);
        },
      },
    },
  });
  ```
- `omit` excludes sensitive fields (Preview as `omitApi` from 5.13.0, generally available since 6.2.0).
- `{ sentiment: { not: 'NEGATIVE' } }` generates `WHERE sentiment != 'NEGATIVE'`. `undefined` in a `where` is a no-op — the filter is silently omitted; `null` filters for `IS NULL`.
- N+1: use `include`, or `relationLoadStrategy: 'join'` for a single LATERAL JOIN (Preview since 5.7.0 on PostgreSQL; still needs `previewFeatures = ["relationJoins"]`). Same-tick `findUnique()` calls auto-batch into `WHERE id IN (...)` — scalar equality filters only, not `findMany()` or relation filters. Log queries with `new PrismaClient({ log: ['query'] })`.
- Upsert is native `INSERT...ON CONFLICT` only with no nested queries, a single model, a single unique field, and matching `where`/`create` values; otherwise SELECT + INSERT/UPDATE. With `update: {}`, a concurrent caller hits `P2002: Unique constraint failed`; a non-empty `update` (e.g. set the same value) forces `ON CONFLICT`.

### Principle 5 — Prisma schema types
- Prisma converts `DateTime` to UTC before writing, which other tools can't know.
- `@default(cuid())` and `@default(uuid())` generate IDs in the client; `uuid()` stores UUIDv4 as TEXT. Fix: `@default(dbgenerated("gen_random_uuid()")) @db.Uuid`; on Postgres 18 or later, `dbgenerated("uuidv7()")` for time-ordered IDs. CUID v1 is deprecated by its creator due to security concerns (leaks creation time and host fingerprint).
- Partial unique indexes need raw SQL, and Prisma can't use `findUnique`/`upsert` with them.

### Principle 6 — Neon connections (Prisma 6 and earlier, unless noted)
- On Neon, **P1** for any application code on the direct host instead of the `-pooler` host.
- Neon's `-pooler` hostname runs PgBouncer in transaction mode, supporting up to 10,000 concurrent client connections; direct, you get `max_connections` (104 on the smallest compute). Prisma CLI and migrations use the direct connection.
- Prisma's default pool is `num_physical_cpus * 2 + 1` (typically 5+), and each serverless invocation creates its own PrismaClient. Symptom: "Timed out fetching a new connection from the connection pool".
- Neon auto-suspends idle computes after 5 minutes by default; activation takes 500ms to a few seconds, and Prisma's default `connect_timeout` (5s) may be exceeded (`P1001: Can't reach database server`).

**Recommended connection string:**
```env
DATABASE_URL="postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/dbname?sslmode=require&connection_limit=1&connect_timeout=15&pool_timeout=15"
DIRECT_URL="postgresql://user:pass@ep-xxx.region.aws.neon.tech/dbname?sslmode=require"
```

Prisma 7 ignores those URL parameters: set the pool on the driver adapter —
`new PrismaPg({ connectionString, max: 1, connectionTimeoutMillis: 15_000 })` — and put the CLI's
direct URL in `prisma.config.ts` (`datasource.url`).

### Principle 7 — Prisma's defaults on Neon (Prisma 6 and earlier; v7 noted where it differs)

| What Prisma Does | What You Need | How to Fix | Severity |
|---|---|---|---|
| `TIMESTAMP(3)` for DateTime | `TIMESTAMPTZ(6)` | Add `@db.Timestamptz(6)` | P2 |
| `CREATE INDEX` (blocks writes) | `CREATE INDEX CONCURRENTLY` | `--create-only`, edit SQL, single statement per migration | P1 |
| No FK indexes | `@@index([fkField])` | Add manually to every relation | P2 |
| No CHECK constraints | Raw SQL in migrations | `--create-only`, edit migration | P2 |
| `SET NOT NULL` via full table scan | CHECK constraint pattern | `--create-only`, edit migration | P1 |
| Immediate `DROP COLUMN` | Two-phase deploy | Manual deploy coordination | P2 |
| `DROP + ADD` for renames | `RENAME COLUMN` | `--create-only`, edit migration | P1 |
| ~5 connection pool | a one-connection pool | `connection_limit=1` URL parameter (v6) / adapter `max: 1` (v7) | P1 |
| 5s connect timeout (v7's `pg` adapter: none) | 15s for Neon cold starts | URL parameter (v6) / adapter `connectionTimeoutMillis` (v7) | P2 |
| Unbounded `findMany` | Default `take` | Client Extension | P2 |
| All fields returned | Explicit `select` or `omit` | Per-query discipline | P2 |
| `cuid()`/`uuid()` as TEXT | `@db.Uuid` with `dbgenerated()` | Schema change | P3 |
| No partial unique indexes | Raw SQL | `--create-only`, edit migration | P2 |
| Upsert may not be atomic | Raw `ON CONFLICT` for critical paths | `$executeRaw` | P2 |
