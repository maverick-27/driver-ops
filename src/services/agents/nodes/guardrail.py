import logging

from langgraph.runtime import Runtime

from src.services.agents.context import Context
from src.services.agents.models import GuardrailScoring
from src.services.agents.nodes.utils import previous_block
from src.services.agents.prompts import GUARDRAIL_PROMPT
from src.services.agents.state import AgentState

logger = logging.getLogger(__name__)


async def ainvoke_guardrail_step(state: AgentState, runtime: Runtime[Context]) -> dict:
    ctx = runtime.context
    prompt = GUARDRAIL_PROMPT.format(question=state["original_query"], previous_block=previous_block(state))
    with ctx.tracer.generation("guardrail", model=ctx.model_name, input=prompt) as generation:
        try:
            llm = ctx.ollama_client.get_langchain_model(model=ctx.model_name, temperature=0.0)
            result = await llm.with_structured_output(GuardrailScoring).ainvoke(prompt)
            generation.update(output=result.model_dump())
            route = "continue" if result.score >= ctx.guardrail_threshold else "out_of_scope"
            return {"guardrail_result": result, "guardrail_failed": False, "routing_decision": route}
        except Exception as e:
            # Deliberate: when the scope check cannot run, nothing is answered (fail closed), and the
            # driver is told the system is down rather than that the question is out of scope.
            logger.error("Guardrail LLM call failed: %s", e)
            generation.update(output={"error": type(e).__name__})
            return {"guardrail_result": None, "guardrail_failed": True, "routing_decision": "out_of_scope"}
