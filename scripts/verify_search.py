"""Exercise authorized hybrid search and cross-tenant isolation in Compose."""

import asyncio
import hashlib
import json
import time
import urllib.parse
import urllib.request

from sqlalchemy import select

from nevis.infrastructure.database import build_engine, build_session_factory
from nevis.infrastructure.models import (
    Advisor,
    AdvisorTenantMembership,
    AuthorizationDecisionRecord,
    Document,
    DocumentSource,
    DocumentVersion,
    EmbeddingProfile,
    IndexingJob,
    Tenant,
)
from nevis.settings import get_settings


async def provision_other_tenant() -> tuple[str, str]:
    tenant_slug = "compose-other-tenant"
    advisor_external_id = "compose-other-advisor"
    engine = build_engine(get_settings().database_url)
    sessions = build_session_factory(engine)
    try:
        async with sessions() as session, session.begin():
            tenant = await session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
            if tenant is None:
                tenant = Tenant(slug=tenant_slug, name="Compose other tenant")
                session.add(tenant)
                await session.flush()
            advisor = await session.scalar(
                select(Advisor).where(Advisor.external_id == advisor_external_id)
            )
            if advisor is None:
                advisor = Advisor(external_id=advisor_external_id)
                session.add(advisor)
                await session.flush()
            membership = await session.scalar(
                select(AdvisorTenantMembership).where(
                    AdvisorTenantMembership.tenant_id == tenant.id,
                    AdvisorTenantMembership.advisor_id == advisor.id,
                )
            )
            if membership is None:
                session.add(AdvisorTenantMembership(tenant_id=tenant.id, advisor_id=advisor.id))
    finally:
        await engine.dispose()
    return tenant_slug, advisor_external_id


async def provision_legacy_unassociated_document() -> str:
    engine = build_engine(get_settings().database_url)
    sessions = build_session_factory(engine)
    try:
        async with sessions() as session, session.begin():
            tenant = await session.scalar(select(Tenant).where(Tenant.slug == "nevis-global"))
            assert tenant is not None
            existing = await session.scalar(
                select(Document).where(
                    Document.tenant_id == tenant.id,
                    Document.external_document_id == "legacy-unassociated-v1",
                )
            )
            if existing is not None:
                version = await session.scalar(
                    select(DocumentVersion)
                    .where(DocumentVersion.document_id == existing.id)
                    .order_by(DocumentVersion.version_number.desc())
                    .limit(1)
                )
                assert version is not None
                return str(version.id)
            profile = await session.scalar(
                select(EmbeddingProfile).where(EmbeddingProfile.is_active.is_(True))
            )
            decision = await session.scalar(
                select(AuthorizationDecisionRecord)
                .where(
                    AuthorizationDecisionRecord.tenant_id == tenant.id,
                    AuthorizationDecisionRecord.result == "allow",
                )
                .order_by(AuthorizationDecisionRecord.occurred_at.desc())
                .limit(1)
            )
            assert profile is not None and decision is not None
            source = await session.scalar(
                select(DocumentSource).where(
                    DocumentSource.tenant_id == tenant.id,
                    DocumentSource.source_reference == "legacy-smoke",
                )
            )
            if source is None:
                source = DocumentSource(tenant_id=tenant.id, source_reference="legacy-smoke")
                session.add(source)
                await session.flush()
            document = Document(
                tenant_id=tenant.id,
                client_id=None,
                source_id=source.id,
                external_document_id="legacy-unassociated-v1",
                title="Legacy unassociated archive",
            )
            session.add(document)
            await session.flush()
            content = "Legacy unassociated compliance archive evidence."
            version = DocumentVersion(
                tenant_id=tenant.id,
                source_id=source.id,
                document_id=document.id,
                version_number=1,
                content=content,
                content_hash=hashlib.sha256(content.encode()).hexdigest(),
                authorization_policy=decision.policy,
                authorization_result=decision.result,
                authorization_decision_id=decision.id,
            )
            session.add(version)
            await session.flush()
            session.add(
                IndexingJob(
                    tenant_id=tenant.id,
                    source_id=source.id,
                    document_id=document.id,
                    document_version_id=version.id,
                    embedding_profile_id=profile.id,
                    authorization_policy=decision.policy,
                    authorization_result=decision.result,
                    authorization_decision_id=decision.id,
                    status="queued",
                    attempt_count=0,
                )
            )
            return str(version.id)
    finally:
        await engine.dispose()


def api_request(path: str, tenant: str, advisor: str) -> dict[str, object]:
    request = urllib.request.Request(
        f"http://127.0.0.1:8000{path}",
        headers={"X-Nevis-Tenant": tenant, "X-Nevis-Advisor": advisor},
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def ingest_other(tenant: str, advisor: str) -> str:
    identity = {
        "Content-Type": "application/json",
        "X-Nevis-Tenant": tenant,
        "X-Nevis-Advisor": advisor,
    }
    client_request = urllib.request.Request(
        "http://127.0.0.1:8000/v1/clients",
        data=json.dumps(
            {
                "first_name": "Other",
                "last_name": "Fixture",
                "email": "other-fixture@nevis.test",
                "social_links": [],
                "source_type": "smoke",
                "source_reference": "other-client",
            }
        ).encode(),
        headers={**identity, "Idempotency-Key": "compose-other-client-v1"},
        method="POST",
    )
    with urllib.request.urlopen(client_request) as response:
        client_id = json.load(response)["id"]
    payload = json.dumps(
        {
            "source_reference": "compose-smoke",
            "external_document_id": "other-tenant-client-fixture-2",
            "title": "Other tenant Nevis indexing",
            "content": "Nevis indexing " * 100,
        }
    ).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:8000/v1/clients/{client_id}/documents",
        data=payload,
        headers={
            **identity,
            "Idempotency-Key": "compose-other-client-search-v2",
        },
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return str(json.load(response)["document_version_id"])


def ingest_secondary_global_fixture() -> str:
    identity = {
        "Content-Type": "application/json",
        "X-Nevis-Tenant": "nevis-global",
        "X-Nevis-Advisor": "compose-smoke-advisor",
    }
    client_request = urllib.request.Request(
        "http://127.0.0.1:8000/v1/clients",
        data=json.dumps(
            {
                "first_name": "Grace",
                "last_name": "Hopper",
                "email": "grace-hopper-mixed-v1@nevis.test",
                "description": "Estate and inheritance tax specialist",
                "social_links": [],
                "source_type": "smoke",
                "source_reference": "mixed-secondary-client-v1",
            }
        ).encode(),
        headers={**identity, "Idempotency-Key": "mixed-secondary-client-v1"},
        method="POST",
    )
    with urllib.request.urlopen(client_request) as response:
        client_id = json.load(response)["id"]
    document_request = urllib.request.Request(
        f"http://127.0.0.1:8000/v1/clients/{client_id}/documents",
        data=json.dumps(
            {
                "source_reference": "compose-smoke",
                "external_document_id": "mixed-secondary-document-v1",
                "title": "Inheritance trust note",
                "content": (
                    "A family estate plan covering inheritance tax allowances "
                    "and trust administration."
                ),
            }
        ).encode(),
        headers={
            **identity,
            "Idempotency-Key": "mixed-secondary-document-v1",
        },
        method="POST",
    )
    with urllib.request.urlopen(document_request) as response:
        return str(json.load(response)["document_version_id"])


def wait_for_index(version_id: str, tenant: str, advisor: str) -> None:
    for _ in range(60):
        status = api_request(f"/v1/document-versions/{version_id}", tenant, advisor)
        if status["indexing_status"] == "completed":
            return
        time.sleep(1)
    raise RuntimeError("search isolation fixture indexing did not complete")


other_tenant, other_advisor = asyncio.run(provision_other_tenant())
secondary_version = ingest_secondary_global_fixture()
wait_for_index(secondary_version, "nevis-global", "compose-smoke-advisor")
legacy_version = asyncio.run(provision_legacy_unassociated_document())
wait_for_index(legacy_version, "nevis-global", "compose-smoke-advisor")
other_version = ingest_other(other_tenant, other_advisor)
wait_for_index(other_version, other_tenant, other_advisor)

query = urllib.parse.urlencode({"q": "Nevis indexing", "limit": 20})
page = api_request(f"/search?{query}", "nevis-global", "compose-smoke-advisor")
assert page["mode"] == "hybrid"
assert page["ranking_version"] == "mixed-rrf-v1"
results = page["results"]
assert isinstance(results, list) and results
assert {item["type"] for item in results} >= {"client", "document"}
assert results[0]["type"] == "client"
document_required = {
    "tenant_id",
    "client_id",
    "source_id",
    "document_id",
    "document_version_id",
    "embedding_profile_id",
    "indexing_authorization_decision_id",
    "search_authorization_decision_id",
}
client_required = {
    "tenant_id",
    "client_id",
    "creation_authorization_decision_id",
    "search_authorization_decision_id",
}
assert all(
    (client_required if item["type"] == "client" else document_required) <= set(item["provenance"])
    for item in results
)
assert all(item["title"] != "Other tenant Nevis indexing" for item in results)

legacy_query = urllib.parse.urlencode({"q": "legacy unassociated compliance", "limit": 20})
legacy_page = api_request(f"/search?{legacy_query}", "nevis-global", "compose-smoke-advisor")
legacy_result = next(
    item for item in legacy_page["results"] if item["title"] == "Legacy unassociated archive"
)
assert legacy_result["type"] == "document"
assert legacy_result["provenance"]["client_id"] is None
