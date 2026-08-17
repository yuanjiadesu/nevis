import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from nevis.application import clients as client_app
from nevis.domain.authorization import (
    AuthorizationAction,
    AuthorizationContext,
    AuthorizationDecision,
)
from nevis.domain.clients import ClientNotFound
from nevis.infrastructure.models import Client


def authorization() -> AuthorizationContext:
    tenant_id = uuid.uuid4()
    advisor_id = uuid.uuid4()
    return AuthorizationContext(
        tenant_id=tenant_id,
        advisor_id=advisor_id,
        decision=AuthorizationDecision(
            tenant_id=tenant_id,
            advisor_id=advisor_id,
            action=AuthorizationAction.CLIENT_LIST,
            decision_id=uuid.uuid4(),
        ),
    )


def client(tenant_id: uuid.UUID, email: str) -> Client:
    now = datetime.now(UTC)
    return Client(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        first_name="Ada",
        last_name="Lovelace",
        email=email,
        normalized_email=email,
        description=None,
        social_links=[],
        source_type="fixture",
        source_reference="fixture",
        creation_authorization_decision_id=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_list_clients_uses_an_extra_row_for_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = authorization()
    records = [client(context.tenant_id, f"ada{index}@example.com") for index in range(3)]
    session = AsyncMock()
    listed = AsyncMock(return_value=records)
    audited = AsyncMock()
    monkeypatch.setattr(client_app, "list_clients", listed)
    monkeypatch.setattr(client_app, "append_audit_event", audited)

    page = await client_app.list_client_records(
        session,
        context,
        "request-1",
        limit=2,
    )

    assert page.has_more
    assert [item.email for item in page.clients] == [
        "ada0@example.com",
        "ada1@example.com",
    ]
    listed.assert_awaited_once_with(
        session,
        context.tenant_id,
        limit=3,
        before_created_at=None,
        before_id=None,
    )
    audited.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_retrieve_client_audits_not_found_without_leaking_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = authorization()
    session = AsyncMock()
    audited = AsyncMock()
    monkeypatch.setattr(client_app, "get_client", AsyncMock(return_value=None))
    monkeypatch.setattr(client_app, "append_audit_event", audited)

    with pytest.raises(ClientNotFound, match="client not found"):
        await client_app.retrieve_client(session, uuid.uuid4(), context, "request-2")

    assert audited.await_args is not None
    assert audited.await_args.kwargs["metadata"] == {"reason": "not_found"}
    session.commit.assert_awaited_once()
