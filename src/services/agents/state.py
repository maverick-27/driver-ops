from typing import Any, TypedDict

from src.services.agents.models import GradingResult, GuardrailScoring


class AgentState(TypedDict):
    """What the nodes change. Dependencies and per-request settings live in Context."""

    original_query: str
    previous_question: str | None
    rewritten_query: str | None
    retrieval_attempts: int
    guardrail_result: GuardrailScoring | None
    guardrail_failed: bool
    routing_decision: str | None
    chunks: list[dict[str, Any]]
    search_mode: str
    grading_results: list[GradingResult]
    raw_answer: str | None
    outcome: str | None  # answered | refused | not_found | unavailable
