from src.services.agents.prompts import NOT_FOUND_MESSAGE
from src.services.agents.state import AgentState


async def ainvoke_not_found_step(state: AgentState) -> dict:
    """Retrieval attempts are used up and nothing relevant was found: fixed answer, no LLM."""
    return {"raw_answer": NOT_FOUND_MESSAGE, "outcome": "not_found"}
