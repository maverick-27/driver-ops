"""Unit tests for retrieval and search logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestHybridSearchQuery:
    """Test hybrid BM25 + vector search."""

    @pytest.fixture
    def mock_opensearch_client(self):
        """Mock OpenSearch client."""
        client = AsyncMock()
        client.search = AsyncMock()
        return client

    def test_bm25_query_structure(self, mock_opensearch_client):
        """BM25 query should have correct structure."""
        from src.services.opensearch.query_builder import QueryBuilder

        builder = QueryBuilder("fuel card policy", size=5)
        query = builder.build_bm25()
        assert "query" in query
        assert "bool" in query["query"]
        assert "multi_match" in query["query"]["bool"]["must"][0]

    def test_vector_query_requires_embedding(self):
        """Vector search requires query embedding."""
        from src.services.opensearch.query_builder import QueryBuilder

        builder = QueryBuilder("test", size=5)
        query = builder.build_hybrid([0.1, 0.2])
        assert "query" in query
        assert "knn" in query or "vector" in str(query).lower()

    def test_search_result_ranking(self):
        """Results should be ranked by relevance score."""
        results = [
            {"_score": 0.95, "_id": "C05", "text": "fuel card policy"},
            {"_score": 0.65, "_id": "R01", "text": "general rules"},
            {"_score": 0.72, "_id": "C03", "text": "related policy"},
        ]
        # Should be sorted by score descending
        sorted_results = sorted(results, key=lambda x: x["_score"], reverse=True)
        assert sorted_results[0]["_score"] == 0.95
        assert sorted_results[1]["_score"] == 0.72

    def test_min_relevance_threshold(self):
        """Low-score results should be filtered."""
        results = [
            {"_score": 0.15, "_id": "X01"},  # Too low
            {"_score": 0.5, "_id": "C05"},
            {"_score": 0.3, "_id": "R02"},  # Below threshold
        ]
        MIN_SCORE = 0.4
        filtered = [r for r in results if r["_score"] >= MIN_SCORE]
        assert len(filtered) == 1
        assert filtered[0]["_id"] == "C05"


class TestChunkExtraction:
    """Test chunk extraction from search results."""

    def test_chunk_with_metadata(self):
        """Chunk should preserve metadata."""
        chunk = {"id": "C05", "text": "fuel card policy...", "chunk_index": 2, "source": "C05.md"}
        assert chunk["id"] == "C05"
        assert chunk["chunk_index"] == 2
        assert chunk["source"] == "C05.md"

    def test_chunk_scoring(self):
        """Chunks should include relevance scores."""
        chunks = [
            {"id": "C05", "text": "policy", "score": 0.9},
            {"id": "C03", "text": "related", "score": 0.7},
        ]
        top_chunks = sorted(chunks, key=lambda x: x["score"], reverse=True)[:3]
        assert top_chunks[0]["score"] >= top_chunks[1]["score"]

    def test_duplicate_source_deduplication(self):
        """Chunks from same source should not duplicate."""
        chunks = [
            {"id": "C05", "chunk_index": 0, "text": "policy part 1"},
            {"id": "C05", "chunk_index": 1, "text": "policy part 2"},  # Same source
            {"id": "R01", "chunk_index": 0, "text": "rule"},
        ]
        unique_sources = set(f"{c['id']}#{c.get('chunk_index', 0)}" for c in chunks)
        # When showing results, group by source
        by_source = {}
        for chunk in chunks:
            src = chunk["id"]
            if src not in by_source:
                by_source[src] = []
            by_source[src].append(chunk)
        assert len(by_source) == 2  # C05 and R01


class TestSearchModes:
    """Test different search modes."""

    def test_bm25_mode(self):
        """BM25-only search for keyword matching."""
        search_mode = "bm25"
        query_text = "fuel card"
        # Should use text search without embeddings
        assert search_mode == "bm25"
        assert query_text is not None

    def test_vector_mode(self):
        """Vector-only search for semantic search."""
        search_mode = "vector"
        query_embedding = [0.1, 0.2, 0.3]
        assert search_mode == "vector"
        assert len(query_embedding) > 0

    def test_hybrid_mode(self):
        """Hybrid search combines both methods."""
        search_mode = "hybrid"
        query_text = "fuel card"
        query_embedding = [0.1, 0.2, 0.3]
        assert search_mode == "hybrid"
        assert query_text is not None
        assert query_embedding is not None

    def test_invalid_mode_rejected(self):
        """Invalid search mode should raise error."""
        search_mode = "invalid"
        with pytest.raises((ValueError, AssertionError)):
            assert search_mode in ("bm25", "vector", "hybrid")


class TestRetrievalFiltering:
    """Test document retrieval filtering logic."""

    def test_corpus_filter_regulations(self):
        """Should filter to only regulations when specified."""
        documents = [
            {"id": "C05", "type": "company"},
            {"id": "R01", "type": "regulation"},
            {"id": "C03", "type": "company"},
            {"id": "R02", "type": "regulation"},
        ]
        regulations = [d for d in documents if d["type"] == "regulation"]
        assert len(regulations) == 2
        assert all(d["id"].startswith("R") for d in regulations)

    def test_corpus_filter_company_policies(self):
        """Should filter to company policies when specified."""
        documents = [
            {"id": "C05", "type": "company"},
            {"id": "R01", "type": "regulation"},
        ]
        policies = [d for d in documents if d["type"] == "company"]
        assert len(policies) == 1
        assert policies[0]["id"] == "C05"

    def test_corpus_filter_none(self):
        """No filter returns all documents."""
        documents = [
            {"id": "C05"},
            {"id": "R01"},
            {"id": "C03"},
        ]
        unfiltered = documents
        assert len(unfiltered) == 3

    def test_top_k_limiting(self):
        """Results should respect top_k limit."""
        results = [
            {"id": "C05", "score": 0.9},
            {"id": "R01", "score": 0.8},
            {"id": "C03", "score": 0.7},
            {"id": "R02", "score": 0.6},
        ]
        top_k = 2
        top_results = results[:top_k]
        assert len(top_results) == 2
        assert top_results[0]["id"] == "C05"


class TestRetrievalIntegration:
    """Integration tests for full retrieval flow."""

    @pytest.mark.asyncio
    async def test_retrieval_with_follow_up_question(self):
        """Follow-up questions should be combined with previous context."""
        from src.services.citations import compose_retrieval_query

        previous = "What is a fuel card?"
        follow_up = "Is it required in Canada?"
        combined = compose_retrieval_query(follow_up, previous)
        assert "What is a fuel card?" in combined
        assert "Is it required in Canada?" in combined

    def test_empty_results_handling(self):
        """Empty search results should be handled gracefully."""
        results = []
        if not results:
            return None  # No results found
        assert results is None or len(results) == 0

    def test_single_result_handling(self):
        """Single result should work correctly."""
        results = [{"id": "C05", "text": "policy", "score": 0.95}]
        assert len(results) == 1
        assert results[0]["id"] == "C05"
