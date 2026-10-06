from src.config import get_settings
from src.services.ollama.client import OllamaClient


def make_ollama_client() -> OllamaClient:
    """Not cached: the client owns an httpx.AsyncClient. Call once in lifespan."""
    return OllamaClient(get_settings())
