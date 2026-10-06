"""Unit tests for OpenSearch QueryBuilder."""

import pytest

from src.services.opensearch.query_builder import QueryBuilder


class TestQueryBuilder:
    def test_bm25_no_highlight(self):
        """BM25 query should not include highlight by default."""
        builder = QueryBuilder("test query", highlight=False)
        body = builder.build_bm25()

        assert "highlight" not in body
        assert body["_source"] == {"excludes": ["embedding"]}

    def test_bm25_with_highlight(self):
        """BM25 query should include highlight when enabled."""
        builder = QueryBuilder("test query", highlight=True)
        body = builder.build_bm25()

        assert "highlight" in body
        assert body["highlight"]["fields"]["chunk_text"]["fragment_size"] == 150

    def test_hybrid_no_highlight(self):
        """Hybrid query should not include highlight by default."""
        builder = QueryBuilder("test query", highlight=False)
        embedding = [0.1] * 1024
        body = builder.build_hybrid(embedding)

        assert "highlight" not in body
        assert body["_source"] == {"excludes": ["embedding"]}

    def test_hybrid_with_highlight(self):
        """Hybrid query should include highlight when enabled."""
        builder = QueryBuilder("test query", highlight=True)
        embedding = [0.1] * 1024
        body = builder.build_hybrid(embedding)

        assert "highlight" in body
        assert body["highlight"]["fields"]["chunk_text"]["fragment_size"] == 150

    def test_query_builder_tracks_total_hits(self):
        """BM25 should track total hits for accurate counts."""
        builder = QueryBuilder("test query")
        body = builder.build_bm25()

        assert body["track_total_hits"] is True

    def test_query_builder_respects_size(self):
        """Query builder should respect size parameter."""
        builder = QueryBuilder("test query", size=10)
        body = builder.build_bm25()

        assert body["size"] == 10

    def test_query_builder_respects_from(self):
        """Query builder should respect from parameter."""
        builder = QueryBuilder("test query", from_=20)
        body = builder.build_bm25()

        assert body["from"] == 20
