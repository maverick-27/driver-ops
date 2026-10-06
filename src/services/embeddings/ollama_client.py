"""Self-hosted embeddings through Ollama (default model bge-m3: 1024 dims, multilingual)."""

import asyncio
import logging

import httpx

from src.config import EmbeddingsSettings
from src.exceptions import EmbeddingsError

logger = logging.getLogger(__name__)


class OllamaEmbeddingsClient:
    def __init__(self, settings: EmbeddingsSettings):
        self.settings = settings
        self.model = settings.model
        self._client = httpx.AsyncClient(base_url=settings.host, timeout=settings.timeout_seconds)

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        last_error: Exception | None = None
        for attempt in range(1, self.settings.retries + 1):
            try:
                response = await self._client.post("/api/embed", json={"model": self.model, "input": texts})
                response.raise_for_status()
                embeddings = response.json()["embeddings"]
                if len(embeddings) != len(texts) or any(len(e) != self.settings.dimensions for e in embeddings):
                    raise EmbeddingsError("Embedding count or dimension does not match the request")
                return embeddings
            except EmbeddingsError:
                raise
            except Exception as e:
                last_error = e
                if attempt < self.settings.retries:
                    await asyncio.sleep(attempt)
        raise EmbeddingsError(f"Embedding request failed after {self.settings.retries} attempts: {last_error}")

    # bge-m3 uses the same encoding for passages and queries; the two methods keep the interface
    # that task-specific models (Jina) need.
    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.settings.batch_size):
            out.extend(await self._embed(texts[i : i + self.settings.batch_size]))
        return out

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([text]))[0]

    async def close(self) -> None:
        await self._client.aclose()
