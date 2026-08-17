from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from nevis.domain.embeddings import EmbeddingProfileIdentity
from nevis.domain.reranking import RerankerProfileIdentity
from nevis.infrastructure.embeddings import EmbeddingProviderUnavailable, LocalTEIProvider
from nevis.infrastructure.reranking import LocalTEIReranker, RerankerProviderUnavailable
from nevis.settings import Settings
from nevis.workers import main as worker


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


class FakeClient:
    def __init__(
        self, response: FakeResponse | None = None, error: Exception | None = None
    ) -> None:
        self.response = response
        self.error = error

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, *_: object, **__: object) -> FakeResponse:
        return self._result()

    async def post(self, *_: object, **__: object) -> FakeResponse:
        return self._result()

    def _result(self) -> FakeResponse:
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def embedding_provider() -> LocalTEIProvider:
    return LocalTEIProvider(
        "http://tei/",
        EmbeddingProfileIdentity("tei", "fixture", "1", 2, "l2", 1, 1),
    )


@pytest.mark.asyncio
async def test_embedding_adapter_maps_health_and_invalid_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "nevis.infrastructure.embeddings.httpx.AsyncClient",
        lambda **_: FakeClient(error=httpx.ConnectError("private endpoint")),
    )
    provider = embedding_provider()
    assert not (await provider.healthcheck()).available
    with pytest.raises(EmbeddingProviderUnavailable, match="embedding runtime unavailable"):
        await provider.embed_query("query")

    monkeypatch.setattr(
        "nevis.infrastructure.embeddings.httpx.AsyncClient",
        lambda **_: FakeClient(FakeResponse({"data": [{"embedding": [1.0, 0.0]}]})),
    )
    with pytest.raises(EmbeddingProviderUnavailable, match="invalid response"):
        await provider.embed_documents(["one", "two"])


@pytest.mark.asyncio
async def test_reranker_reorders_scores_and_rejects_duplicate_indices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = LocalTEIReranker(
        "http://tei/",
        RerankerProfileIdentity("tei", "fixture", "1"),
        timeout_seconds=1,
    )
    monkeypatch.setattr(
        "nevis.infrastructure.reranking.httpx.AsyncClient",
        lambda **_: FakeClient(
            FakeResponse([{"index": 1, "score": 0.2}, {"index": 0, "score": 0.9}])
        ),
    )
    assert await provider.rerank("query", ["first", "second"]) == [0.9, 0.2]
    assert await provider.rerank("query", []) == []

    monkeypatch.setattr(
        "nevis.infrastructure.reranking.httpx.AsyncClient",
        lambda **_: FakeClient(
            FakeResponse([{"index": 0, "score": 0.2}, {"index": 0, "score": 0.9}])
        ),
    )
    with pytest.raises(RerankerProviderUnavailable, match="invalid response"):
        await provider.rerank("query", ["first", "second"])


@pytest.mark.asyncio
async def test_worker_routes_idle_and_summary_work(monkeypatch: pytest.MonkeyPatch) -> None:
    indexing = AsyncMock(return_value=False)
    summary = AsyncMock(return_value=True)
    monkeypatch.setattr(worker, "process_indexing_once", indexing)
    monkeypatch.setattr(worker, "process_summary_once", summary)
    session_factory: Any = object()
    provider: Any = object()
    summarizer: Any = object()
    settings = Settings(_env_file=None)

    assert not await worker.process_work_once(session_factory, provider, None, settings)
    assert await worker.process_work_once(session_factory, provider, summarizer, settings)
    summary.assert_awaited_once_with(
        session_factory,
        summarizer,
        input_max_chars=settings.document_summary_input_max_chars,
        output_max_chars=settings.document_summary_output_max_chars,
        lease_seconds=settings.document_summary_lease_seconds,
        max_attempts=settings.document_summary_max_attempts,
    )
