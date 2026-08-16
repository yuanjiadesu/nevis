"""Provision or reactivate an operator-controlled advisor membership."""

import argparse
import asyncio

from sqlalchemy import select

from nevis.infrastructure.database import build_engine, build_session_factory
from nevis.infrastructure.models import Advisor, AdvisorTenantMembership, Tenant
from nevis.settings import get_settings


async def provision(tenant_slug: str, advisor_external_id: str) -> None:
    engine = build_engine(get_settings().database_url)
    sessions = build_session_factory(engine)
    try:
        async with sessions() as session:
            async with session.begin():
                tenant = await session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
                if tenant is None:
                    raise RuntimeError(f"tenant not found: {tenant_slug}")
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
                else:
                    membership.is_active = True
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "advisor_external_id",
        help="local advisor ID, or the exact verified OIDC sub in production",
    )
    parser.add_argument("--tenant", default="nevis-global")
    arguments = parser.parse_args()
    asyncio.run(provision(arguments.tenant, arguments.advisor_external_id))
