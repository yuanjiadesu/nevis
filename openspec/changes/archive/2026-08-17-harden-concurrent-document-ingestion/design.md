## Context

See `proposal.md` for motivation. Ingestion already runs in one PostgreSQL transaction and enforces uniqueness, but it reads idempotency and version state before writing. The database can therefore reject valid concurrent work after both transactions pass their reads.

## Goals / Non-Goals

**Goals:**

- Serialize requests that share an idempotency key or logical document
- Preserve current API outcomes and transaction boundaries
- Prove behavior with real PostgreSQL concurrency tests

**Non-Goals:**

- General distributed locking
- Retry middleware
- New queues, outboxes, dependencies, or schema objects

## Decisions

### Use transaction-scoped PostgreSQL advisory locks

At the start of the ingestion transaction, acquire two namespaced locks in a fixed order:

1. Tenant and idempotency key
2. Tenant, source reference, and external document identifier

PostgreSQL releases both locks on commit or rollback. The second transaction then repeats the existing reads against committed state.

Row locking cannot cover the first version because no document row exists yet. Serializable isolation would require broader retry handling. Advisory locks keep the change local and require no migration.

### Keep uniqueness constraints as the final guard

Existing unique constraints remain authoritative. The application maps any ingestion uniqueness conflict that escapes serialization to the existing replay or `409` behavior.

## Risks / Trade-offs

- [Requests for one logical document run sequentially] → The lock scope matches the version sequence that already requires ordering
- [Hash collisions serialize unrelated requests] → Namespace lock inputs and accept rare extra waiting; collisions do not change data
- [PostgreSQL-specific behavior] → Nevis already requires PostgreSQL and pgvector
