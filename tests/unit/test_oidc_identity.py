import asyncio
from datetime import UTC, datetime

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from nevis.domain.identity import (
    IdentityCredentials,
    IdentityMode,
    IdentityProviderUnavailable,
    InvalidIdentity,
)
from nevis.infrastructure.identity import OIDCIdentityProvider
from tests.helpers.oidc import MutableClock, TestOIDCIssuer


def _provider(
    issuer: TestOIDCIssuer,
    clock: MutableClock | None = None,
) -> OIDCIdentityProvider:
    return OIDCIdentityProvider(
        issuer=issuer.issuer,
        audience=issuer.audience,
        algorithms=("RS256",),
        token_max_length=16_384,
        subject_max_length=200,
        clock_skew_seconds=0,
        fresh_ttl_seconds=10,
        max_stale_seconds=30,
        refresh_min_interval_seconds=1,
        timeout_seconds=1,
        response_max_bytes=100_000,
        client=issuer.client(),
        clock=clock or MutableClock(),
    )


@pytest.mark.asyncio
async def test_oidc_verifies_identity_and_ignores_authorization_claims() -> None:
    issuer = TestOIDCIssuer()
    issuer.add_key("key-1")
    provider = _provider(issuer)
    token = issuer.token(
        "key-1",
        claims={"tenant": "other", "roles": ["admin"], "groups": ["all"]},
    )

    identity = await provider.authenticate(IdentityCredentials(bearer_token=token))

    assert identity.external_id == "test-advisor"
    assert identity.mode is IdentityMode.OIDC
    assert len(identity.issuer_id) == 16


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "token_factory",
    [
        lambda issuer: issuer.token("key-1", remove=("exp",)),
        lambda issuer: issuer.token("key-1", remove=("sub",)),
        lambda issuer: issuer.token("key-1", claims={"iss": "https://wrong.example"}),
        lambda issuer: issuer.token("key-1", claims={"aud": "wrong-audience"}),
        lambda issuer: issuer.token("key-1", claims={"exp": 1}),
        lambda issuer: issuer.token(
            "key-1", claims={"nbf": int(datetime.now(UTC).timestamp()) + 3_600}
        ),
        lambda issuer: issuer.token("key-1", subject=""),
        lambda issuer: issuer.token("key-1", include_kid=False),
    ],
)
async def test_oidc_rejects_invalid_claims_and_headers(token_factory) -> None:
    issuer = TestOIDCIssuer()
    issuer.add_key("key-1")
    provider = _provider(issuer)

    with pytest.raises(InvalidIdentity):
        await provider.authenticate(IdentityCredentials(bearer_token=token_factory(issuer)))


@pytest.mark.asyncio
async def test_oidc_rejects_bad_signature_and_algorithm_without_leaking_token() -> None:
    issuer = TestOIDCIssuer()
    issuer.add_key("key-1")
    provider = _provider(issuer)
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    bad_signature = issuer.token("key-1", key=other_key)
    bad_algorithm = issuer.token("key-1", key="s" * 32, algorithm="HS256")

    for token in (bad_signature, bad_algorithm, "not-a-token"):
        with pytest.raises(InvalidIdentity) as caught:
            await provider.authenticate(IdentityCredentials(bearer_token=token))
        assert token not in str(caught.value)
        assert token not in repr(caught.value)


@pytest.mark.asyncio
async def test_oidc_rotates_keys_with_one_single_flight_refresh() -> None:
    issuer = TestOIDCIssuer()
    issuer.add_key("key-1")
    clock = MutableClock()
    provider = _provider(issuer, clock)
    await provider.authenticate(IdentityCredentials(bearer_token=issuer.token("key-1")))
    issuer.add_key("key-2")
    clock.value = 2
    token = issuer.token("key-2")
    before = issuer.jwks_requests

    identities = await asyncio.gather(
        *[provider.authenticate(IdentityCredentials(bearer_token=token)) for _ in range(5)]
    )

    assert {identity.external_id for identity in identities} == {"test-advisor"}
    assert issuer.jwks_requests == before + 1


@pytest.mark.asyncio
async def test_oidc_uses_bounded_stale_keys_then_fails_closed() -> None:
    issuer = TestOIDCIssuer()
    issuer.add_key("key-1")
    clock = MutableClock()
    provider = _provider(issuer, clock)
    credentials = IdentityCredentials(bearer_token=issuer.token("key-1"))
    await provider.authenticate(credentials)
    issuer.fail_requests = True

    clock.value = 20
    assert (await provider.authenticate(credentials)).external_id == "test-advisor"
    assert (await provider.healthcheck()).available

    clock.value = 31
    assert not (await provider.healthcheck()).available
    with pytest.raises(IdentityProviderUnavailable):
        await provider.authenticate(credentials)


@pytest.mark.asyncio
async def test_malformed_token_does_not_trigger_jwks_refresh() -> None:
    issuer = TestOIDCIssuer()
    issuer.add_key("key-1")
    provider = _provider(issuer)
    before = issuer.jwks_requests

    with pytest.raises(InvalidIdentity):
        await provider.authenticate(IdentityCredentials(bearer_token="malformed"))

    assert issuer.jwks_requests == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("discovery_issuer", "jwks_uri"),
    [
        ("https://wrong.example", "https://issuer.example/keys"),
        ("https://issuer.example", "http://issuer.example/keys"),
    ],
)
async def test_oidc_rejects_unsafe_discovery(discovery_issuer: str, jwks_uri: str) -> None:
    issuer = TestOIDCIssuer()
    issuer.add_key("key-1")
    issuer.discovery_issuer = discovery_issuer
    issuer.jwks_uri = jwks_uri
    provider = _provider(issuer)

    with pytest.raises(IdentityProviderUnavailable):
        await provider.authenticate(IdentityCredentials(bearer_token=issuer.token("key-1")))


@pytest.mark.asyncio
async def test_oidc_rejects_oversized_discovery_response() -> None:
    issuer = TestOIDCIssuer()
    issuer.add_key("key-1")

    def oversized(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 101, request=request)

    provider = OIDCIdentityProvider(
        issuer=issuer.issuer,
        audience=issuer.audience,
        algorithms=("RS256",),
        token_max_length=16_384,
        subject_max_length=200,
        clock_skew_seconds=0,
        fresh_ttl_seconds=10,
        max_stale_seconds=30,
        refresh_min_interval_seconds=1,
        timeout_seconds=1,
        response_max_bytes=100,
        client=httpx.AsyncClient(transport=httpx.MockTransport(oversized)),
    )

    with pytest.raises(IdentityProviderUnavailable):
        await provider.authenticate(IdentityCredentials(bearer_token=issuer.token("key-1")))
