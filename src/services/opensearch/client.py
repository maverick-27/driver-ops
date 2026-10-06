import logging
from typing import Any

from opensearchpy import OpenSearch, helpers
from opensearchpy.exceptions import NotFoundError, RequestError

from src.config import OpenSearchSettings
from src.exceptions import SearchError
from src.services.opensearch.index_config_hybrid import RRF_PIPELINE, build_chunk_index
from src.services.opensearch.query_builder import QueryBuilder

logger = logging.getLogger(__name__)


class OpenSearchClient:
    def __init__(self, settings: OpenSearchSettings):
        self.settings = settings
        self.index_name = settings.chunk_index
        self.client = OpenSearch(hosts=[settings.host], use_ssl=False, verify_certs=False, timeout=settings.timeout_seconds)

    def health_check(self) -> bool:
        try:
            return self.client.cluster.health()["status"] in ("green", "yellow")
        except Exception as e:
            logger.warning("OpenSearch health check failed: %s", e)
            return False

    def setup_indices(self, force: bool = False) -> dict[str, bool]:
        return {"index": self._create_index(force), "pipeline": self._create_pipeline(force)}

    def _create_index(self, force: bool) -> bool:
        if force and self.client.indices.exists(index=self.index_name):
            self.client.indices.delete(index=self.index_name)
        if self.client.indices.exists(index=self.index_name):
            return False
        try:
            self.client.indices.create(index=self.index_name, body=build_chunk_index(self.settings.vector_dimension))
            return True
        except RequestError as e:
            # Several API workers start at once; losing the race is fine.
            if "resource_already_exists_exception" in str(e):
                return False
            raise

    def _create_pipeline(self, force: bool) -> bool:
        path = f"/_search/pipeline/{self.settings.rrf_pipeline_name}"
        if not force:
            try:
                self.client.transport.perform_request("GET", path)
                return False
            except NotFoundError:
                pass
        self.client.transport.perform_request("PUT", path, body=RRF_PIPELINE)
        return True

    def count(self) -> int:
        return int(self.client.count(index=self.index_name)["count"])

    def search_unified(
        self,
        query: str,
        query_embedding: list[float] | None = None,
        size: int = 5,
        from_: int = 0,
        doc_types: list[str] | None = None,
        use_hybrid: bool = True,
        min_score: float = 0.0,
        highlight: bool = False,
    ) -> dict[str, Any]:
        """Single search entry point. BM25 when there is no embedding or use_hybrid is false. Raises SearchError."""
        hybrid = use_hybrid and query_embedding is not None
        try:
            if hybrid:
                builder = QueryBuilder(query, size=size, doc_types=doc_types, highlight=highlight)
                body = builder.build_hybrid(query_embedding, candidates=self.settings.hybrid_candidates)
                response = self.client.search(
                    index=self.index_name, body=body, params={"search_pipeline": self.settings.rrf_pipeline_name}
                )
            else:
                body = QueryBuilder(query, size=size, from_=from_, doc_types=doc_types, highlight=highlight).build_bm25()
                response = self.client.search(index=self.index_name, body=body)
        except Exception as e:
            raise SearchError(f"Search failed: {e}") from e

        hits = []
        for hit in response["hits"]["hits"]:
            score = hit.get("_score") or 0.0
            if hybrid and score < min_score:
                continue
            item = dict(hit["_source"])
            item["score"] = score
            item["chunk_id"] = hit["_id"]
            item["highlights"] = hit.get("highlight", {})
            hits.append(item)
        return {"total": response["hits"]["total"]["value"], "hits": hits, "search_mode": "hybrid" if hybrid else "bm25"}

    def delete_document_chunks(self, doc_id: str) -> int:
        response = self.client.delete_by_query(
            index=self.index_name, body={"query": {"term": {"doc_id": doc_id}}}, params={"refresh": "true"}
        )
        return int(response.get("deleted", 0))

    def bulk_index_chunks(self, chunks: list[dict[str, Any]]) -> int:
        actions = [{"_index": self.index_name, "_id": c["chunk_id"], "_source": c} for c in chunks]
        success, _ = helpers.bulk(self.client, actions, refresh=True)
        return int(success)
