import logging

from fastapi import APIRouter, HTTPException

from src.dependencies import ApiKeyDep, EmbeddingsDep, OpenSearchDep
from src.exceptions import SearchError
from src.schemas.api.search import HybridSearchRequest, SearchHit, SearchResponse
from src.services.retrieval import embed_query_or_none, search

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hybrid-search", tags=["search"], dependencies=[ApiKeyDep])


@router.post("/", response_model=SearchResponse)
async def hybrid_search(
    request: HybridSearchRequest, opensearch_client: OpenSearchDep, embeddings_client: EmbeddingsDep
) -> SearchResponse:
    query_embedding = await embed_query_or_none(embeddings_client, request.query, request.use_hybrid)
    try:
        results = await search(
            opensearch_client,
            request.query,
            query_embedding,
            size=request.size,
            doc_types=request.doc_types,
            use_hybrid=request.use_hybrid,
            from_=request.from_,
            min_score=request.min_score,
            highlight=True,
        )
    except SearchError:
        logger.exception("Search backend error")
        raise HTTPException(status_code=503, detail="Search is temporarily unavailable") from None
    return SearchResponse(
        query=request.query,
        total=results["total"],
        hits=[SearchHit(**{k: v for k, v in hit.items() if k in SearchHit.model_fields}) for hit in results["hits"]],
        search_mode=results["search_mode"],
        size=request.size,
    )
