import pytest

from scripts.verify_preview_pipeline import TITLE, verify


def test_preview_pipeline_verifies_all_stages() -> None:
    document_id = "document-1"

    def read(path: str) -> dict[str, object]:
        if path.startswith("/v1/clients?"):
            return {"clients": [{"id": "client-1"}]}
        if path.startswith("/v1/document-versions/"):
            return {"indexing_status": "completed"}
        if path.startswith("/v1/documents/"):
            return {"summary_status": "ready", "summary": "Bounded summary."}
        if path.startswith("/search?"):
            return {
                "results": [
                    {
                        "type": "document",
                        "provenance": {"document_id": document_id},
                    }
                ]
            }
        raise AssertionError(path)

    def write(path: str, payload: dict[str, object], key: str) -> dict[str, object]:
        assert path == "/v1/clients/client-1/documents"
        assert payload["title"] == TITLE
        assert TITLE not in str(payload["content"])
        assert key == "preview-pipeline-check-v1"
        return {"document_id": document_id, "document_version_id": "version-1"}

    assert verify(read, write, timeout_seconds=1, sleep=lambda _: None)["status"] == "ok"


def test_preview_pipeline_reports_failed_stage_without_content() -> None:
    def read(path: str) -> dict[str, object]:
        if path.startswith("/v1/clients?"):
            return {"clients": [{"id": "client-1"}]}
        if path.startswith("/v1/document-versions/"):
            return {"indexing_status": "completed"}
        return {"summary_status": "failed"}

    def write(path: str, payload: dict[str, object], key: str) -> dict[str, object]:
        del path, payload, key
        return {"document_id": "document-1", "document_version_id": "version-1"}

    with pytest.raises(RuntimeError, match="summary stage failed"):
        verify(read, write, timeout_seconds=1, sleep=lambda _: None)
