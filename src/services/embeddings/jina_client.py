"""Hosted Jina embeddings. Sends document text to a third party: do not use for a corpus that must stay in-house."""

import asyncio

import httpx

from src.config import EmbeddingsSettings
from src.exceptions import EmbeddingsError


class JinaEmbeddingsClient:
    URL = "https://api.jina.ai/v1/embeddings"

    def __init__(self, settings: EmbeddingsSettings):
        if not settings.jina_api_key:
            raise EmbeddingsError("EMBEDDINGS__JINA_API_KEY is not set")
        self.settings = settings
        self.model = "jina-embeddings-v3"
        self._client = httpx.AsyncClient(
            timeout=settings.timeout_seconds, headers={"Authorization": f"Bearer {settings.jina_api_key}"}
        )

    async def _embed(self, texts: list[str], task: str) -> list[list[float]]:
        payload = {"model": self.model, "task": task, "dimensions": self.settings.dimensions, "input": texts}
        last_error: Exception | None = None
        for attempt in range(1, self.settings.retries + 1):
            try:
                response = await self._client.post(self.URL, json=payload)
                response.raise_for_status()
                return [item["embedding"] for item in response.json()["data"]]
            except Exception as e:
                last_error = e
                if attempt < self.settings.retries:
                    await asyncio.sleep(attempt)
        raise EmbeddingsError(f"Embedding request failed after {self.settings.retries} attempts: {last_error}")

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 50):
            out.extend(await self._embed(texts[i : i + 50], "retrieval.passage"))
        return out

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([text], "retrieval.query"))[0]

    async def close(self) -> None:
        await self._client.aclose()
