"""Rollback-only representative exact-search benchmark for PostgreSQL."""

import asyncio
import json
import os
import statistics
import time
import uuid

from sqlalchemy import text

from nevis.infrastructure.database import build_engine, build_session_factory
from nevis.infrastructure.repositories import (
    search_exact_email_clients,
    search_exact_name_clients,
    search_lexical_candidates,
    search_lexical_clients,
    search_semantic_candidates,
)
from nevis.settings import get_settings

DOCUMENTS = int(os.getenv("NEVIS_BENCHMARK_DOCUMENTS", "100000"))
CLIENTS = int(os.getenv("NEVIS_BENCHMARK_CLIENTS", "10000"))
ITERATIONS = int(os.getenv("NEVIS_BENCHMARK_ITERATIONS", "20"))
TARGET_MS = float(os.getenv("NEVIS_SEARCH_P95_TARGET_MS", "800"))


async def benchmark() -> None:
    engine = build_engine(get_settings().database_url)
    sessions = build_session_factory(engine)
    async with sessions() as session:
        transaction = await session.begin()
        try:
            tenant_id = await session.scalar(
                text("SELECT id FROM tenants WHERE slug = 'nevis-global'")
            )
            profile_id = await session.scalar(
                text("SELECT id FROM embedding_profiles WHERE is_active LIMIT 1")
            )
            decision_id = await session.scalar(
                text(
                    "SELECT id FROM authorization_decisions "
                    "WHERE tenant_id = :tenant_id AND result = 'allow' LIMIT 1"
                ),
                {"tenant_id": tenant_id},
            )
            assert tenant_id and profile_id and decision_id
            await session.execute(
                text(
                    "INSERT INTO clients "
                    "(id, tenant_id, first_name, last_name, email, normalized_email, "
                    "description, social_links, source_type, source_reference, "
                    "creation_authorization_decision_id) "
                    "SELECT ('10000000-0000-0000-0000-' || lpad(n::text, 12, '0'))::uuid, "
                    ":tenant_id, 'Benchmark', n::text, "
                    "'benchmark-' || n || '@example.test', "
                    "'benchmark-' || n || '@example.test', "
                    "CASE WHEN n % 2 = 0 THEN 'retirement income specialist' "
                    "ELSE 'inheritance trust specialist' END, '[]'::jsonb, "
                    "'benchmark', 'benchmark-' || n, :decision_id "
                    "FROM generate_series(1, :client_count) AS n"
                ),
                {
                    "tenant_id": tenant_id,
                    "decision_id": decision_id,
                    "client_count": CLIENTS,
                },
            )
            source_id = uuid.uuid5(uuid.NAMESPACE_URL, "nevis-search-benchmark-source")
            await session.execute(
                text(
                    "INSERT INTO document_sources (id, tenant_id, source_reference) "
                    "VALUES (:id, :tenant_id, :reference) ON CONFLICT DO NOTHING"
                ),
                {"id": source_id, "tenant_id": tenant_id, "reference": "benchmark-rollback"},
            )
            vector = "[" + ",".join(["0.051031"] * 384) + "]"
            fixture_parameters = {
                "tenant_id": tenant_id,
                "source_id": source_id,
                "profile_id": profile_id,
                "decision_id": decision_id,
                "document_count": DOCUMENTS,
                "client_count": CLIENTS,
                "vector": vector,
            }
            await session.execute(
                text(
                    "INSERT INTO documents "
                    "(id, tenant_id, client_id, source_id, external_document_id, title) "
                    "SELECT md5('nevis-benchmark-document-' || n)::uuid, :tenant_id, "
                    "('10000000-0000-0000-0000-' || "
                    "lpad(((n % :client_count) + 1)::text, 12, '0'))::uuid, :source_id, "
                    "'benchmark-' || n, "
                    "CASE WHEN n % 100 = 0 THEN 'retirement pension planning ' || n "
                    "ELSE 'estate trust tax ' || n END "
                    "FROM generate_series(0, :document_count - 1) AS n"
                ),
                fixture_parameters,
            )
            await session.execute(
                text(
                    "INSERT INTO document_versions "
                    "(id, tenant_id, source_id, document_id, version_number, content, "
                    "content_hash, authorization_policy, authorization_result, "
                    "authorization_decision_id) "
                    "SELECT md5('nevis-benchmark-version-' || n)::uuid, :tenant_id, :source_id, "
                    "md5('nevis-benchmark-document-' || n)::uuid, 1, "
                    "CASE WHEN n % 100 = 0 "
                    "THEN 'Synthetic retirement pension planning evidence ' "
                    "ELSE 'Synthetic estate trust tax evidence ' END || n, repeat('a', 64), "
                    "'tenant-membership-v1', 'allow', :decision_id "
                    "FROM generate_series(0, :document_count - 1) AS n"
                ),
                fixture_parameters,
            )
            await session.execute(
                text(
                    "INSERT INTO indexing_jobs "
                    "(id, tenant_id, source_id, document_id, document_version_id, "
                    "embedding_profile_id, authorization_policy, authorization_result, "
                    "authorization_decision_id, status, attempt_count) "
                    "SELECT md5('nevis-benchmark-job-' || n)::uuid, :tenant_id, :source_id, "
                    "md5('nevis-benchmark-document-' || n)::uuid, "
                    "md5('nevis-benchmark-version-' || n)::uuid, :profile_id, "
                    "'tenant-membership-v1', 'allow', :decision_id, 'completed', 1 "
                    "FROM generate_series(0, :document_count - 1) AS n"
                ),
                fixture_parameters,
            )
            await session.execute(
                text(
                    "INSERT INTO document_chunks "
                    "(id, tenant_id, source_id, document_id, document_version_id, "
                    "embedding_profile_id, authorization_policy, authorization_result, "
                    "authorization_decision_id, chunking_version, ordinal, start_offset, "
                    "end_offset, content, content_hash, embedding) "
                    "SELECT md5('nevis-benchmark-chunk-' || n)::uuid, :tenant_id, :source_id, "
                    "md5('nevis-benchmark-document-' || n)::uuid, "
                    "md5('nevis-benchmark-version-' || n)::uuid, :profile_id, "
                    "'tenant-membership-v1', 'allow', :decision_id, 1, 0, 0, 64, "
                    "CASE WHEN n % 100 = 0 "
                    "THEN 'Synthetic retirement pension planning evidence ' "
                    "ELSE 'Synthetic estate trust tax evidence ' END || n, repeat('b', 64), "
                    "CAST(:vector AS vector) "
                    "FROM generate_series(0, :document_count - 1) AS n"
                ),
                fixture_parameters,
            )
            await session.flush()
            await session.execute(
                text(
                    "ANALYZE clients, documents, document_versions, indexing_jobs, document_chunks"
                )
            )

            timings: list[float] = []
            branch_timings: dict[str, list[float]] = {
                "client_email": [],
                "client_name": [],
                "client_lexical": [],
                "document_lexical": [],
                "document_semantic": [],
            }
            for _ in range(ITERATIONS):
                started = time.perf_counter()
                branch_started = time.perf_counter()
                await search_exact_email_clients(
                    session,
                    tenant_id=tenant_id,
                    query="benchmark-42@example.test",
                )
                branch_timings["client_email"].append(
                    (time.perf_counter() - branch_started) * 1_000
                )
                branch_started = time.perf_counter()
                await search_exact_name_clients(
                    session,
                    tenant_id=tenant_id,
                    query="Benchmark 42",
                    limit=100,
                )
                branch_timings["client_name"].append((time.perf_counter() - branch_started) * 1_000)
                branch_started = time.perf_counter()
                await search_lexical_clients(
                    session,
                    tenant_id=tenant_id,
                    query="retirement specialist",
                    limit=100,
                )
                branch_timings["client_lexical"].append(
                    (time.perf_counter() - branch_started) * 1_000
                )
                branch_started = time.perf_counter()
                await search_lexical_candidates(
                    session,
                    tenant_id=tenant_id,
                    profile_id=profile_id,
                    query="retirement pension",
                    limit=100,
                    snippet_length=280,
                )
                branch_timings["document_lexical"].append(
                    (time.perf_counter() - branch_started) * 1_000
                )
                branch_started = time.perf_counter()
                await search_semantic_candidates(
                    session,
                    tenant_id=tenant_id,
                    profile_id=profile_id,
                    embedding=[0.051031] * 384,
                    threshold=-1.0,
                    limit=100,
                    snippet_length=280,
                )
                branch_timings["document_semantic"].append(
                    (time.perf_counter() - branch_started) * 1_000
                )
                timings.append((time.perf_counter() - started) * 1_000)
            p95 = statistics.quantiles(timings, n=100, method="inclusive")[94]
            print(
                json.dumps(
                    {
                        "clients": CLIENTS,
                        "documents": DOCUMENTS,
                        "iterations": ITERATIONS,
                        "p50_ms": round(statistics.median(timings), 2),
                        "p95_ms": round(p95, 2),
                        "branch_p95_ms": {
                            name: round(
                                statistics.quantiles(values, n=100, method="inclusive")[94],
                                2,
                            )
                            for name, values in branch_timings.items()
                        },
                        "target_ms": TARGET_MS,
                    },
                    sort_keys=True,
                )
            )
            if p95 > TARGET_MS:
                raise RuntimeError("representative exact-search p95 exceeds target")
        finally:
            await transaction.rollback()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(benchmark())
