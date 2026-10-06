"""Unit tests for agent node functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.models import GuardrailScoring
from src.services.agents.nodes.guardrail import ainvoke_guardrail_step
from src.services.agents.state import AgentState


@pytest.fixture
def mock_context():
    """Mock Context with all required attributes."""
    context = MagicMock()
    context.ollama_client = MagicMock()
    context.model_name = "test-model"
    context.guardrail_threshold = 0.7
    context.tracer = MagicMock()
    context.tracer.generation = MagicMock()
    context.tracer.generation.return_value.__enter__ = MagicMock(return_value=MagicMock())
    context.tracer.generation.return_value.__exit__ = MagicMock(return_value=None)
    return context


@pytest.fixture
def mock_runtime(mock_context):
    """Mock LangGraph Runtime."""
    runtime = MagicMock()
    runtime.context = mock_context
    return runtime


@pytest.fixture
def sample_state():
    """Sample agent state."""
    return AgentState(
        original_query="What is a fuel card?",
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


class TestGuardrailNode:
    """Test guardrail/scope-checking node."""

    @pytest.mark.asyncio
    async def test_guardrail_passes_when_score_above_threshold(self, mock_runtime, sample_state):
        """Question passes scope check when score >= threshold."""
        result = GuardrailScoring(reason="This is about truck fuel cards", score=80)
        mock_model = AsyncMock()
        mock_model.with_structured_output.return_value.ainvoke = AsyncMock(return_value=result)
        mock_runtime.context.ollama_client.get_langchain_model.return_value = mock_model

        output = await ainvoke_guardrail_step(sample_state, mock_runtime)

        assert output["guardrail_result"] == result
        assert output["guardrail_failed"] is False
        assert output["routing_decision"] == "continue"

    @pytest.mark.asyncio
    async def test_guardrail_fails_when_score_below_threshold(self, mock_runtime, sample_state):
        """Question fails scope check when score < threshold."""
        result = GuardrailScoring(reason="This is about cooking", score=20)
        mock_model = AsyncMock()
        mock_model.with_structured_output.return_value.ainvoke = AsyncMock(return_value=result)
        mock_runtime.context.ollama_client.get_langchain_model.return_value = mock_model

        output = await ainvoke_guardrail_step(sample_state, mock_runtime)

        assert output["guardrail_result"] == result
        assert output["guardrail_failed"] is False
        assert output["routing_decision"] == "out_of_scope"

    @pytest.mark.asyncio
    async def test_guardrail_failure_fails_closed(self, mock_runtime, sample_state):
        """LLM error fails closed with out_of_scope routing."""
        mock_model = AsyncMock()
        mock_model.with_structured_output.return_value.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))
        mock_runtime.context.ollama_client.get_langchain_model.return_value = mock_model

        output = await ainvoke_guardrail_step(sample_state, mock_runtime)

        assert output["guardrail_result"] is None
        assert output["guardrail_failed"] is True
        assert output["routing_decision"] == "out_of_scope"

    @pytest.mark.asyncio
    async def test_guardrail_passes_at_exact_threshold(self, mock_runtime, sample_state):
        """Score exactly at threshold should pass."""
        result = GuardrailScoring(reason="Borderline question", score=70)
        mock_model = AsyncMock()
        mock_model.with_structured_output.return_value.ainvoke = AsyncMock(return_value=result)
        mock_runtime.context.ollama_client.get_langchain_model.return_value = mock_model

        output = await ainvoke_guardrail_step(sample_state, mock_runtime)

        assert output["routing_decision"] == "continue"


class TestGuardrailPromptGeneration:
    """Test that guardrail receives correct prompt with context."""

    @pytest.mark.asyncio
    async def test_guardrail_includes_question_in_prompt(self, mock_runtime, sample_state):
        """Prompt should include the original question."""
        mock_model = AsyncMock()
        mock_model.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=GuardrailScoring(reasoning="", score=0.9, reasoning_en="")
        )
        mock_runtime.context.ollama_client.get_langchain_model.return_value = mock_model

        await ainvoke_guardrail_step(sample_state, mock_runtime)

        # Check that the prompt was created with the question
        call_args = mock_model.with_structured_output.return_value.ainvoke.call_args
        prompt = call_args[0][0]
        assert sample_state["original_query"] in prompt

    @pytest.mark.asyncio
    async def test_guardrail_handles_empty_question(self, mock_runtime):
        """Edge case: empty question should still work."""
        state = AgentState(
            original_query="",
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
        mock_model = AsyncMock()
        mock_model.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=GuardrailScoring(reasoning="Empty", score=0.1, reasoning_en="Empty")
        )
        mock_runtime.context.ollama_client.get_langchain_model.return_value = mock_model

        output = await ainvoke_guardrail_step(state, mock_runtime)
        assert output["guardrail_failed"] is False  # Should still process


class TestNodeErrorHandling:
    """Test error handling and resilience."""

    @pytest.mark.asyncio
    async def test_llm_timeout_handled_gracefully(self, mock_runtime, sample_state):
        """Timeout should be caught and handled."""
        mock_model = AsyncMock()
        mock_model.with_structured_output.return_value.ainvoke = AsyncMock(
            side_effect=TimeoutError("LLM call timed out")
        )
        mock_runtime.context.ollama_client.get_langchain_model.return_value = mock_model

        output = await ainvoke_guardrail_step(sample_state, mock_runtime)
        assert output["guardrail_failed"] is True

    @pytest.mark.asyncio
    async def test_malformed_response_handled(self, mock_runtime, sample_state):
        """Invalid response format should be handled."""
        mock_model = AsyncMock()
        mock_model.with_structured_output.return_value.ainvoke = AsyncMock(side_effect=ValueError("Invalid JSON"))
        mock_runtime.context.ollama_client.get_langchain_model.return_value = mock_model

        output = await ainvoke_guardrail_step(sample_state, mock_runtime)
        assert output["guardrail_failed"] is True
