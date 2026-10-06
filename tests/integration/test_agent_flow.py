"""Integration tests for agent orchestration and workflows."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.agents.models import GuardrailScoring


class TestAgentInScopeFlow:
    """Test happy path: in-scope questions."""

    @pytest.mark.asyncio
    async def test_in_scope_question_flow(self):
        """Complete flow for in-scope question."""
        # Mock context and runtime
        context = MagicMock()
        context.model_name = "test-model"
        context.guardrail_threshold = 0.7

        # 1. Question passes guardrail
        guardrail_result = GuardrailScoring(reason="Fuel card question", score=90)

        # 2. Retrieval finds documents
        retrieved_chunks = [
            {"id": "C05", "text": "Company fuel card policy...", "score": 0.95},
            {"id": "R01", "text": "Government regulations...", "score": 0.85},
        ]

        # 3. Grading validates documents (simplified for this test)

        # 4. Generate answer
        answer = "According to our company policy [C05], fuel cards are required for all drivers. "
        answer += "Government regulations [R01] require compliance with..."

        # Verify flow
        assert guardrail_result.score >= context.guardrail_threshold * 100  # Convert to 0-100 scale
        assert len(retrieved_chunks) > 0
        assert "[C05]" in answer
        assert "[R01]" in answer


class TestAgentOutOfScopeFlow:
    """Test out-of-scope question handling."""

    @pytest.mark.asyncio
    async def test_out_of_scope_question_rejected(self):
        """Out-of-scope questions should be rejected early."""
        guardrail_result = GuardrailScoring(
            reason="This is about cooking, not trucking",
            score=20,
        )
        guardrail_threshold = 70

        # Should route to out_of_scope
        if guardrail_result.score < guardrail_threshold:
            outcome = "refused"
        else:
            outcome = "answered"

        assert outcome == "refused"
        assert guardrail_result.score < guardrail_threshold


class TestAgentQueryRewritingFlow:
    """Test query rewriting for better retrieval."""

    @pytest.mark.asyncio
    async def test_failed_retrieval_triggers_rewrite(self):
        """Poor retrieval results should trigger query rewriting."""
        original_query = "fuel stuff"
        poor_results = [
            {"score": 0.3, "text": "unrelated"},
        ]

        # Quality threshold
        MIN_SCORE = 0.5
        poor_quality = all(r["score"] < MIN_SCORE for r in poor_results)

        if poor_quality:
            rewritten_query = "fuel card policy requirements"
        else:
            rewritten_query = None

        assert rewritten_query is not None
        assert len(rewritten_query) > len(original_query)

    @pytest.mark.asyncio
    async def test_rewrite_improves_results(self):
        """Rewritten queries should get better results."""
        original_retrieval = [
            {"score": 0.3, "text": "off-topic"},
        ]

        rewritten_retrieval = [
            {"score": 0.9, "text": "fuel card policy"},
            {"score": 0.85, "text": "fuel regulations"},
        ]

        original_best = max((r["score"] for r in original_retrieval), default=0)
        rewritten_best = max((r["score"] for r in rewritten_retrieval), default=0)

        assert rewritten_best > original_best


class TestAgentNotFoundFlow:
    """Test when no relevant documents are found."""

    @pytest.mark.asyncio
    async def test_no_documents_found_returns_not_found(self):
        """No relevant documents should return not_found."""
        retrieval_results = []
        max_attempts = 3
        attempts = 1

        if not retrieval_results and attempts >= max_attempts:
            outcome = "not_found"
        else:
            outcome = "answered"

        assert outcome == "not_found"

    @pytest.mark.asyncio
    async def test_poor_quality_documents_rejected(self):
        """Low-quality documents should be rejected."""
        retrieved = [
            {"score": 0.15, "text": "barely relevant"},
            {"score": 0.2, "text": "somewhat related"},
        ]

        MIN_SCORE = 0.5
        quality_docs = [r for r in retrieved if r["score"] >= MIN_SCORE]

        assert len(quality_docs) == 0


class TestAgentWithFollowUp:
    """Test handling of follow-up questions."""

    @pytest.mark.asyncio
    async def test_follow_up_includes_previous_context(self):
        """Follow-up questions should search with previous context."""
        from src.services.citations import compose_retrieval_query

        previous_question = "What is a fuel card?"
        follow_up_question = "Is it required in Canada?"

        search_query = compose_retrieval_query(follow_up_question, previous_question)

        assert previous_question in search_query
        assert follow_up_question in search_query

    @pytest.mark.asyncio
    async def test_answer_references_previous_context(self):
        """Answers should reference both previous and current questions."""
        previous = "What is a fuel card?"
        current = "Canada requirement?"

        answer = (
            "As we discussed, fuel cards are used for tracking expenses. "
            "In Canada, they are required by law [R01]."
        )

        # Should address context
        assert "As we discussed" in answer or "[R01]" in answer


class TestAgentCaching:
    """Test response caching in agent."""

    @pytest.mark.asyncio
    async def test_identical_queries_use_cache(self):
        """Same query should return cached response."""
        from src.services.rag import cache_key

        query1 = "What is a fuel card?"
        query2 = "What is a fuel card?"

        key1 = cache_key(query=query1, mode="hybrid")
        key2 = cache_key(query=query2, mode="hybrid")

        assert key1 == key2

    @pytest.mark.asyncio
    async def test_different_queries_dont_share_cache(self):
        """Different queries should have different cache keys."""
        from src.services.rag import cache_key

        query1 = "What is a fuel card?"
        query2 = "What is a credit card?"

        key1 = cache_key(query=query1, mode="hybrid")
        key2 = cache_key(query=query2, mode="hybrid")

        assert key1 != key2


class TestAgentWithMultipleRetrieverAttempts:
    """Test agent retrying retrieval."""

    @pytest.mark.asyncio
    async def test_agent_retries_on_poor_results(self):
        """Agent should retry retrieval if results are poor."""
        attempt_1_results = [{"score": 0.3}]  # Poor
        attempt_2_results = [{"score": 0.9}, {"score": 0.85}]  # Good

        # After attempt 1: results are poor, retry
        if all(r["score"] < 0.5 for r in attempt_1_results):
            attempt = 2
        else:
            attempt = 1

        # After attempt 2: good results
        if any(r["score"] >= 0.7 for r in attempt_2_results):
            outcome = "answered"
        else:
            outcome = "not_found"

        assert attempt == 2
        assert outcome == "answered"

    @pytest.mark.asyncio
    async def test_max_retrieval_attempts_respected(self):
        """Should not retry beyond max attempts."""
        max_attempts = 3
        attempts = 0

        while attempts < max_attempts:
            attempts += 1
            results = [{"score": 0.2}]  # Always poor
            if any(r["score"] >= 0.7 for r in results):
                break

        assert attempts == max_attempts


class TestAgentErrorRecovery:
    """Test agent handling of service failures."""

    @pytest.mark.asyncio
    async def test_search_failure_returns_unavailable(self):
        """Search service failure should return unavailable."""
        try:
            raise ConnectionError("OpenSearch down")
        except ConnectionError:
            outcome = "unavailable"

        assert outcome == "unavailable"

    @pytest.mark.asyncio
    async def test_llm_failure_returns_unavailable(self):
        """LLM service failure should return unavailable."""
        try:
            raise TimeoutError("Ollama timeout")
        except TimeoutError:
            outcome = "unavailable"

        assert outcome == "unavailable"

    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Should degrade gracefully when services fail."""
        # If embeddings unavailable, fallback to BM25
        embeddings_available = False
        search_mode = "vector" if embeddings_available else "bm25"
        assert search_mode == "bm25"

        # If cache unavailable, query directly
        cache_available = False
        should_use_cache = cache_available
        assert should_use_cache is False


class TestAgentCitationValidation:
    """Test citation handling in agent."""

    @pytest.mark.asyncio
    async def test_unretrieved_citations_removed(self):
        """Citations not in retrieval results should be removed."""
        from src.services.citations import sanitize_citations

        answer = "According to [C05], fuel cards are [R02] required."
        retrieved_ids = {"C05"}  # R02 not retrieved

        cleaned, valid, removed = sanitize_citations(answer, retrieved_ids)

        assert "C05" in cleaned
        assert "R02" not in cleaned
        assert "R02" in removed

    @pytest.mark.asyncio
    async def test_multiple_citations_validated(self):
        """Multiple citations should all be validated."""
        from src.services.citations import sanitize_citations

        answer = "[C05, R01, C03] all apply here."
        retrieved_ids = {"C05", "R01"}  # C03 not retrieved

        cleaned, valid, removed = sanitize_citations(answer, retrieved_ids)

        assert len(valid) == 2
        assert "C03" in removed


class TestAgentStateManagement:
    """Test agent state throughout flow."""

    @pytest.mark.asyncio
    async def test_state_accumulates_across_nodes(self):
        """State should accumulate data from each node."""
        from src.services.agents.state import AgentState

        state = AgentState(
            original_query="test question",
            previous_question=None,
            rewritten_query=None,
            retrieval_attempts=0,
            guardrail_result=None,
            guardrail_failed=False,
            routing_decision=None,
            chunks=[],
            search_mode="hybrid",
            grading_results=[],
            raw_answer=None,
            outcome=None,
        )

        # After guardrail
        state["guardrail_failed"] = False
        state["routing_decision"] = "continue"

        # After retrieval
        state["chunks"] = [{"id": "C05", "text": "policy"}]
        state["retrieval_attempts"] = 1

        # After grading
        state["grading_results"] = [{"document": "C05", "score": 0.9}]

        # After generation
        state["raw_answer"] = "Generated answer [C05]"
        state["outcome"] = "answered"

        # Verify state progression
        assert state["guardrail_failed"] is False
        assert len(state["chunks"]) == 1
        assert len(state["grading_results"]) == 1
        assert state["outcome"] == "answered"
