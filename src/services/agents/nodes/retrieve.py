from langgraph.runtime import Runtime

from src.services.agents.context import Context
from src.services.agents.nodes.utils import search_query
from src.services.agents.state import AgentState
from src.services.retrieval import embed_query_or_none, search


async def ainvoke_retrieve_step(state: AgentState, runtime: Runtime[Context]) -> dict:
    """Search with the current query. The LLM does not decide whether to retrieve: every in-scope question is searched.

    A SearchError propagates: the service turns it into a 503 rather than a "not found" answer.
    """
    ctx = runtime.context
    query = search_query(state)
    attempt = state["retrieval_attempts"] + 1
    with ctx.tracer.span("retrieve", input={"query": query, "attempt": attempt}) as span:
        embedding = await embed_query_or_none(ctx.embeddings_client, query, ctx.use_hybrid)
        results = await search(
            ctx.opensearch_client, query, embedding, size=ctx.top_k, doc_types=ctx.doc_types, use_hybrid=ctx.use_hybrid
        )
        span.update(output={"mode": results["search_mode"], "chunks": [h["chunk_id"] for h in results["hits"]]})
    return {"retrieval_attempts": attempt, "chunks": results["hits"], "search_mode": results["search_mode"]}
