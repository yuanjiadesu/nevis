from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EmbeddingProfileIdentity:
    provider: str
    model: str
    model_revision: str | None
    dimensions: int
    normalization: str
    chunking_version: int
    pipeline_version: int


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    available: bool
    provider: str
    detail: str | None = None


class EmbeddingProvider(Protocol):
    @property
    def profile(self) -> EmbeddingProfileIdentity: ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...

    async def healthcheck(self) -> ProviderHealth: ...
