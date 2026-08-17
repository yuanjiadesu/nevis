# Scale constraints

Nevis targets 10,000 clients, 10–100 documents per client, and 10 KB of plain text per document on average. That is 100,000–1,000,000 documents and about 1.3–13 million chunks with the current window. Estimated PostgreSQL storage is 8–70 GB, subject to a representative load test.

## Know the unproven paths

The data model, tenant-leading indexes, bounded pagination, and durable indexing jobs fit this target. Two paths have no capacity evidence yet:

- Each worker indexes serially, but the queue supports safe worker replicas. More workers improve throughput only while the shared embedding service has spare capacity; they also use more database connections and memory. Local emulated embedding throughput is about six chunks per second.
- Semantic search scans every authorised chunk. `document_chunks` has no vector index, and the current materialized query cannot use one directly.

Do not claim support for the full target until staged tests measure indexing throughput, search p95, recall, and database size with representative text and embeddings.

The 50-client, 150-document UAT seed used about 2.8 GB on an Intel N100 with 4 cores and 16 GB RAM. Its original run did not record warm-up, so these figures describe that deployment rather than a reproducible benchmark:

| Concurrent searches | p95 |
| ---: | ---: |
| 1 | 187 ms |
| 2 | 415 ms |
| 3 | 533 ms |
| 5 | 1,055 ms |

The 800 ms target passed at three concurrent searches and failed at five. Four was not measured.

## Capacity gate

Test the low, midpoint, and high shapes with generated client identities and a real document corpus. Record:

- indexing chunks per second and recovery behavior
- lexical, semantic, and mixed-search p95
- relevance or recall at the configured candidate limits
- table and index size
- PostgreSQL query plans

If indexing misses its objective, test 2–4 worker replicas before changing the design. Increase embedding capacity only if the shared service saturates. Restructure semantic retrieval for an approximate vector index only if search misses its objective.

## Large-document cost

The local embedding runtime accepts at most 32 texts per request, so the worker batches larger documents. A 500,000-character document creates about 625 chunks and needs 20 sequential embedding requests. The job remains one atomic indexing transaction: a later provider failure stores no partial chunks, but the work and database transaction last longer.

Run the repository capacity harness and inspect query plans as described in the [operations runbook](runbook.md#diagnose-search-failures). [Performance](performance.md) is the how-to; do not treat a previous host table as a current measurement.
