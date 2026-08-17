"""Comparable, credential-safe performance reports for operator harnesses."""

from __future__ import annotations

import os
import platform
import statistics
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

WORKLOADS = frozenset({"search_eval", "search_warm_p95", "repo_capacity"})
ALLOWED_KEYS = frozenset(
    {
        "timestamp",
        "workload",
        "ranking_version",
        "corpus",
        "concurrency",
        "warm_up",
        "runtime",
        "p50_ms",
        "p95_ms",
        "good_event_ratio",
        "slo_ms",
        "outcome",
        "metrics",
    }
)
FORBIDDEN_KEY_FRAGMENTS = (
    "content",
    "document_text",
    "snippet",
    "vector",
    "email",
    "query",
    "token",
    "secret",
    "password",
    "api_key",
    "authorization",
    "bearer",
    "claim",
    "jwt",
    "signing",
    "connection",
    "database_url",
    "dsn",
)


class UnsafePerformanceReport(ValueError):
    """A report included a forbidden field or value."""


def runtime_identity() -> dict[str, str | int | None]:
    return {
        "system": platform.system(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }


def latency_stats(samples: list[float], slo_ms: float | None) -> tuple[float, float, float]:
    if not samples:
        raise ValueError("at least one latency sample is required")
    p50 = statistics.median(samples)
    p95 = (
        statistics.quantiles(samples, n=100, method="inclusive")[94]
        if len(samples) >= 2
        else samples[0]
    )
    if slo_ms is None:
        ratio = 1.0
    else:
        ratio = sum(sample <= slo_ms for sample in samples) / len(samples)
    return round(p50, 2), round(p95, 2), round(ratio, 4)


def outcome_for_p95(p95_ms: float, slo_ms: float | None) -> str:
    if slo_ms is None:
        return "pass"
    return "pass" if p95_ms <= slo_ms else "fail"


def build_report(
    *,
    workload: str,
    samples: list[float],
    slo_ms: float | None,
    ranking_version: str | None = None,
    corpus: dict[str, int] | None = None,
    concurrency: int = 1,
    warm_up: bool = False,
    metrics: dict[str, Any] | None = None,
    runtime: dict[str, str | int | None] | None = None,
) -> dict[str, Any]:
    if workload not in WORKLOADS:
        raise UnsafePerformanceReport(f"unknown workload {workload!r}")
    p50_ms, p95_ms, good_event_ratio = latency_stats(samples, slo_ms)
    report = {
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "workload": workload,
        "ranking_version": ranking_version,
        "corpus": corpus,
        "concurrency": concurrency,
        "warm_up": warm_up,
        "runtime": runtime if runtime is not None else runtime_identity(),
        "p50_ms": p50_ms,
        "p95_ms": p95_ms,
        "good_event_ratio": good_event_ratio,
        "slo_ms": slo_ms,
        "outcome": outcome_for_p95(p95_ms, slo_ms),
        "metrics": metrics or {},
    }
    return validate_report(report)


def validate_report(report: Mapping[str, Any]) -> dict[str, Any]:
    unknown = set(report) - ALLOWED_KEYS
    if unknown:
        raise UnsafePerformanceReport(f"forbidden report fields: {sorted(unknown)}")
    payload = dict(report)
    _reject_forbidden_keys("report", payload)
    if "metrics" in payload:
        _reject_forbidden_keys("metrics", payload["metrics"])
        _reject_non_numeric_metrics(payload["metrics"])
    _reject_sensitive_strings(payload)
    return payload


def _reject_forbidden_keys(label: str, fields: dict[str, Any]) -> None:
    for key in fields:
        lowered = key.lower()
        if any(fragment in lowered for fragment in FORBIDDEN_KEY_FRAGMENTS):
            raise UnsafePerformanceReport(f"{label} contains forbidden field {key!r}")


def _reject_non_numeric_metrics(metrics: dict[str, Any]) -> None:
    for key, value in metrics.items():
        if isinstance(value, dict):
            _reject_non_numeric_metrics(value)
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise UnsafePerformanceReport(f"metrics[{key!r}] must be numeric")


def _reject_sensitive_strings(value: Any) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _reject_sensitive_strings(item)
        return
    if not isinstance(value, str):
        return
    lowered = value.lower()
    if "://" in value or "@" in value or "password=" in lowered:
        raise UnsafePerformanceReport("report contains a credential-like string")
