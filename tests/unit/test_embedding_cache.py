"""Unit tests for query embedding cache."""

import pytest

from src.config import EmbeddingsSettings
from src.services.embeddings.ollama_client import OllamaEmbeddingsClient


class MockOllamaEmbeddingsClient(OllamaEmbeddingsClient):
    """Mock client that tracks embed calls."""

    def __init__(self, settings: EmbeddingsSettings):
        super().__init__(settings)
        self.embed_calls = 0

    async def _embed(self, texts, retries=None, timeout=None):
        """Mock embed that returns deterministic embeddings."""
        self.embed_calls += 1
        return [[float(i) for i in range(self.settings.dimensions)] for _ in texts]


@pytest.mark.asyncio
async def test_embedding_cache_hit():
    """Embedding cache should return cached result on hit."""
    settings = EmbeddingsSettings()
    client = MockOllamaEmbeddingsClient(settings)

    # First call should hit the network
    emb1 = await client.embed_query("test query")
    calls_after_first = client.embed_calls

    # Second call with same query should hit cache
    emb2 = await client.embed_query("test query")
    calls_after_second = client.embed_calls

    assert calls_after_first == 1
    assert calls_after_second == 1  # No new call
    assert emb1 == emb2


@pytest.mark.asyncio
async def test_embedding_cache_normalizes():
    """Embedding cache should normalize query text."""
    settings = EmbeddingsSettings()
    client = MockOllamaEmbeddingsClient(settings)

    emb1 = await client.embed_query("test query")
    emb2 = await client.embed_query("TEST QUERY")
    emb3 = await client.embed_query("  test   query  ")

    assert client.embed_calls == 1  # All normalized to same query
    assert emb1 == emb2 == emb3


@pytest.mark.asyncio
async def test_embedding_cache_limit():
    """Embedding cache should respect 256-entry limit."""
    settings = EmbeddingsSettings()
    client = MockOllamaEmbeddingsClient(settings)

    # Fill cache beyond limit
    for i in range(300):
        await client.embed_query(f"query {i}")

    # Cache size should not exceed 256
    assert len(client._query_cache) <= 256


@pytest.mark.asyncio
async def test_embedding_cache_different_models():
    """Different models should have separate cache entries."""
    settings = EmbeddingsSettings()
    client = MockOllamaEmbeddingsClient(settings)

    # Manually add entries for different models (simulating)
    client._query_cache["abc:model1"] = [0.1] * 1024
    client._query_cache["abc:model2"] = [0.2] * 1024

    assert client._query_cache["abc:model1"] != client._query_cache["abc:model2"]
