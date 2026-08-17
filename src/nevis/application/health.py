from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nevis.domain.embeddings import EmbeddingProvider
from nevis.domain.identity import IdentityProvider
from nevis.domain.reranking import RerankerProvider
from nevis.domain.summarization import summary_capability_hash
from nevis.infrastructure.summary_repository import get_runtime_capability
from nevis.settings import Settings


@dataclass(frozen=True, slots=True)
class DependencyStatus:
    name: str
    available: bool


async def readiness(
    session_factory: async_sessionmaker[AsyncSession],
    provider: EmbeddingProvider,
    identity_provider: IdentityProvider | None = None,
    reranker_provider: RerankerProvider | None = None,
    settings: Settings | None = None,
) -> tuple[bool, list[DependencyStatus]]:
    database_available = False
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        database_available = True
    except Exception:  # readiness must not leak connection details
        database_available = False
    provider_health = await provider.healthcheck()
    statuses = [
        DependencyStatus(name="database", available=database_available),
        DependencyStatus(name="embedding_provider", available=provider_health.available),
    ]
    if identity_provider is not None:
        try:
            identity_health = await identity_provider.healthcheck()
            identity_available = identity_health.available
        except Exception:  # readiness must not leak identity dependency details
            identity_available = False
        statuses.append(DependencyStatus(name="identity_provider", available=identity_available))
    required_available = all(status.available for status in statuses)
    if reranker_provider is not None:
        try:
            reranker_health = await reranker_provider.healthcheck()
            reranker_available = reranker_health.available
        except Exception:  # optional dependency has an explicit degraded mode
            reranker_available = False
        statuses.append(DependencyStatus(name="reranker_provider", available=reranker_available))
    if settings is not None and settings.document_summaries_enabled:
        summary_worker_available = False
        if database_available:
            try:
                async with session_factory() as session:
                    heartbeat = await get_runtime_capability(session, "summary-worker")
                expected_hash = summary_capability_hash(
                    enabled=True,
                    provider=settings.llm_provider,
                    model=settings.llm_model,
                    prompt_version=settings.document_summary_prompt_version,
                )
                cutoff = datetime.now(UTC) - timedelta(
                    seconds=settings.summary_worker_heartbeat_freshness_seconds
                )
                summary_worker_available = bool(
                    heartbeat is not None
                    and heartbeat.enabled
                    and heartbeat.identity_hash == expected_hash
                    and heartbeat.heartbeat_at >= cutoff
                )
            except Exception:
                summary_worker_available = False
        statuses.append(DependencyStatus(name="summary_worker", available=summary_worker_available))
        required_available = required_available and summary_worker_available
    return required_available, statuses
