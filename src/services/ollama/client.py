import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from src.config import Settings
from src.exceptions import LLMError

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama over HTTP. One reused connection pool; build once at startup."""

    def __init__(self, settings: Settings):
        self.base_url = settings.ollama_host
        self.default_model = settings.ollama_model
        self.num_ctx = settings.ollama_num_ctx
        self.timeout = settings.ollama_timeout
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)

    async def health_check(self) -> dict[str, Any]:
        try:
            response = await self._client.get("/api/tags", timeout=5.0)
            response.raise_for_status()
            models = [m["name"] for m in response.json().get("models", [])]
            return {"status": "healthy", "models": models}
        except Exception as e:
            logger.warning("Ollama health check failed: %s", e)
            return {"status": "unhealthy", "models": []}

    def _payload(self, prompt: str, model: str | None, temperature: float, top_p: float, stream: bool) -> dict[str, Any]:
        return {
            "model": model or self.default_model,
            "prompt": prompt,
            "stream": stream,
            "options": {"temperature": temperature, "top_p": top_p, "num_ctx": self.num_ctx},
        }

    async def generate(self, prompt: str, model: str | None = None, temperature: float = 0.0, top_p: float = 0.9) -> str:
        try:
            response = await self._client.post("/api/generate", json=self._payload(prompt, model, temperature, top_p, False))
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except Exception as e:
            raise LLMError(f"Generation failed: {e}") from e

    async def generate_stream(
        self, prompt: str, model: str | None = None, temperature: float = 0.0, top_p: float = 0.9
    ) -> AsyncIterator[str]:
        try:
            async with self._client.stream(
                "POST", "/api/generate", json=self._payload(prompt, model, temperature, top_p, True)
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("response"):
                        yield data["response"]
                    if data.get("done"):
                        break
        except Exception as e:
            raise LLMError(f"Streaming generation failed: {e}") from e

    def get_langchain_model(self, model: str | None = None, temperature: float = 0.0):
        """Chat model for the agent nodes; supports with_structured_output."""
        from langchain_ollama import ChatOllama

        return ChatOllama(
            base_url=self.base_url,
            model=model or self.default_model,
            temperature=temperature,
            num_ctx=self.num_ctx,
            client_kwargs={"timeout": self.timeout},
        )

    async def close(self) -> None:
        await self._client.aclose()
