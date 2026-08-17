import pytest

from nevis.domain.identity import IdentityCredentials, IdentityMode, InvalidIdentity
from nevis.infrastructure.identity import (
    DeterministicIdentityProvider,
    LocalHeaderIdentityProvider,
)
from nevis.settings import Settings


@pytest.mark.asyncio
async def test_local_header_identity_is_bounded() -> None:
    provider = LocalHeaderIdentityProvider(subject_max_length=8)

    identity = await provider.authenticate(IdentityCredentials(local_advisor_external_id="advisor"))

    assert identity.external_id == "advisor"
    assert identity.mode is IdentityMode.LOCAL_HEADER
    with pytest.raises(InvalidIdentity):
        await provider.authenticate(IdentityCredentials())
    with pytest.raises(InvalidIdentity):
        await provider.authenticate(IdentityCredentials(local_advisor_external_id="too-long-id"))


@pytest.mark.asyncio
async def test_deterministic_identity_ignores_transport_credentials() -> None:
    provider = DeterministicIdentityProvider("fixed-advisor")

    identity = await provider.authenticate(IdentityCredentials(bearer_token="ignored"))

    assert identity.external_id == "fixed-advisor"
    assert identity.mode is IdentityMode.DETERMINISTIC


@pytest.mark.parametrize(
    ("environment", "provider"),
    [
        ("local", "deterministic"),
        ("local", "oidc"),
        ("test", "local-header"),
        ("production", "local-header"),
        ("production", "deterministic"),
    ],
)
def test_environment_rejects_wrong_identity_provider(environment: str, provider: str) -> None:
    with pytest.raises(ValueError, match="identity provider"):
        Settings(
            _env_file=None,
            environment=environment,  # type: ignore[arg-type]
            identity_provider=provider,  # type: ignore[arg-type]
            search_cursor_signing_key="x" * 32,
            oidc_issuer="https://issuer.example",
            oidc_audience="nevis-api",
        )


def test_production_requires_complete_safe_oidc_settings() -> None:
    with pytest.raises(ValueError, match="OIDC issuer"):
        Settings(
            _env_file=None,
            environment="production",
            search_cursor_signing_key="x" * 32,
        )
    with pytest.raises(ValueError, match="OIDC audience"):
        Settings(
            _env_file=None,
            environment="production",
            search_cursor_signing_key="x" * 32,
            oidc_issuer="https://issuer.example",
        )
    with pytest.raises(ValueError, match="algorithms"):
        Settings(
            _env_file=None,
            environment="production",
            search_cursor_signing_key="x" * 32,
            oidc_issuer="https://issuer.example",
            oidc_audience="nevis-api",
            oidc_algorithms=("HS256",),
        )
