# Keep the service honest

Nevis is not production. This page is the smallest SRE contract: what we measure, what must be true before real client data, and what we will not build yet.

## Measure three things

An SLI is good events over total events. Compare runs only with [matching context](performance.md).

| Signal | Good event | Starting objective |
| --- | --- | --- |
| Search latency | One-pass `hybrid` page faster than 800 ms | 99% over four weeks |
| Search mode | Page is `hybrid` | Watch `lexical_degraded` and `hybrid_unreranked`; do not hide them |
| Index freshness | Current version is searchable | 99% within 15 minutes while TEI is up |

`lexical_degraded` is a quality miss, not a 5xx. Database or audit failure is an availability miss: return nothing.

If an objective is missed, stop ranking, model, and schema changes until it recovers. There is no SLO platform. `make eval` and `make bench` plus `/health/ready` are enough to start.

## Real data needs these first

Do not load a real client until all five exist:

1. Production browser identity (no shared `local-advisor`)
2. Delete, retain, and export one client, including chunks and summaries
3. A Postgres backup you have restored
4. Replay a failed indexing job without creating a new version
5. The three signals above, with no query, content, email, or vector in logs

Summaries stay off for non-fictional data. They send full document text to a remote model.

## Kill toil before adding platforms

Failed jobs are terminal. `mangabox` is a file copy. There is no restore drill. Fix those before Kubernetes, a second vector store, or multi-region.

Do not page on every health flap. Page when search stays degraded, the index queue ages, or restore is untested and a disk is dying.

## Capacity

Do not claim 10,000 clients. Measure representative text first; tune Postgres first; add an approximate vector index only if search misses 800 ms. See [Scale constraints](scale-constraints.md).

The [roadmap](roadmap.md#work-starts-when) says when other product work may start. This page is only the reliability gate.
