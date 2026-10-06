"""The one retrieval path shared by the search endpoint, /ask and the agent."""

import asyncio
import logging
from typing import Any

from src.services.embeddings.factory import EmbeddingsClient
from src.services.opensearch.client import OpenSearchClient

logger = logging.getLogger(__name__)


async def embed_query_or_none(embeddings_client: EmbeddingsClient | None, query: str, use_hybrid: bool) -> list[float] | None:
    """Query embedding, or None when hybrid is off or the embedder is down (search then degrades to BM25)."""
    if not use_hybrid or embeddings_client is None:
        return None
    try:
        return await embeddings_client.embed_query(query)
    except Exception as e:
        logger.warning("Query embedding failed, falling back to BM25: %s", e)
        return None


async def search(
    opensearch_client: OpenSearchClient,
    query: str,
    query_embedding: list[float] | None,
    size: int,
    doc_types: list[str] | None = None,
    use_hybrid: bool = True,
    from_: int = 0,
    min_score: float = 0.0,
) -> dict[str, Any]:
    """Run the search off the event loop (the OpenSearch client is synchronous). Raises SearchError."""
    return await asyncio.to_thread(
        opensearch_client.search_unified,
        query=query,
        query_embedding=query_embedding,
        size=size,
        from_=from_,
        doc_types=doc_types,
        use_hybrid=use_hybrid,
        min_score=min_score,
    )
