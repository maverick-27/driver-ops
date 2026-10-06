import logging

from langgraph.runtime import Runtime

from src.services.agents.context import Context
from src.services.agents.models import GradeDocuments, GradingResult
from src.services.agents.nodes.utils import previous_block
from src.services.agents.prompts import GRADE_DOCUMENTS_PROMPT
from src.services.agents.state import AgentState
from src.services.ollama.prompts import format_excerpts

logger = logging.getLogger(__name__)


async def ainvoke_grade_documents_step(state: AgentState, runtime: Runtime[Context]) -> dict:
    """One relevance judgment over the whole retrieved batch; sets the route."""
    ctx = runtime.context
    attempt = state["retrieval_attempts"]
    chunks = state["chunks"]

    if not chunks:
        grading = GradingResult(attempt=attempt, is_relevant=False, reasoning="search returned nothing")
    else:
        prompt = GRADE_DOCUMENTS_PROMPT.format(
            context=format_excerpts(chunks), question=state["original_query"], previous_block=previous_block(state)
        )
        with ctx.tracer.generation("grade_documents", model=ctx.model_name, input=prompt) as generation:
            try:
                llm = ctx.ollama_client.get_langchain_model(model=ctx.model_name, temperature=0.0)
                result = await llm.with_structured_output(GradeDocuments).ainvoke(prompt)
                generation.update(output=result.model_dump())
                grading = GradingResult(attempt=attempt, is_relevant=result.binary_score == "yes", reasoning=result.reasoning)
            except Exception as e:
                # Fallback without the LLM: there are chunks, so let generation decide what they support.
                logger.warning("Grading LLM call failed, using heuristic: %s", e)
                generation.update(output={"error": type(e).__name__})
                grading = GradingResult(attempt=attempt, is_relevant=True, reasoning="grader unavailable", by_fallback=True)

    if grading.is_relevant:
        route = "generate_answer"
    elif attempt < ctx.max_retrieval_attempts:
        route = "rewrite_query"
    else:
        route = "not_found"  # attempts exhausted: skip the rewrite whose result would never be used
    return {"grading_results": state["grading_results"] + [grading], "routing_decision": route}
