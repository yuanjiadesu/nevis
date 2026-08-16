import base64
import hashlib
import hmac
import json
import time
import uuid
from collections.abc import Callable

from nevis.domain.search import (
    CursorState,
    InvalidSearchCursor,
    MatchBand,
    ResultType,
    RetrievalMode,
)


class SearchCursorCodec:
    def __init__(self, key: str, ttl_seconds: int, clock: Callable[[], float] = time.time) -> None:
        self._key = key.encode()
        self._ttl_seconds = ttl_seconds
        self._clock = clock

    def encode(self, state: CursorState) -> str:
        payload = {
            "v": 2,
            "q": state.query_fingerprint,
            "t": str(state.tenant_id),
            "p": str(state.embedding_profile_id),
            "m": state.mode.value,
            "rv": state.ranking_version,
            "b": int(state.match_band),
            "s": state.fused_score,
            "rt": state.result_type.value,
            "r": str(state.result_id),
            "iat": state.issued_at,
        }
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        signature = hmac.new(self._key, body, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(body + signature).decode().rstrip("=")

    def decode(self, cursor: str) -> CursorState:
        try:
            raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
            body, signature = raw[:-32], raw[-32:]
            expected = hmac.new(self._key, body, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                raise InvalidSearchCursor("invalid search cursor")
            payload = json.loads(body)
            if payload["v"] != 2 or self._clock() - int(payload["iat"]) > self._ttl_seconds:
                raise InvalidSearchCursor("invalid search cursor")
            return CursorState(
                query_fingerprint=str(payload["q"]),
                tenant_id=uuid.UUID(payload["t"]),
                embedding_profile_id=uuid.UUID(payload["p"]),
                mode=RetrievalMode(payload["m"]),
                ranking_version=str(payload["rv"]),
                match_band=MatchBand(int(payload["b"])),
                fused_score=float(payload["s"]),
                result_type=ResultType(payload["rt"]),
                result_id=uuid.UUID(payload["r"]),
                issued_at=int(payload["iat"]),
            )
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as error:
            raise InvalidSearchCursor("invalid search cursor") from error
