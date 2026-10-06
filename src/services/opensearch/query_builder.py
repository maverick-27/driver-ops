from typing import Any

BM25_FIELDS = ["chunk_text^3", "title^2"]
_SOURCE = {"excludes": ["embedding"]}
_HIGHLIGHT = {
    "fields": {"chunk_text": {"fragment_size": 150, "number_of_fragments": 2, "pre_tags": ["<mark>"], "post_tags": ["</mark>"]}}
}


class QueryBuilder:
    def __init__(self, query: str, size: int = 5, from_: int = 0, doc_types: list[str] | None = None, highlight: bool = False):
        self.query = query.strip()
        self.size = size
        self.from_ = from_
        self.doc_types = doc_types or []
        self.highlight = highlight

    def filters(self) -> list[dict[str, Any]]:
        return [{"terms": {"doc_type": self.doc_types}}] if self.doc_types else []

    def bm25_query(self) -> dict[str, Any]:
        if self.query:
            must: list[dict[str, Any]] = [
                {
                    "multi_match": {
                        "query": self.query,
                        "fields": BM25_FIELDS,
                        "type": "best_fields",
                        "operator": "or",
                        "fuzziness": "AUTO",
                        "prefix_length": 2,
                    }
                }
            ]
        else:
            must = [{"match_all": {}}]
        return {"bool": {"must": must, "filter": self.filters()}}

    def build_bm25(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "query": self.bm25_query(),
            "size": self.size,
            "from": self.from_,
            "track_total_hits": True,
            "_source": _SOURCE,
        }
        if self.highlight:
            body["highlight"] = _HIGHLIGHT
        return body

    def build_hybrid(self, query_embedding: list[float], candidates: int | None = None) -> dict[str, Any]:
        candidates = max(candidates or 0, self.size * 2)
        knn: dict[str, Any] = {"vector": query_embedding, "k": candidates}
        if self.doc_types:
            # Same filter as the BM25 clause, so vector hits cannot bypass it.
            knn["filter"] = {"bool": {"filter": self.filters()}}
        body: dict[str, Any] = {
            "size": self.size,
            "query": {
                "hybrid": {"queries": [self.bm25_query(), {"knn": {"embedding": knn}}], "pagination_depth": candidates}
            },
            "_source": _SOURCE,
        }
        if self.highlight:
            body["highlight"] = _HIGHLIGHT
        return body
