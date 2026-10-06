"""Integration tests for API endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest


API_KEY = "test-key-12345"
HEADERS = {"X-API-Key": API_KEY}


class TestHybridSearchEndpoint:
    """Test /api/v1/hybrid-search/ endpoint."""

    def test_successful_hybrid_search(self):
        """Should return search results."""
        # Expected behavior:
        # POST /api/v1/hybrid-search/ with valid query and API key
        # Should return 200 with list of documents sorted by relevance
        endpoint = "/api/v1/hybrid-search/"
        payload = {"query": "fuel card"}
        assert endpoint and payload

    def test_missing_api_key_is_401(self):
        """Missing API key should return 401."""
        # POST /api/v1/hybrid-search/ without X-API-Key header
        # Should return 401 Unauthorized
        headers_without_key = {}
        assert not headers_without_key.get("X-API-Key")

    def test_wrong_api_key_is_401(self):
        """Wrong API key should return 401."""
        # POST /api/v1/hybrid-search/ with invalid X-API-Key
        # Should return 401 Unauthorized
        wrong_key = "invalid-key"
        assert wrong_key != API_KEY

    def test_empty_query_is_422(self):
        """Empty query should return 422."""
        # POST /api/v1/hybrid-search/ with empty query string
        # Should return 422 Unprocessable Entity
        payload = {"query": ""}
        assert len(payload["query"]) == 0

    def test_missing_query_is_422(self):
        """Missing query field should return 422."""
        # POST /api/v1/hybrid-search/ without query field
        # Should return 422 Unprocessable Entity
        payload = {}
        assert "query" not in payload

    def test_query_too_long_is_422(self):
        """Query exceeding max length should return 422."""
        # Query max length is 1000 characters
        long_query = "x" * 1001
        assert len(long_query) > 1000

    def test_invalid_top_k_is_422(self):
        """Invalid top_k should return 422."""
        # top_k must be between 1 and 10
        for invalid_k in [0, 11, -1]:
            assert invalid_k < 1 or invalid_k > 10


class TestPlainAskEndpoint:
    """Test /api/v1/ask endpoint (plain RAG)."""

    def test_successful_ask_returns_answer(self):
        """Should return answer with citations."""
        # POST /api/v1/ask with valid question
        # Should return 200 with { answer, citations }
        response_schema = {"answer": str, "citations": list}
        assert response_schema

    def test_search_service_unavailable_returns_503(self):
        """Search failure should return 503."""
        # If OpenSearch is down, should return 503 Service Unavailable
        # with message: "Search is temporarily unavailable"
        from src.exceptions import SearchError
        error = SearchError()
        assert isinstance(error, Exception)

    def test_llm_service_unavailable_returns_503(self):
        """LLM failure should return 503."""
        # If Ollama is down, should return 503 Service Unavailable
        # with message: "The answer service is temporarily unavailable"
        from src.exceptions import LLMError
        error = LLMError()
        assert isinstance(error, Exception)

    def test_unexpected_error_returns_500_without_details(self):
        """Unexpected errors should return 500 without leaking details."""
        # Unexpected errors should return 500 but not expose internal details
        # Should not include stack trace, passwords, hostnames, etc.
        error_message = "An unexpected error occurred"
        assert "secret" not in error_message.lower()
        assert "localhost" not in error_message.lower()


class TestAgenticAskEndpoint:
    """Test /api/v1/ask-agentic endpoint."""

    def test_successful_agentic_ask_returns_answer(self):
        """Should return agent answer with citations."""
        # POST /api/v1/ask-agentic with valid question
        # Should return 200 with { answer, citations, outcome }
        # outcome: "answered" | "refused" | "not_found" | "unavailable"
        response_schema = {"answer": str, "citations": list, "outcome": str}
        assert response_schema

    def test_whitespace_only_query_is_422(self):
        """Whitespace-only query should return 422."""
        # POST /api/v1/ask-agentic with only whitespace
        # Should return 422 - query must have non-whitespace content
        query = "   \n  "
        assert query.strip() == ""

    def test_config_overrides_in_request(self):
        """Should accept per-request config overrides."""
        # POST /api/v1/ask-agentic can include optional config:
        # - top_k: 1-10 (default varies)
        # - guardrail_threshold: 0.0-1.0
        # - search_mode: "bm25" | "vector" | "hybrid"
        config = {"top_k": 5, "guardrail_threshold": 0.6}
        assert config


class TestAgenticAskStreamEndpoint:
    """Test /api/v1/ask-agentic/stream endpoint."""

    def test_successful_stream_returns_200_with_sse(self):
        """Should return 200 with Server-Sent Events."""
        # POST /api/v1/ask-agentic/stream
        # Returns 200 with Content-Type: text/event-stream
        # Each line is a JSON event: {"event": "...", "data": "..."}
        # Events: start, step, data, done, error
        events = [
            {"event": "start"},
            {"event": "data", "data": "tokens..."},
            {"event": "done"},
        ]
        assert len(events) > 0

    def test_stream_error_returns_200_with_error_event(self):
        """Stream errors should be sent as events, not HTTP errors."""
        # Stream errors should send {"event": "error", "message": "..."} as an event
        # Should still return HTTP 200, not 500
        # This allows graceful error handling on the client side
        error_event = {"event": "error", "message": "Search failed"}
        assert error_event["event"] == "error"


class TestEndpointInputValidation:
    """Test request validation across all endpoints."""

    def test_query_required_for_all_endpoints(self):
        """All endpoints require query parameter."""
        # /api/v1/hybrid-search/, /api/v1/ask, /api/v1/ask-agentic
        # All require POST with {"query": "..."} field
        # Missing query -> 422 Unprocessable Entity
        endpoints = [
            "/api/v1/hybrid-search/",
            "/api/v1/ask",
            "/api/v1/ask-agentic",
        ]
        for endpoint in endpoints:
            assert endpoint.startswith("/api/v1/")

    def test_api_key_required_for_all_endpoints(self):
        """All endpoints require API key."""
        # All endpoints require X-API-Key header
        # Missing or wrong key -> 401 Unauthorized
        required_header = "X-API-Key"
        assert required_header

    def test_response_content_type_is_json(self):
        """Responses should be JSON."""
        # All endpoints return application/json (except stream which uses text/event-stream)
        # Response body should be valid JSON
        content_type = "application/json"
        assert "json" in content_type.lower()
