from src.services.agents.state import AgentState
from src.services.citations import compose_retrieval_query


def previous_block(state: AgentState) -> str:
    previous = state.get("previous_question")
    return f"Driver's previous question (context only): {previous}\n" if previous else ""


def search_query(state: AgentState) -> str:
    """The rewritten query once there is one, else the question (joined with the one before it for a follow-up)."""
    return state.get("rewritten_query") or compose_retrieval_query(state["original_query"], state.get("previous_question"))
