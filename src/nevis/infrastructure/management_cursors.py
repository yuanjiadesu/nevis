import base64
import hashlib
import hmac
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime


class InvalidManagementCursor(ValueError):
    """A cursor is malformed, expired, or belongs to another resource collection."""


@dataclass(frozen=True, slots=True)
class ManagementCursorState:
    tenant_id: uuid.UUID
    collection: str
    created_at: datetime
    record_id: uuid.UUID
    issued_at: int


class ManagementCursorCodec:
    def __init__(self, key: str, ttl_seconds: int, clock: Callable[[], float] = time.time) -> None:
        self._key = key.encode()
        self._ttl_seconds = ttl_seconds
        self._clock = clock

    def encode(self, state: ManagementCursorState) -> str:
        payload = {
            "v": 1,
            "t": str(state.tenant_id),
            "c": state.collection,
            "a": state.created_at.isoformat(),
            "i": str(state.record_id),
            "iat": state.issued_at,
        }
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        signature = hmac.new(self._key, body, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(body + signature).decode().rstrip("=")

    def decode(
        self, cursor: str, *, tenant_id: uuid.UUID, collection: str
    ) -> ManagementCursorState:
        try:
            raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
            body, signature = raw[:-32], raw[-32:]
            expected = hmac.new(self._key, body, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                raise InvalidManagementCursor("invalid cursor")
            payload = json.loads(body)
            state = ManagementCursorState(
                tenant_id=uuid.UUID(payload["t"]),
                collection=str(payload["c"]),
                created_at=datetime.fromisoformat(payload["a"]),
                record_id=uuid.UUID(payload["i"]),
                issued_at=int(payload["iat"]),
            )
            if (
                payload["v"] != 1
                or state.tenant_id != tenant_id
                or state.collection != collection
                or self._clock() - state.issued_at > self._ttl_seconds
            ):
                raise InvalidManagementCursor("invalid cursor")
            return state
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as error:
            if isinstance(error, InvalidManagementCursor):
                raise
            raise InvalidManagementCursor("invalid cursor") from error
