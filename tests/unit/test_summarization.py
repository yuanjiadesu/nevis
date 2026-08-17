import json
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from nevis.domain.summarization import SummarizationError, normalize_summary
from nevis.infrastructure.summarization import OpenAICompatibleSummarizer
from nevis.settings import Settings


def test_summary_configuration_is_disabled_by_default_and_guarded() -> None:
    defaults = Settings(_env_file=None)
    assert not defaults.document_summaries_enabled
    assert defaults.llm_provider == "opencode-go"
    assert defaults.llm_model == "mimo-v2.5"
    assert defaults.llm_endpoint == "https://opencode.ai/zen/go/v1/chat/completions"
    with pytest.raises(ValidationError, match="fictional_test_data"):
        Settings(
            _env_file=None,
            document_summaries_enabled=True,
            llm_api_key="secret",
        )
    with pytest.raises(ValidationError, match="NEVIS_LLM_API_KEY"):
        Settings(
            _env_file=None,
            document_summaries_enabled=True,
            fictional_test_data=True,
        )


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://llm.example.com/v1/chat/completions",
        "https://user:secret@llm.example.com/v1/chat/completions",
        "https://llm.example.com/v1/chat/completions?target=other",
        "https://llm.example.com/v1/chat/completions#fragment",
        "https://llm.example.com/v1/responses",
    ],
)
def test_summary_configuration_rejects_unsafe_provider_endpoint(endpoint: str) -> None:
    with pytest.raises(ValidationError, match="safe HTTPS Chat Completions URL"):
        Settings(
            _env_file=None,
            document_summaries_enabled=True,
            fictional_test_data=True,
            llm_api_key="secret",
            llm_endpoint=endpoint,
        )


def test_summary_configuration_rejects_an_untrusted_host() -> None:
    with pytest.raises(ValidationError, match="opencode.ai"):
        Settings(
            _env_file=None,
            document_summaries_enabled=True,
            fictional_test_data=True,
            llm_api_key="secret",
            llm_provider="example-provider",
            llm_model="example-model",
            llm_endpoint="https://llm.example.com/v1/chat/completions",
        )


def test_summary_output_is_plain_bounded_and_two_sentences() -> None:
    assert normalize_summary(" One fact.\n Another fact. ", max_chars=40) == (
        "One fact. Another fact."
    )
    with pytest.raises(SummarizationError, match="too_many_sentences"):
        normalize_summary("One. Two. Three.", max_chars=100)
    with pytest.raises(SummarizationError, match="output_too_large"):
        normalize_summary("too long", max_chars=3)


@pytest.mark.asyncio
async def test_openai_compatible_adapter_sends_bounded_non_persistent_request(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "choices": [
                    {"message": {"content": "A fictional utility bill confirms the address."}}
                ]
            }

    class FakeClient:
        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, url: str, **kwargs: object) -> FakeResponse:
            captured.update(url=url, **kwargs)
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: FakeClient())
    summarizer = OpenAICompatibleSummarizer(
        api_key="private-key",
        provider="configured-provider",
        model="configured-model",
        endpoint="https://llm.example.com/v1/chat/completions",
        prompt_version="v1",
        input_max_chars=1_000,
        output_max_chars=200,
        max_tokens=500,
        timeout_seconds=2,
    )

    result = await summarizer.summarize("Fictional account evidence.")

    assert result.text == "A fictional utility bill confirms the address."
    assert captured["url"] == "https://llm.example.com/v1/chat/completions"
    assert captured["headers"] == {"Authorization": "Bearer private-key"}
    body = captured["json"]
    assert isinstance(body, dict)
    assert body["model"] == "configured-model"
    assert body["store"] is False
    assert body["temperature"] == 0
    assert body["max_tokens"] == 500
    assert body["messages"][1] == {
        "role": "user",
        "content": "<document>Fictional account evidence.</document>",
    }
    assert "private-key" not in json.dumps(body)
    assert result.provider == "configured-provider"
    assert result.model == "configured-model"


@pytest.mark.asyncio
async def test_openai_compatible_adapter_rejects_oversized_input_without_a_call(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_: pytest.fail("provider must not be called"),
    )
    summarizer = OpenAICompatibleSummarizer(
        api_key="private-key",
        provider="example-provider",
        model="example-model",
        endpoint="https://llm.example.com/v1/chat/completions",
        prompt_version="v1",
        input_max_chars=3,
        output_max_chars=200,
        max_tokens=500,
        timeout_seconds=2,
    )
    with pytest.raises(SummarizationError, match="input_too_large"):
        await summarizer.summarize("long")


@pytest.mark.asyncio
async def test_openai_compatible_adapter_maps_http_failures_to_a_safe_code(monkeypatch) -> None:
    class FailingClient:
        async def __aenter__(self) -> "FailingClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, *_: object, **__: object) -> None:
            raise httpx.ConnectError("credential and content must not escape")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: FailingClient())
    summarizer = OpenAICompatibleSummarizer(
        api_key="private-key",
        provider="example-provider",
        model="example-model",
        endpoint="https://llm.example.com/v1/chat/completions",
        prompt_version="v1",
        input_max_chars=1_000,
        output_max_chars=200,
        max_tokens=500,
        timeout_seconds=2,
    )

    with pytest.raises(SummarizationError, match="provider_unavailable"):
        await summarizer.summarize("fictional content")


@pytest.mark.asyncio
async def test_openai_compatible_adapter_maps_provider_errors_to_a_safe_code(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"error": {"type": "FreeUsageLimitError"}}

    class FakeClient:
        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, *_: object, **__: object) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: FakeClient())
    summarizer = OpenAICompatibleSummarizer(
        api_key="private-key",
        provider="example-provider",
        model="example-model",
        endpoint="https://llm.example.com/v1/chat/completions",
        prompt_version="v1",
        input_max_chars=1_000,
        output_max_chars=200,
        max_tokens=500,
        timeout_seconds=2,
    )

    with pytest.raises(SummarizationError, match="provider_unavailable"):
        await summarizer.summarize("fictional content")
