"""One chunk index for BM25 and kNN. Document metadata is denormalised onto every chunk."""

from typing import Any

_KEYWORD_SUBFIELD = {"keyword": {"type": "keyword", "ignore_above": 256}}


def build_chunk_index(vector_dimension: int) -> dict[str, Any]:
    return {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "index.knn": True,
            "analysis": {
                "analyzer": {
                    "text_analyzer": {"type": "custom", "tokenizer": "standard", "filter": ["lowercase", "stop", "snowball"]},
                }
            },
        },
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "chunk_id": {"type": "keyword"},
                "doc_id": {"type": "keyword"},
                "document_uuid": {"type": "keyword"},
                "chunk_index": {"type": "integer"},
                "chunk_word_count": {"type": "integer"},
                "start_char": {"type": "integer"},
                "end_char": {"type": "integer"},
                "chunk_text": {"type": "text", "analyzer": "text_analyzer"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": vector_dimension,
                    # lucene, not nmslib: filters inside the kNN clause need an engine that supports them.
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "lucene",
                        "parameters": {"ef_construction": 512, "m": 16},
                    },
                },
                "title": {"type": "text", "analyzer": "text_analyzer", "fields": _KEYWORD_SUBFIELD},
                "doc_type": {"type": "keyword"},
                "jurisdiction": {"type": "keyword"},
                "source_url": {"type": "keyword"},
                "section_title": {"type": "keyword"},
                "embedding_model": {"type": "keyword"},
                "created_at": {"type": "date"},
            },
        },
    }


RRF_PIPELINE = {
    "description": "Post processor for hybrid RRF search",
    "phase_results_processors": [{"score-ranker-processor": {"combination": {"technique": "rrf", "rank_constant": 60}}}],
}
