from sqlalchemy.ext.asyncio import AsyncSession

from nevis.domain.authorization import (
    AuthorizationAction,
    AuthorizationContext,
    AuthorizationDenied,
)
from nevis.infrastructure.repositories import (
    append_audit_event,
    create_authorization_decision,
    get_active_membership,
    get_advisor_by_external_id,
    get_tenant_by_slug,
)


async def authorize(
    session: AsyncSession,
    *,
    tenant_slug: str,
    advisor_external_id: str,
    action: AuthorizationAction,
    request_id: str,
    identity_mode: str = "internal",
    identity_issuer_id: str = "internal",
) -> AuthorizationContext:
    tenant = await get_tenant_by_slug(session, tenant_slug)
    if tenant is None:
        raise AuthorizationDenied("unknown tenant")
    advisor = await get_advisor_by_external_id(session, advisor_external_id)
    advisor_id = advisor.id if advisor is not None else None
    is_allowed = advisor_id is not None and await get_active_membership(
        session, tenant.id, advisor_id
    )
    decision = await create_authorization_decision(
        session,
        tenant_id=tenant.id,
        advisor_id=advisor_id,
        action=action,
        request_id=request_id,
        result="allow" if is_allowed else "deny",
        context={"identity_mode": identity_mode, "identity_issuer_id": identity_issuer_id},
    )
    await append_audit_event(
        session,
        event_type="authorization.allowed" if is_allowed else "authorization.denied",
        request_id=request_id,
        decision=decision,
        metadata={
            "action": action,
            "identity_mode": identity_mode,
            "identity_issuer_id": identity_issuer_id,
        },
    )
    if not is_allowed:
        raise AuthorizationDenied("advisor is not an active tenant member")
    assert advisor_id is not None
    return AuthorizationContext(tenant_id=tenant.id, advisor_id=advisor_id, decision=decision)
