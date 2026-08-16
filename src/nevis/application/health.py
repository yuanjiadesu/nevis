from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nevis.domain.embeddings import EmbeddingProvider
from nevis.domain.identity import IdentityProvider


@dataclass(frozen=True, slots=True)
class DependencyStatus:
    name: str
    available: bool


async def readiness(
    session_factory: async_sessionmaker[AsyncSession],
    provider: EmbeddingProvider,
    identity_provider: IdentityProvider | None = None,
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
    return all(status.available for status in statuses), statuses
