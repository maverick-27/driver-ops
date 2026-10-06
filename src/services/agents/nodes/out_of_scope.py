from src.services.agents.prompts import OUT_OF_SCOPE_MESSAGE, UNAVAILABLE_MESSAGE
from src.services.agents.state import AgentState


async def ainvoke_out_of_scope_step(state: AgentState) -> dict:
    if state.get("guardrail_failed"):
        return {"raw_answer": UNAVAILABLE_MESSAGE, "outcome": "unavailable"}
    return {"raw_answer": OUT_OF_SCOPE_MESSAGE, "outcome": "refused"}
