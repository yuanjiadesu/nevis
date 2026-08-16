import pytest

from nevis.domain.embeddings import EmbeddingProfileIdentity
from nevis.infrastructure.embeddings import DeterministicFakeProvider


@pytest.mark.asyncio
async def test_fake_provider_is_deterministic_and_normalized() -> None:
    provider = DeterministicFakeProvider(
        EmbeddingProfileIdentity("fake", "fixture", "1", 8, "l2", 1, 1)
    )
    first = await provider.embed_query("proof of address")
    second = await provider.embed_query("proof of address")

    assert first == second
    assert len(first) == 8
    assert sum(value * value for value in first) == pytest.approx(1.0)
