import hashlib
import math

import httpx

from nevis.domain.embeddings import EmbeddingProfileIdentity, ProviderHealth


class EmbeddingProviderUnavailable(RuntimeError):
    pass


class LocalTEIProvider:
    def __init__(self, base_url: str, profile: EmbeddingProfileIdentity) -> None:
        self._base_url = base_url.rstrip("/")
        self._profile = profile

    @property
    def profile(self) -> EmbeddingProfileIdentity:
        return self._profile

    async def healthcheck(self) -> ProviderHealth:
        try:
            async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
                response = await client.get(f"{self._base_url}/health")
                response.raise_for_status()
        except httpx.HTTPError:
            return ProviderHealth(
                available=False, provider="tei", detail="embedding runtime unavailable"
            )
        return ProviderHealth(available=True, provider="tei")

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts)

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([text]))[0]

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        try:
            async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                response = await client.post(
                    f"{self._base_url}/v1/embeddings", json={"input": texts}
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise EmbeddingProviderUnavailable("embedding runtime unavailable") from exc
        vectors = [item["embedding"] for item in payload["data"]]
        if len(vectors) != len(texts):
            raise EmbeddingProviderUnavailable("embedding runtime returned an invalid response")
        return vectors


class DeterministicFakeProvider:
    def __init__(self, profile: EmbeddingProfileIdentity) -> None:
        self._profile = profile

    @property
    def profile(self) -> EmbeddingProfileIdentity:
        return self._profile

    async def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(available=True, provider="fake")

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector_for(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._vector_for(text)

    def _vector_for(self, text: str) -> list[float]:
        digest = hashlib.shake_256(text.encode()).digest(self.profile.dimensions * 2)
        vector = [
            int.from_bytes(digest[i : i + 2], "big") / 65535 for i in range(0, len(digest), 2)
        ]
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector]
