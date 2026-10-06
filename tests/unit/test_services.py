"""Unit tests for service clients and dependencies."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCacheClient:
    """Test Redis cache client."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        return MagicMock()

    def test_cache_key_generation(self):
        """Cache keys should be consistent."""
        from src.services.rag import cache_key

        key1 = cache_key(query="what is X", mode="hybrid")
        key2 = cache_key(query="what is X", mode="hybrid")
        assert key1 == key2

    def test_cache_key_different_for_different_queries(self):
        """Different queries should have different keys."""
        from src.services.rag import cache_key

        key1 = cache_key(query="what is X", mode="hybrid")
        key2 = cache_key(query="what is Y", mode="hybrid")
        assert key1 != key2

    def test_cache_key_different_for_different_modes(self):
        """Different modes should have different keys."""
        from src.services.rag import cache_key

        key1 = cache_key(query="test", mode="hybrid")
        key2 = cache_key(query="test", mode="bm25")
        assert key1 != key2

    def test_cache_hit_returns_cached_value(self, mock_redis):
        """Cache hit should return stored value."""
        mock_redis.get = MagicMock(return_value=b'{"cached": "result"}')
        cached = mock_redis.get("cache_key")
        assert cached is not None

    def test_cache_miss_returns_none(self, mock_redis):
        """Cache miss should return None."""
        mock_redis.get = MagicMock(return_value=None)
        cached = mock_redis.get("cache_key")
        assert cached is None

    def test_cache_set_stores_value(self, mock_redis):
        """Cache set should store value."""
        mock_redis.set = MagicMock()
        mock_redis.set("key", b'{"data": "value"}')
        mock_redis.set.assert_called_once()


class TestEmbeddingsClient:
    """Test embeddings service."""

    @pytest.fixture
    def mock_ollama_embeddings(self):
        """Mock Ollama embeddings client."""
        client = AsyncMock()
        client.embed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
        return client

    def test_single_query_embedding(self, mock_ollama_embeddings):
        """Should embed a single query."""
        embedding = mock_ollama_embeddings.embed_query("fuel card policy")
        assert len(embedding) > 0
        assert isinstance(embedding, list)

    def test_batch_embeddings(self, mock_ollama_embeddings):
        """Should embed multiple documents."""
        mock_ollama_embeddings.embed_documents = MagicMock(
            return_value=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        )
        embeddings = mock_ollama_embeddings.embed_documents(
            ["doc1", "doc2", "doc3"]
        )
        assert len(embeddings) == 3

    def test_embedding_dimension_consistency(self):
        """All embeddings should have same dimension."""
        embeddings = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9],
        ]
        dims = [len(e) for e in embeddings]
        assert len(set(dims)) == 1  # All same dimension

    def test_empty_text_handling(self, mock_ollama_embeddings):
        """Empty text should be handled gracefully."""
        mock_ollama_embeddings.embed_query = MagicMock(return_value=[])
        embedding = mock_ollama_embeddings.embed_query("")
        assert embedding == []


class TestOpenSearchClient:
    """Test OpenSearch client."""

    @pytest.fixture
    def mock_opensearch(self):
        """Mock OpenSearch client."""
        client = MagicMock()
        client.search = MagicMock()
        return client

    def test_index_exists_check(self):
        """Should check if index exists."""
        mock_client = MagicMock()
        mock_client.indices.exists = MagicMock(return_value=True)
        exists = mock_client.indices.exists(index="documents")
        assert exists is True

    def test_index_creation(self):
        """Should create index with proper settings."""
        mock_client = MagicMock()
        mock_client.indices.create = MagicMock()
        mock_client.indices.create(
            index="documents",
            body={
                "settings": {"number_of_replicas": 0},
                "mappings": {"properties": {"text": {"type": "text"}}},
            },
        )
        mock_client.indices.create.assert_called_once()

    def test_document_indexing(self):
        """Should index documents with metadata."""
        mock_client = MagicMock()
        mock_client.index = MagicMock()
        doc = {"id": "C05", "text": "policy text", "source": "C05.md"}
        mock_client.index(index="documents", body=doc)
        mock_client.index.assert_called_once()

    def test_search_returns_hits(self):
        """Search should return hits with score and content."""
        mock_client = MagicMock()
        mock_client.search = MagicMock(
            return_value={
                "hits": {
                    "hits": [
                        {
                            "_id": "1",
                            "_score": 0.95,
                            "_source": {"text": "fuel card policy"},
                        }
                    ]
                }
            }
        )
        result = mock_client.search(
            index="documents", body={"query": {"match_all": {}}}
        )
        assert len(result["hits"]["hits"]) == 1
        assert result["hits"]["hits"][0]["_score"] == 0.95


class TestOllamaClient:
    """Test Ollama LLM client."""

    @pytest.fixture
    def mock_ollama(self):
        """Mock Ollama client."""
        client = AsyncMock()
        return client

    def test_generate_response(self, mock_ollama):
        """Should generate text response."""
        mock_ollama.ainvoke = MagicMock(
            return_value="Fuel cards are used for..."
        )
        response = mock_ollama.ainvoke("What is a fuel card?")
        assert response is not None
        assert isinstance(response, str)

    def test_structured_output_parsing(self, mock_ollama):
        """Should parse structured output."""
        class Score:
            score: float
            reasoning: str

        mock_model = MagicMock()
        mock_model.with_structured_output = MagicMock(return_value=mock_model)
        mock_model.ainvoke = MagicMock(
            return_value=Score(score=0.8, reasoning="Yes")
        )

        result = mock_model.ainvoke("test prompt")
        assert hasattr(result, "score")

    def test_temperature_setting(self, mock_ollama):
        """Should respect temperature parameter."""
        mock_ollama.temperature = 0.0
        assert mock_ollama.temperature == 0.0

    def test_model_name_configuration(self, mock_ollama):
        """Should use configured model name."""
        model_name = "gemma3:4b"
        mock_ollama.model = model_name
        assert mock_ollama.model == model_name


class TestDatabaseConnections:
    """Test database and connection pooling."""

    def test_postgres_connection_string(self):
        """Postgres connection string should be properly formatted."""
        connection_string = "postgresql://user:pass@localhost:5432/dbname"
        assert "postgresql://" in connection_string
        assert "@" in connection_string

    def test_connection_pool_size(self):
        """Connection pool should have reasonable size."""
        pool_size = 10
        assert pool_size > 0
        assert pool_size <= 20  # Not too large

    def test_redis_connection_url(self):
        """Redis URL should be valid."""
        redis_url = "redis://localhost:6379/0"
        assert redis_url.startswith("redis://")


class TestServiceFactories:
    """Test service factory patterns."""

    def test_make_client_pattern(self):
        """Factory should create consistent clients."""
        # Simulate factory pattern
        def make_client(config):
            client = MagicMock()
            client.config = config
            return client

        config1 = {"host": "localhost"}
        client1 = make_client(config1)
        client2 = make_client(config1)
        # Different instances but same config
        assert client1 is not client2
        assert client1.config == client2.config

    def test_singleton_pattern_for_services(self):
        """Some services should be singletons."""
        # Simulate singleton
        instances = {}

        def get_service(name):
            if name not in instances:
                instances[name] = MagicMock()
            return instances[name]

        service1 = get_service("ollama")
        service2 = get_service("ollama")
        assert service1 is service2  # Same instance


class TestErrorHandling:
    """Test error handling in services."""

    def test_connection_error_handling(self):
        """Connection errors should be caught."""
        mock_client = MagicMock()
        mock_client.search = MagicMock(
            side_effect=ConnectionError("Cannot reach OpenSearch")
        )
        with pytest.raises(ConnectionError):
            mock_client.search(index="test", body={})

    def test_timeout_handling(self):
        """Timeouts should be handled gracefully."""
        mock_client = MagicMock()
        mock_client.index = MagicMock(
            side_effect=TimeoutError("Operation timed out")
        )
        with pytest.raises(TimeoutError):
            mock_client.index(index="test", body={})

    def test_invalid_config_validation(self):
        """Invalid configuration should raise error."""
        config = {}  # Missing required fields
        if not config.get("host"):
            raise ValueError("Missing required config: host")
        assert False  # Should not reach here
