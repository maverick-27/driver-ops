"""Self-hosted embeddings through Ollama (default model bge-m3: 1024 dims, multilingual)."""

import asyncio
import hashlib
import logging
from functools import lru_cache

import httpx

from src.config import EmbeddingsSettings
from src.exceptions import EmbeddingsError

logger = logging.getLogger(__name__)


class OllamaEmbeddingsClient:
    def __init__(self, settings: EmbeddingsSettings):
        self.settings = settings
        self.model = settings.model
        self._client = httpx.AsyncClient(base_url=settings.host, timeout=settings.timeout_seconds)
        self._query_cache: dict[str, list[float]] = {}

    async def _embed(self, texts: list[str], retries: int | None = None, timeout: float | None = None) -> list[list[float]]:
        if retries is None:
            retries = self.settings.retries
        if timeout is None:
            timeout = self.settings.timeout_seconds

        client = self._client if timeout == self.settings.timeout_seconds else httpx.AsyncClient(base_url=self.settings.host, timeout=timeout)
        try:
            last_error: Exception | None = None
            for attempt in range(1, retries + 1):
                try:
                    response = await client.post("/api/embed", json={"model": self.model, "input": texts})
                    response.raise_for_status()
                    embeddings = response.json()["embeddings"]
                    if len(embeddings) != len(texts) or any(len(e) != self.settings.dimensions for e in embeddings):
                        raise EmbeddingsError("Embedding count or dimension does not match the request")
                    return embeddings
                except EmbeddingsError:
                    raise
                except Exception as e:
                    last_error = e
                    if attempt < retries:
                        await asyncio.sleep(attempt)
            raise EmbeddingsError(f"Embedding request failed after {retries} attempts: {last_error}")
        finally:
            if timeout != self.settings.timeout_seconds:
                await client.aclose()

    # bge-m3 uses the same encoding for passages and queries; the two methods keep the interface
    # that task-specific models (Jina) need.
    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.settings.batch_size):
            out.extend(await self._embed(texts[i : i + self.settings.batch_size]))
        return out

    async def embed_query(self, text: str) -> list[float]:
        normalized = " ".join(text.strip().split()).lower()
        cache_key = hashlib.sha256(f"{normalized}:{self.model}".encode()).hexdigest()[:16]
        if cache_key in self._query_cache:
            return self._query_cache[cache_key]
        embedding = (await self._embed([text], retries=self.settings.query_retries, timeout=self.settings.query_timeout_seconds))[0]
        self._query_cache[cache_key] = embedding
        if len(self._query_cache) > 256:
            oldest = next(iter(self._query_cache))
            del self._query_cache[oldest]
        return embedding

    async def close(self) -> None:
        await self._client.aclose()
