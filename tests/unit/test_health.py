from collections.abc import AsyncIterator

import pytest

from nevis.application.health import readiness
from nevis.domain.embeddings import EmbeddingProfileIdentity, ProviderHealth
from nevis.domain.identity import IdentityMode, IdentityProviderHealth


class HealthyProvider:
    profile = EmbeddingProfileIdentity("fake", "fixture", "1", 8, "l2", 1, 1)

    async def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(True, "fake")


class UnhealthyProvider(HealthyProvider):
    async def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(False, "fake")


class FailingSessionFactory:
    def __call__(self) -> AsyncIterator[object]:
        raise ConnectionError


class UnhealthyIdentityProvider:
    mode = IdentityMode.OIDC

    async def authenticate(self, credentials):  # pragma: no cover - health fixture only
        raise AssertionError

    async def healthcheck(self) -> IdentityProviderHealth:
        return IdentityProviderHealth(False, self.mode)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_readiness_reports_unavailable_dependencies() -> None:
    available, statuses = await readiness(FailingSessionFactory(), UnhealthyProvider())  # type: ignore[arg-type]

    assert not available
    assert {status.name: status.available for status in statuses} == {
        "database": False,
        "embedding_provider": False,
    }


@pytest.mark.asyncio
async def test_readiness_includes_configured_identity_provider() -> None:
    available, statuses = await readiness(
        FailingSessionFactory(),  # type: ignore[arg-type]
        UnhealthyProvider(),
        UnhealthyIdentityProvider(),
    )

    assert not available
    assert {status.name: status.available for status in statuses} == {
        "database": False,
        "embedding_provider": False,
        "identity_provider": False,
    }
