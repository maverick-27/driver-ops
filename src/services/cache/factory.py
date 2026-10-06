from src.config import Settings
from src.services.cache.client import CacheClient


def make_cache_client(settings: Settings) -> CacheClient:
    return CacheClient(settings.redis)
