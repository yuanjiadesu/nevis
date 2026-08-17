from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nevis.domain.authorization import AuthorizationContext
from nevis.domain.clients import (
    ClientConflict,
    ClientCreationOutcome,
    ClientCreationResult,
    ClientNotFound,
    ClientPage,
    ClientResource,
    ClientUpdateConflict,
    CreateClientCommand,
    UpdateClientCommand,
    client_request_fingerprint,
)
from nevis.infrastructure.models import Client
from nevis.infrastructure.repositories import (
    acquire_client_creation_locks,
    append_audit_event,
    create_client_record,
    get_client,
    get_client_by_normalized_email,
    get_client_creation_request,
    list_clients,
    record_client_creation_request,
    update_client_record,
)


def _resource(client: Client, retrieval_decision_id: UUID | None = None) -> ClientResource:
    return ClientResource(
        id=client.id,
        tenant_id=client.tenant_id,
        first_name=client.first_name,
        last_name=client.last_name,
        email=client.email,
        description=client.description,
        social_links=tuple(client.social_links),
        source_type=client.source_type,
        source_reference=client.source_reference,
        creation_authorization_decision_id=client.creation_authorization_decision_id,
        created_at=client.created_at,
        updated_at=client.updated_at,
        retrieval_authorization_decision_id=retrieval_decision_id,
    )


async def create_client(
    session: AsyncSession, command: CreateClientCommand, authorization: AuthorizationContext
) -> ClientCreationResult:
    normalized = command.normalized()
    fingerprint = client_request_fingerprint(normalized)
    try:
        await acquire_client_creation_locks(
            session,
            tenant_id=authorization.tenant_id,
            idempotency_key=normalized.idempotency_key,
            normalized_email=normalized.email,
        )
        previous = await get_client_creation_request(
            session, authorization.tenant_id, normalized.idempotency_key
        )
        if previous is not None:
            if previous.request_fingerprint != fingerprint:
                await append_audit_event(
                    session,
                    event_type="client.creation_conflicted",
                    request_id=normalized.request_id,
                    decision=authorization.decision,
                    metadata={"reason": "idempotency_conflict"},
                )
                await session.commit()
                raise ClientConflict("client creation conflict")
            client = await get_client(session, authorization.tenant_id, previous.client_id)
            if client is None:
                raise RuntimeError("client idempotency lineage is incomplete")
            await append_audit_event(
                session,
                event_type="client.creation_replayed",
                request_id=normalized.request_id,
                decision=authorization.decision,
                metadata={"client_id": str(client.id)},
            )
            await session.commit()
            return ClientCreationResult(_resource(client), ClientCreationOutcome.REPLAYED)
        if (
            await get_client_by_normalized_email(session, authorization.tenant_id, normalized.email)
            is not None
        ):
            await append_audit_event(
                session,
                event_type="client.creation_conflicted",
                request_id=normalized.request_id,
                decision=authorization.decision,
                metadata={"reason": "email_conflict"},
            )
            await session.commit()
            raise ClientConflict("client creation conflict")
        client = await create_client_record(
            session,
            tenant_id=authorization.tenant_id,
            command=normalized,
            decision=authorization.decision,
        )
        await record_client_creation_request(
            session,
            tenant_id=authorization.tenant_id,
            idempotency_key=normalized.idempotency_key,
            fingerprint=fingerprint,
            client_id=client.id,
        )
        await append_audit_event(
            session,
            event_type="client.created",
            request_id=normalized.request_id,
            decision=authorization.decision,
            metadata={"client_id": str(client.id)},
        )
        await session.commit()
        return ClientCreationResult(_resource(client), ClientCreationOutcome.CREATED)
    except IntegrityError as error:
        await session.rollback()
        previous = await get_client_creation_request(
            session, authorization.tenant_id, normalized.idempotency_key
        )
        if previous is not None and previous.request_fingerprint == fingerprint:
            client = await get_client(session, authorization.tenant_id, previous.client_id)
            if client is not None:
                await append_audit_event(
                    session,
                    event_type="client.creation_replayed",
                    request_id=normalized.request_id,
                    decision=authorization.decision,
                    metadata={"client_id": str(client.id)},
                )
                await session.commit()
                return ClientCreationResult(_resource(client), ClientCreationOutcome.REPLAYED)
        try:
            await append_audit_event(
                session,
                event_type="client.creation_conflicted",
                request_id=normalized.request_id,
                decision=authorization.decision,
                metadata={"reason": "concurrent_conflict"},
            )
            await session.commit()
        except IntegrityError:
            await session.rollback()
        raise ClientConflict("client creation conflict") from error


async def retrieve_client(
    session: AsyncSession,
    client_id: UUID,
    authorization: AuthorizationContext,
    request_id: str,
) -> ClientResource:
    client = await get_client(session, authorization.tenant_id, client_id)
    if client is None:
        await append_audit_event(
            session,
            event_type="client.not_found",
            request_id=request_id,
            decision=authorization.decision,
            metadata={"reason": "not_found"},
        )
        await session.commit()
        raise ClientNotFound("client not found")
    await append_audit_event(
        session,
        event_type="client.found",
        request_id=request_id,
        decision=authorization.decision,
        metadata={"client_id": str(client.id)},
    )
    await session.commit()
    return _resource(client, authorization.decision.decision_id)


async def list_client_records(
    session: AsyncSession,
    authorization: AuthorizationContext,
    request_id: str,
    *,
    limit: int,
    before_created_at: datetime | None = None,
    before_id: UUID | None = None,
) -> ClientPage:
    records = await list_clients(
        session,
        authorization.tenant_id,
        limit=limit + 1,
        before_created_at=before_created_at,
        before_id=before_id,
    )
    page = records[:limit]
    await append_audit_event(
        session,
        event_type="client.listed",
        request_id=request_id,
        decision=authorization.decision,
        metadata={"result_count": len(page)},
    )
    await session.commit()
    return ClientPage(
        clients=tuple(_resource(record, authorization.decision.decision_id) for record in page),
        has_more=len(records) > limit,
    )


async def update_client(
    session: AsyncSession,
    client_id: UUID,
    command: UpdateClientCommand,
    authorization: AuthorizationContext,
) -> ClientResource:
    normalized = command.normalized()
    client = await get_client(session, authorization.tenant_id, client_id)
    if client is None:
        await append_audit_event(
            session,
            event_type="client.not_found",
            request_id=normalized.request_id,
            decision=authorization.decision,
            metadata={"reason": "not_found"},
        )
        await session.commit()
        raise ClientNotFound("client not found")
    matching_email = await get_client_by_normalized_email(
        session, authorization.tenant_id, normalized.email
    )
    if matching_email is not None and matching_email.id != client.id:
        await append_audit_event(
            session,
            event_type="client.update_conflicted",
            request_id=normalized.request_id,
            decision=authorization.decision,
            metadata={"reason": "email_conflict"},
        )
        await session.commit()
        raise ClientUpdateConflict("client update conflict")
    try:
        updated = await update_client_record(session, client=client, command=normalized)
        await append_audit_event(
            session,
            event_type="client.updated",
            request_id=normalized.request_id,
            decision=authorization.decision,
            metadata={"client_id": str(updated.id)},
        )
        await session.commit()
        await session.refresh(updated)
        return _resource(updated, authorization.decision.decision_id)
    except IntegrityError as error:
        await session.rollback()
        raise ClientUpdateConflict("client update conflict") from error
