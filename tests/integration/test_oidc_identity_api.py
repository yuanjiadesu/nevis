import os
import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog.testing import capture_logs

from nevis.domain.embeddings import EmbeddingProfileIdentity
from nevis.domain.identity import (
    IdentityCredentials,
    IdentityMode,
    IdentityProviderHealth,
    IdentityProviderUnavailable,
)
from nevis.infrastructure.embeddings import DeterministicFakeProvider
from nevis.infrastructure.identity import OIDCIdentityProvider
from nevis.infrastructure.models import (
    Advisor,
    AdvisorTenantMembership,
    AuthorizationDecisionRecord,
    Tenant,
)
from nevis.main import create_app
from nevis.settings import Settings
from nevis.workers.main import process_indexing_once
from tests.helpers.oidc import MutableClock, TestOIDCIssuer


def _profile() -> EmbeddingProfileIdentity:
    return EmbeddingProfileIdentity("fake", "fixture", "1", 384, "l2", 1, 1)


class CountingFakeProvider(DeterministicFakeProvider):
    def __init__(self, profile: EmbeddingProfileIdentity) -> None:
        super().__init__(profile)
        self.query_calls = 0

    async def embed_query(self, text: str) -> list[float]:
        self.query_calls += 1
        return await super().embed_query(text)


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="production",
        database_url=os.environ["NEVIS_TEST_DATABASE_URL"],
        search_cursor_signing_key="x" * 32,
        search_semantic_candidate_threshold=-1.0,
        oidc_issuer="https://issuer.example",
        oidc_audience="nevis-api",
        oidc_jwks_fresh_ttl_seconds=30,
        oidc_jwks_max_stale_seconds=60,
        oidc_jwks_refresh_min_interval_seconds=1,
    )


def _oidc_provider(
    issuer: TestOIDCIssuer, client: httpx.AsyncClient, clock: MutableClock
) -> OIDCIdentityProvider:
    settings = _settings()
    assert settings.oidc_issuer is not None
    assert settings.oidc_audience is not None
    return OIDCIdentityProvider(
        issuer=settings.oidc_issuer,
        audience=settings.oidc_audience,
        algorithms=settings.oidc_algorithms,
        token_max_length=settings.oidc_token_max_length,
        subject_max_length=settings.oidc_subject_max_length,
        clock_skew_seconds=settings.oidc_clock_skew_seconds,
        fresh_ttl_seconds=settings.oidc_jwks_fresh_ttl_seconds,
        max_stale_seconds=settings.oidc_jwks_max_stale_seconds,
        refresh_min_interval_seconds=settings.oidc_jwks_refresh_min_interval_seconds,
        timeout_seconds=settings.oidc_http_timeout_seconds,
        response_max_bytes=settings.oidc_response_max_bytes,
        client=client,
        clock=clock,
    )


@pytest.mark.asyncio
async def test_production_oidc_protects_all_routes_and_preserves_lineage(
    database_session_factory: async_sessionmaker[AsyncSession],
    authorized_context,
    client_id,
) -> None:
    del authorized_context
    issuer = TestOIDCIssuer()
    issuer.add_key("key-1")
    identity_http = issuer.client()
    clock = MutableClock()
    identity_provider = _oidc_provider(issuer, identity_http, clock)
    embedding_provider = CountingFakeProvider(_profile())
    app = create_app(_settings(), identity_provider=identity_provider)
    app.state.session_factory = database_session_factory
    app.state.embedding_provider = embedding_provider
    transport = httpx.ASGITransport(app=app)
    token = issuer.token("key-1", claims={"tenant": "attacker-tenant", "roles": ["super-admin"]})
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Nevis-Tenant": "nevis-global",
        "X-Nevis-Advisor": "spoofed-advisor",
        "Idempotency-Key": "oidc-ingestion-1",
    }
    payload = {
        "source_reference": "oidc-api",
        "external_document_id": "oidc-document",
        "title": "OIDC protected document",
        "content": "Pension planning with protected identity",
    }

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            ready = await client.get("/health/ready")
            assert ready.status_code == 200
            assert ready.json()["dependencies"]["identity_provider"] is True

            accepted = await client.post(
                f"/v1/clients/{client_id}/documents", json=payload, headers=headers
            )
            assert accepted.status_code == 202
            assert await process_indexing_once(database_session_factory, embedding_provider)
            version_id = accepted.json()["document_version_id"]

            status_response = await client.get(
                f"/v1/document-versions/{version_id}", headers=headers
            )
            assert status_response.status_code == 200
            search = await client.get("/search", params={"q": "pension planning"}, headers=headers)
            assert search.status_code == 200
            assert search.json()["results"][0]["type"] == "document"
            provenance = search.json()["results"][0]["provenance"]
            assert provenance["document_version_id"] == version_id
            assert set(provenance) == {
                "tenant_id",
                "client_id",
                "source_id",
                "document_id",
                "document_version_id",
                "embedding_profile_id",
                "indexing_authorization_decision_id",
                "search_authorization_decision_id",
            }

            missing = await client.get(
                "/search", params={"q": "pension"}, headers={"X-Nevis-Tenant": "nevis-global"}
            )
            assert missing.status_code == 401
            assert missing.headers["www-authenticate"] == "Bearer"
            query_calls_before_denial = embedding_provider.query_calls
            with capture_logs() as logs:
                invalid = await client.get(
                    "/search",
                    params={"q": "pension"},
                    headers={
                        "Authorization": "Bearer invalid-token",
                        "X-Nevis-Tenant": "nevis-global",
                    },
                )
            assert invalid.status_code == 401
            assert token not in invalid.text
            assert embedding_provider.query_calls == query_calls_before_denial
            assert "invalid-token" not in str(logs)

            unknown_subject = issuer.token("key-1", subject="unknown-oidc-subject")
            unknown = await client.get(
                "/search",
                params={"q": "pension"},
                headers={
                    "Authorization": f"Bearer {unknown_subject}",
                    "X-Nevis-Tenant": "nevis-global",
                },
            )
            assert unknown.status_code == 403
            assert unknown_subject not in unknown.text

            async with database_session_factory() as session:
                async with session.begin():
                    advisor = await session.scalar(
                        select(Advisor).where(Advisor.external_id == "test-advisor")
                    )
                    tenant = await session.scalar(
                        select(Tenant).where(Tenant.slug == "nevis-global")
                    )
                    assert advisor is not None
                    assert tenant is not None
                    membership = await session.scalar(
                        select(AdvisorTenantMembership).where(
                            AdvisorTenantMembership.advisor_id == advisor.id,
                            AdvisorTenantMembership.tenant_id == tenant.id,
                        )
                    )
                    assert membership is not None
                    membership.is_active = False
            inactive = await client.get("/search", params={"q": "pension"}, headers=headers)
            assert inactive.status_code == 403
            async with database_session_factory() as session:
                async with session.begin():
                    membership = await session.scalar(
                        select(AdvisorTenantMembership).where(
                            AdvisorTenantMembership.advisor_id == advisor.id,
                            AdvisorTenantMembership.tenant_id == tenant.id,
                        )
                    )
                    assert membership is not None
                    membership.is_active = True

            without_tenant = await client.get(
                "/search",
                params={"q": "pension"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert without_tenant.status_code == 401
            unknown_tenant = await client.get(
                "/search",
                params={"q": "pension"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Nevis-Tenant": "does-not-exist",
                },
            )
            assert unknown_tenant.status_code == 403

            suffix = uuid.uuid4().hex
            async with database_session_factory() as session:
                async with session.begin():
                    advisor = await session.scalar(
                        select(Advisor).where(Advisor.external_id == "test-advisor")
                    )
                    assert advisor is not None
                    other_tenant = Tenant(slug=f"oidc-other-{suffix}", name="OIDC other")
                    session.add(other_tenant)
                    await session.flush()
                    session.add(
                        AdvisorTenantMembership(
                            advisor_id=advisor.id,
                            tenant_id=other_tenant.id,
                        )
                    )
            isolated = await client.get(
                "/search",
                params={"q": "pension"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Nevis-Tenant": other_tenant.slug,
                },
            )
            assert isolated.status_code == 200
            assert isolated.json()["results"] == []

            issuer.add_key("key-2")
            clock.value = 2
            rotated_token = issuer.token("key-2")
            rotated_headers = {
                "Authorization": f"Bearer {rotated_token}",
                "X-Nevis-Tenant": "nevis-global",
            }
            rotated = await client.get(
                "/search", params={"q": "pension planning"}, headers=rotated_headers
            )
            assert rotated.status_code == 200
            rotated_provenance = rotated.json()["results"][0]["provenance"]
            for field in (
                "tenant_id",
                "client_id",
                "source_id",
                "document_id",
                "document_version_id",
                "embedding_profile_id",
                "indexing_authorization_decision_id",
            ):
                assert rotated_provenance[field] == provenance[field]

            issuer.fail_requests = True
            clock.value = 40
            cached_during_outage = await client.get(
                "/search", params={"q": "pension planning"}, headers=rotated_headers
            )
            assert cached_during_outage.status_code == 200
            cached_ready = await client.get("/health/ready")
            assert cached_ready.status_code == 200

            clock.value = 63
            stale_expired = await client.get(
                "/search", params={"q": "pension planning"}, headers=rotated_headers
            )
            assert stale_expired.status_code == 503
            assert rotated_token not in stale_expired.text
            stale_ready = await client.get("/health/ready")
            assert stale_ready.status_code == 503
            assert stale_ready.json()["dependencies"]["identity_provider"] is False

        async with database_session_factory() as session:
            decisions = list(
                (
                    await session.scalars(
                        select(AuthorizationDecisionRecord).order_by(
                            AuthorizationDecisionRecord.occurred_at
                        )
                    )
                ).all()
            )
            oidc_decisions = [
                decision
                for decision in decisions
                if decision.context.get("identity_mode") == "oidc"
            ]
            assert oidc_decisions
            assert all(
                len(decision.context["identity_issuer_id"]) == 16 for decision in oidc_decisions
            )
            assert all(
                "subject" not in str(decision.context).lower() for decision in oidc_decisions
            )
            assert any(decision.result == "deny" for decision in oidc_decisions)
    finally:
        await identity_http.aclose()


class UnavailableIdentityProvider:
    mode = IdentityMode.OIDC

    async def authenticate(self, credentials: IdentityCredentials):
        del credentials
        raise IdentityProviderUnavailable

    async def healthcheck(self) -> IdentityProviderHealth:
        return IdentityProviderHealth(False, self.mode)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_production_identity_unavailability_is_credential_safe(
    database_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    app = create_app(_settings(), identity_provider=UnavailableIdentityProvider())
    app.state.session_factory = database_session_factory
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/search",
            params={"q": "pension"},
            headers={"Authorization": "Bearer secret-token", "X-Nevis-Tenant": "nevis-global"},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "identity unavailable"}
    assert "secret-token" not in response.text
