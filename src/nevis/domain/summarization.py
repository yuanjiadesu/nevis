import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class SummarizationError(RuntimeError):
    """A provider or response failure safe to record without document text."""


class SummaryStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SummaryConfiguration:
    enabled: bool
    provider: str
    model: str
    prompt_version: str


@dataclass(frozen=True, slots=True)
class SummaryResult:
    text: str
    provider: str
    model: str
    prompt_version: str


@dataclass(frozen=True, slots=True)
class SummaryReconciliationResult:
    states: dict[str, int]
    created: int
    requeued: int
    dry_run: bool


@dataclass(frozen=True, slots=True)
class SummaryDiagnostics:
    enabled: bool
    states: dict[str, int]
    failure_codes: dict[str, int]
    heartbeat_fresh: bool
    capability_match: bool
    heartbeat_age_seconds: int | None


class DocumentSummarizer(Protocol):
    async def summarize(self, content: str) -> SummaryResult: ...


def summary_capability_hash(
    *, enabled: bool, provider: str, model: str, prompt_version: str
) -> str:
    payload = json.dumps(
        {
            "enabled": enabled,
            "model": model,
            "pipeline_version": 1,
            "prompt_version": prompt_version,
            "provider": provider,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def normalize_summary(value: str, *, max_chars: int) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    if not normalized:
        raise SummarizationError("empty_response")
    if len(normalized) > max_chars:
        raise SummarizationError("output_too_large")
    sentences = [part for part in re.split(r"(?<=[.!?])\s+", normalized) if part]
    if len(sentences) > 2:
        raise SummarizationError("too_many_sentences")
    return normalized
