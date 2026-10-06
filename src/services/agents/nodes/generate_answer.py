import logging

from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime

from src.services.agents.context import Context
from src.services.agents.prompts import UNAVAILABLE_MESSAGE
from src.services.agents.state import AgentState

logger = logging.getLogger(__name__)


async def ainvoke_generate_answer_step(state: AgentState, runtime: Runtime[Context]) -> dict:
    """Answer from the retrieved chunks only, with the same prompt as the plain /ask path.

    Tokens are also written to the graph's custom stream, so a streaming caller can show the answer
    as it is generated. For a non-streaming run the writer does nothing.
    """
    ctx = runtime.context
    write = get_stream_writer()
    prompt = ctx.prompt_builder.build(state["original_query"], state["chunks"], state.get("previous_question"))
    with ctx.tracer.generation("generate_answer", model=ctx.model_name, input=prompt) as generation:
        try:
            parts: list[str] = []
            async for text in ctx.ollama_client.generate_stream(prompt, model=ctx.model_name, temperature=ctx.temperature):
                parts.append(text)
                write({"token": text})
            answer = "".join(parts).strip()
            generation.update(output=answer)
            return {"raw_answer": answer, "outcome": "answered"}
        except Exception as e:
            logger.error("Answer generation failed: %s", e)
            generation.update(output={"error": type(e).__name__})
            return {"raw_answer": UNAVAILABLE_MESSAGE, "outcome": "unavailable"}
