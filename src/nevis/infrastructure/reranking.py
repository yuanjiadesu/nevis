import math

import httpx

from nevis.domain.embeddings import ProviderHealth
from nevis.domain.reranking import RerankerProfileIdentity


class RerankerProviderUnavailable(RuntimeError):
    pass


class LocalTEIReranker:
    def __init__(
        self,
        base_url: str,
        profile: RerankerProfileIdentity,
        *,
        timeout_seconds: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._profile = profile
        self._timeout_seconds = timeout_seconds

    @property
    def profile(self) -> RerankerProfileIdentity:
        return self._profile

    async def healthcheck(self) -> ProviderHealth:
        try:
            async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
                response = await client.get(f"{self._base_url}/health")
                response.raise_for_status()
        except httpx.HTTPError:
            return ProviderHealth(
                available=False, provider="tei-reranker", detail="reranker unavailable"
            )
        return ProviderHealth(available=True, provider="tei-reranker")

    async def rerank(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, trust_env=False) as client:
                response = await client.post(
                    f"{self._base_url}/rerank",
                    json={"query": query, "texts": passages},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RerankerProviderUnavailable("reranker unavailable") from exc
        if not isinstance(payload, list) or len(payload) != len(passages):
            raise RerankerProviderUnavailable("reranker returned an invalid response")
        scores: list[float | None] = [None] * len(passages)
        for item in payload:
            try:
                index = int(item["index"])
                score = float(item["score"])
            except (KeyError, TypeError, ValueError) as exc:
                raise RerankerProviderUnavailable("reranker returned an invalid response") from exc
            if (
                not 0 <= index < len(passages)
                or scores[index] is not None
                or not math.isfinite(score)
            ):
                raise RerankerProviderUnavailable("reranker returned an invalid response")
            scores[index] = score
        if any(score is None for score in scores):
            raise RerankerProviderUnavailable("reranker returned an invalid response")
        return [score for score in scores if score is not None]


class DeterministicFakeReranker:
    profile = RerankerProfileIdentity("fake", "fixture", "1")

    async def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(available=True, provider="fake-reranker")

    async def rerank(self, query: str, passages: list[str]) -> list[float]:
        del query
        return [1.0 - (index / max(len(passages), 1)) for index in range(len(passages))]
