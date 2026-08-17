import pytest

from nevis.performance import (
    ALLOWED_KEYS,
    WORKLOADS,
    UnsafePerformanceReport,
    build_report,
    outcome_for_p95,
    validate_report,
)


def _report(**overrides: object) -> dict[str, object]:
    payload = {
        "workload": "search_warm_p95",
        "samples": [100.0, 120.0, 140.0, 160.0, 180.0],
        "slo_ms": 800.0,
        "ranking_version": "mixed-rrf-v5",
        "warm_up": True,
    }
    payload.update(overrides)
    return build_report(**payload)  # type: ignore[arg-type]


def test_report_contains_required_context_and_no_extra_keys() -> None:
    report = _report()

    assert ALLOWED_KEYS == set(report)
    assert report["workload"] == "search_warm_p95"
    assert report["ranking_version"] == "mixed-rrf-v5"
    assert report["warm_up"] is True
    assert report["concurrency"] == 1
    assert report["slo_ms"] == 800.0
    assert report["outcome"] == "pass"
    assert {"system", "machine", "python", "cpu_count"} <= set(report["runtime"])


def test_unknown_workload_is_rejected() -> None:
    with pytest.raises(UnsafePerformanceReport, match="unknown workload"):
        _report(workload="search_concurrent")


def test_workloads_are_the_three_existing_harnesses() -> None:
    assert WORKLOADS == {"search_eval", "search_warm_p95", "repo_capacity"}


def test_forbidden_fields_are_rejected() -> None:
    report = _report()
    with pytest.raises(UnsafePerformanceReport, match="forbidden report fields"):
        validate_report({**report, "query": "address proof"})
    with pytest.raises(UnsafePerformanceReport, match="client_email"):
        _report(metrics={"client_email": 1.0})
    with pytest.raises(UnsafePerformanceReport, match="embedding_vector"):
        _report(metrics={"embedding_vector": 1.0})
    with pytest.raises(UnsafePerformanceReport, match="bearer_token"):
        _report(metrics={"bearer_token": 1.0})


def test_connection_strings_and_emails_are_rejected() -> None:
    report = _report()
    with pytest.raises(UnsafePerformanceReport, match="credential-like"):
        validate_report({**report, "ranking_version": "postgresql://nevis:nevis@db/nevis"})
    with pytest.raises(UnsafePerformanceReport, match="credential-like"):
        validate_report({**report, "ranking_version": "ada@example.test"})


def test_metrics_must_be_numeric() -> None:
    with pytest.raises(UnsafePerformanceReport, match="must be numeric"):
        _report(metrics={"label": "Household electricity statement"})


def test_warm_search_gate_fails_above_800ms() -> None:
    assert outcome_for_p95(800.0, 800.0) == "pass"
    assert outcome_for_p95(800.01, 800.0) == "fail"
    report = _report(samples=[900.0, 910.0, 920.0])
    assert report["outcome"] == "fail"
    assert report["p95_ms"] > 800


def test_eval_latency_is_not_a_gate() -> None:
    report = _report(workload="search_eval", slo_ms=None, samples=[1100.0, 1200.0], warm_up=False)
    assert report["outcome"] == "pass"
    assert report["slo_ms"] is None
    assert report["p95_ms"] > 800
