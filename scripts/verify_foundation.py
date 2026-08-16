"""Database-backed assertions used by the Compose smoke test."""

import asyncio

from sqlalchemy import func, select, text

from nevis.domain.authorization import AuthorizationAction
from nevis.infrastructure.database import build_engine, build_session_factory
from nevis.infrastructure.models import AuditEvent, Tenant
from nevis.infrastructure.repositories import (
    append_audit_event,
    create_authorization_decision,
    get_global_tenant,
)
from nevis.settings import get_settings


async def verify() -> None:
    engine = build_engine(get_settings().database_url)
    sessions = build_session_factory(engine)
    try:
        async with sessions() as session:
            extension = await session.scalar(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            )
            global_tenant_count = await session.scalar(
                select(func.count()).select_from(Tenant).where(Tenant.slug == "nevis-global")
            )
            tenant = await get_global_tenant(session)
            decision = await create_authorization_decision(
                session,
                tenant_id=tenant.id,
                advisor_id=None,
                action=AuthorizationAction.DOCUMENT_INGEST,
                request_id="compose-smoke",
                result="allow",
            )
            await append_audit_event(
                session,
                event_type="foundation.smoke_tested",
                request_id="compose-smoke",
                decision=decision,
                metadata={"source": "compose-smoke"},
            )
            await session.commit()

        async with sessions() as session:
            audit_count = await session.scalar(select(func.count()).select_from(AuditEvent))

        assert extension == "vector"
        assert global_tenant_count == 1
        assert audit_count and audit_count >= 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(verify())
