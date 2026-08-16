from nevis.infrastructure.telemetry import safe_telemetry_fields, search_telemetry_fields


def test_safe_telemetry_fields_excludes_customer_content_and_credentials() -> None:
    fields = safe_telemetry_fields(
        {
            "organization_id": "nevis-global",
            "provider": "tei",
            "document_content": "private plan",
            "advisor_email": "advisor@example.test",
            "client_name": "Ada Lovelace",
            "client_description": "private profile",
            "result_snippet": "private excerpt",
            "search_cursor": "signed-cursor",
            "embedding_vector": [0.1, 0.2],
            "query_text": "retirement",
            "openai_api_key": "secret",
            "bearer_token": "signed-token",
            "jwt_claims": {"sub": "advisor"},
            "signing_key": "public-or-private-key",
            "advisor_external_id": "oidc-subject",
        }
    )

    assert fields == {"organization_id": "nevis-global", "provider": "tei"}


def test_search_telemetry_has_only_safe_low_cardinality_fields() -> None:
    fields = search_telemetry_fields(
        mode="hybrid",
        outcome="success",
        duration_ms=12.345,
        lexical_candidates=10,
        semantic_candidates=8,
        result_count=3,
        degradation_code=None,
    )

    assert fields["duration_ms"] == 12.35
    assert set(fields) == {
        "mode",
        "outcome",
        "duration_ms",
        "lexical_candidates",
        "semantic_candidates",
        "client_candidates",
        "result_count",
        "degradation_code",
    }
