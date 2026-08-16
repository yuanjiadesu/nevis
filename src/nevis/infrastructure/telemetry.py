"""Safe, low-cardinality fields for operational events.

This boundary deliberately drops raw customer content and secrets. Callers should
emit stable identifiers and outcome metadata, never pass-through request payloads.
"""

from collections.abc import Mapping
from typing import Any

_SENSITIVE_FIELD_FRAGMENTS = (
    "content",
    "document",
    "name",
    "description",
    "snippet",
    "cursor",
    "vector",
    "email",
    "query",
    "text",
    "token",
    "secret",
    "password",
    "api_key",
    "authorization",
    "bearer",
    "claim",
    "external_id",
    "jwt",
    "signing",
    "subject",
)


def safe_telemetry_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    """Return fields safe to attach to logs, traces, or metrics events."""
    return {
        key: value
        for key, value in fields.items()
        if not any(fragment in key.lower() for fragment in _SENSITIVE_FIELD_FRAGMENTS)
    }


def search_telemetry_fields(
    *,
    mode: str,
    outcome: str,
    duration_ms: float,
    lexical_candidates: int,
    semantic_candidates: int,
    client_candidates: int = 0,
    result_count: int,
    degradation_code: str | None,
) -> dict[str, str | float | int | None]:
    """Construct the complete low-cardinality operational search event."""
    return {
        "mode": mode,
        "outcome": outcome,
        "duration_ms": round(duration_ms, 2),
        "lexical_candidates": lexical_candidates,
        "semantic_candidates": semantic_candidates,
        "client_candidates": client_candidates,
        "result_count": result_count,
        "degradation_code": degradation_code,
    }
