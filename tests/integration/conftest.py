import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import InterfaceError, OperationalError

from nevis.infrastructure.database import build_engine, build_session_factory
from nevis.infrastructure.models import Advisor, AdvisorTenantMembership, Client

DEFAULT_DATABASE_URL = "postgresql+asyncpg://nevis:nevis@localhost:5434/nevis"
START_DATABASE = (
    "docker compose -f compose.yaml -f compose.test.yaml -p nevis-integration "
    "up --build --wait postgres migrate"
)

os.environ.setdefault("NEVIS_TEST_DATABASE_URL", DEFAULT_DATABASE_URL)


@pytest.fixture
async def database_session_factory():
    url = os.environ["NEVIS_TEST_DATABASE_URL"]
    if not url:
        pytest.skip("NEVIS_TEST_DATABASE_URL is empty; database integration tests are opted out")
    engine = build_engine(url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE runtime_capabilities, document_summaries, document_chunks, "
                    "indexing_jobs, "
                    "ingestion_requests, "
                    "document_versions, documents, document_sources, audit_events, "
                    "authorization_decisions, client_creation_requests, clients, "
                    "advisor_tenant_memberships, advisors, embedding_profiles CASCADE"
                )
            )
    except (OSError, InterfaceError, OperationalError) as error:
        await engine.dispose()
        pytest.fail(
            f"cannot reach the integration database at {url}\n"
            f"start it with:\n  {START_DATABASE}\n"
            f"or set NEVIS_TEST_DATABASE_URL empty to skip these suites\n({error})",
            pytrace=False,
        )
    try:
        yield build_session_factory(engine)
    finally:
        await engine.dispose()


@pytest.fixture
async def authorized_context(database_session_factory):
    async with database_session_factory() as session:
        async with session.begin():
            tenant = await session.scalar(
                text("SELECT id FROM tenants WHERE slug = 'nevis-global'")
            )
            assert tenant is not None
            advisor = Advisor(external_id="test-advisor")
            session.add(advisor)
            await session.flush()
            session.add(AdvisorTenantMembership(advisor_id=advisor.id, tenant_id=tenant))
        from nevis.application.authorization import authorize
        from nevis.domain.authorization import AuthorizationAction

        context = await authorize(
            session,
            tenant_slug="nevis-global",
            advisor_external_id="test-advisor",
            action=AuthorizationAction.DOCUMENT_INGEST,
            request_id="test-context",
        )
        await session.commit()
    return context


@pytest.fixture
async def client_id(database_session_factory, authorized_context):
    async with database_session_factory() as session:
        async with session.begin():
            client = Client(
                tenant_id=authorized_context.tenant_id,
                first_name="Test",
                last_name="Client",
                email="test@example.com",
                normalized_email="test@example.com",
                description=None,
                social_links=[],
                source_type="fixture",
                source_reference="fixture-client",
                creation_authorization_decision_id=authorized_context.decision.decision_id,
            )
            session.add(client)
            await session.flush()
            return client.id
