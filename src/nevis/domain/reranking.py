from dataclasses import dataclass
from typing import Protocol

from nevis.domain.embeddings import ProviderHealth


@dataclass(frozen=True, slots=True)
class RerankerProfileIdentity:
    provider: str
    model: str
    model_revision: str


class RerankerProvider(Protocol):
    @property
    def profile(self) -> RerankerProfileIdentity: ...

    async def rerank(self, query: str, passages: list[str]) -> list[float]: ...

    async def healthcheck(self) -> ProviderHealth: ...
