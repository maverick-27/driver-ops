from src.config import get_settings
from src.services.embeddings.jina_client import JinaEmbeddingsClient
from src.services.embeddings.ollama_client import OllamaEmbeddingsClient

EmbeddingsClient = OllamaEmbeddingsClient | JinaEmbeddingsClient


def make_embeddings_client() -> EmbeddingsClient | None:
    """Not cached: each client owns an httpx.AsyncClient tied to its caller's event loop. None means BM25 only."""
    settings = get_settings().embeddings
    if settings.provider == "none":
        return None
    if settings.provider == "jina":
        return JinaEmbeddingsClient(settings)
    return OllamaEmbeddingsClient(settings)
