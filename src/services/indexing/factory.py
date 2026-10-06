from src.config import get_settings
from src.services.embeddings.factory import make_embeddings_client
from src.services.indexing.hybrid_indexer import HybridIndexer
from src.services.indexing.text_chunker import TextChunker
from src.services.opensearch.factory import make_opensearch_client


def make_hybrid_indexer() -> HybridIndexer:
    return HybridIndexer(TextChunker(get_settings().chunking), make_opensearch_client(), make_embeddings_client())
