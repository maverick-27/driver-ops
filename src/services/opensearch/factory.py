from functools import lru_cache

from src.config import get_settings
from src.services.opensearch.client import OpenSearchClient


@lru_cache(maxsize=1)
def make_opensearch_client() -> OpenSearchClient:
    return OpenSearchClient(get_settings().opensearch)
