import logging

from langgraph.runtime import Runtime

from src.services.agents.context import Context
from src.services.agents.models import QueryRewriteOutput
from src.services.agents.nodes.utils import previous_block
from src.services.agents.prompts import REWRITE_FALLBACK_KEYWORDS, REWRITE_PROMPT
from src.services.agents.state import AgentState

logger = logging.getLogger(__name__)


async def ainvoke_rewrite_query_step(state: AgentState, runtime: Runtime[Context]) -> dict:
    """Rewrite the ORIGINAL question for retrieval."""
    ctx = runtime.context
    prompt = REWRITE_PROMPT.format(question=state["original_query"], previous_block=previous_block(state))
    with ctx.tracer.generation("rewrite_query", model=ctx.model_name, input=prompt) as generation:
        try:
            llm = ctx.ollama_client.get_langchain_model(model=ctx.model_name, temperature=ctx.rewrite_temperature)
            result = await llm.with_structured_output(QueryRewriteOutput).ainvoke(prompt)
            rewritten = result.rewritten_query.strip()[:500]
            if not rewritten:
                raise ValueError("empty rewrite")
            generation.update(output=result.model_dump())
        except Exception as e:
            logger.warning("Rewrite LLM call failed, appending keywords: %s", e)
            generation.update(output={"error": type(e).__name__})
            rewritten = f"{state['original_query']} {REWRITE_FALLBACK_KEYWORDS}"
    return {"rewritten_query": rewritten}
