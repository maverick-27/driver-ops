"""Unit tests for request cache key normalization."""

import pytest

from src.schemas.api.ask import AskRequest
from src.services.rag import request_cache_key


class TestRequestCacheKey:
    def test_cache_key_normalizes_whitespace(self):
        """Whitespace variations should produce the same key."""
        req1 = AskRequest(query="what is compliance?")
        req2 = AskRequest(query="what   is   compliance?")
        req3 = AskRequest(query="  what is compliance?  ")

        key1 = request_cache_key("ask", req1, "gemma3:4b")
        key2 = request_cache_key("ask", req2, "gemma3:4b")
        key3 = request_cache_key("ask", req3, "gemma3:4b")

        assert key1 == key2 == key3

    def test_cache_key_normalizes_case(self):
        """Case variations should produce the same key."""
        req1 = AskRequest(query="What is compliance?")
        req2 = AskRequest(query="what is compliance?")

        key1 = request_cache_key("ask", req1, "gemma3:4b")
        key2 = request_cache_key("ask", req2, "gemma3:4b")

        assert key1 == key2

    def test_cache_key_none_vs_empty_previous(self):
        """None and empty string previous_question should produce the same key."""
        req1 = AskRequest(query="follow up?", previous_question=None)
        req2 = AskRequest(query="follow up?", previous_question="")

        key1 = request_cache_key("ask", req1, "gemma3:4b")
        key2 = request_cache_key("ask", req2, "gemma3:4b")

        assert key1 == key2

    def test_cache_key_different_models(self):
        """Different models should produce different keys."""
        req = AskRequest(query="what is compliance?")

        key1 = request_cache_key("ask", req, "gemma3:4b")
        key2 = request_cache_key("ask", req, "llama2")

        assert key1 != key2

    def test_cache_key_different_modes(self):
        """Different modes should produce different keys."""
        req = AskRequest(query="what is compliance?")

        key1 = request_cache_key("ask", req, "gemma3:4b")
        key2 = request_cache_key("agentic", req, "gemma3:4b")

        assert key1 != key2

    def test_cache_key_respects_previous_question(self):
        """Different previous_question should produce different keys."""
        req1 = AskRequest(query="follow up?", previous_question="first question")
        req2 = AskRequest(query="follow up?", previous_question="different question")

        key1 = request_cache_key("ask", req1, "gemma3:4b")
        key2 = request_cache_key("ask", req2, "gemma3:4b")

        assert key1 != key2
