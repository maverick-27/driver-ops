"""Agentic RAG service. The graph is compiled once, here, and reused for every request."""

import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.schemas.api.ask import AgenticAskResponse, AskRequest
from src.services.agents.config import GraphConfig
from src.services.agents.context import Context
from src.services.agents.nodes.generate_answer import ainvoke_generate_answer_step
from src.services.agents.prompts import is_greeting
from src.services.agents.nodes.grade_documents import ainvoke_grade_documents_step
from src.services.agents.nodes.guardrail import ainvoke_guardrail_step
from src.services.agents.nodes.not_found import ainvoke_not_found_step
from src.services.agents.nodes.out_of_scope import ainvoke_out_of_scope_step
from src.services.agents.nodes.retrieve import ainvoke_retrieve_step
from src.services.agents.nodes.rewrite_query import ainvoke_rewrite_query_step
from src.services.agents.state import AgentState
from src.services.cache.client import CacheClient
from src.services.citations import sanitize_citations
from src.services.embeddings.factory import EmbeddingsClient
from src.services.langfuse.tracer import LangfuseTracer
from src.services.ollama.client import OllamaClient
from src.services.ollama.prompts import RAGPromptBuilder
from src.services.opensearch.client import OpenSearchClient
from src.services.rag import cited_sources, request_cache_key, unique_doc_ids

logger = logging.getLogger(__name__)


def build_graph():
    workflow = StateGraph(AgentState, context_schema=Context)
    workflow.add_node("guardrail", ainvoke_guardrail_step)
    workflow.add_node("out_of_scope", ainvoke_out_of_scope_step)
    workflow.add_node("retrieve", ainvoke_retrieve_step)
    workflow.add_node("grade_documents", ainvoke_grade_documents_step)
    workflow.add_node("rewrite_query", ainvoke_rewrite_query_step)
    workflow.add_node("generate_answer", ainvoke_generate_answer_step)
    workflow.add_node("not_found", ainvoke_not_found_step)

    workflow.add_edge(START, "guardrail")
    workflow.add_conditional_edges(
        "guardrail", lambda s: s["routing_decision"], {"continue": "retrieve", "out_of_scope": "out_of_scope"}
    )
    workflow.add_edge("out_of_scope", END)
    workflow.add_edge("retrieve", "grade_documents")
    workflow.add_conditional_edges(
        "grade_documents",
        lambda s: s["routing_decision"],
        {"generate_answer": "generate_answer", "rewrite_query": "rewrite_query", "not_found": "not_found"},
    )
    workflow.add_edge("rewrite_query", "retrieve")
    workflow.add_edge("generate_answer", END)
    workflow.add_edge("not_found", END)
    return workflow.compile()


class AgenticRAGService:
    def __init__(
        self,
        opensearch_client: OpenSearchClient,
        embeddings_client: EmbeddingsClient | None,
        ollama_client: OllamaClient,
        tracer: LangfuseTracer,
        cache_client: CacheClient | None,
        graph_config: GraphConfig,
    ):
        self.opensearch_client = opensearch_client
        self.embeddings_client = embeddings_client
        self.ollama_client = ollama_client
        self.tracer = tracer
        self.cache_client = cache_client
        self.graph_config = graph_config
        self.prompt_builder = RAGPromptBuilder()
        self.graph = build_graph()

    def get_graph_mermaid(self) -> str:
        return self.graph.get_graph().draw_mermaid()

    def _prepare(self, request: AskRequest) -> tuple[str, Context, AgentState]:
        """Cache key, per-request context and initial state for one run."""
        if not request.query.strip():
            raise ValueError("Query is empty")
        config = self.graph_config
        model = request.model or config.model
        context = Context(
            ollama_client=self.ollama_client,
            opensearch_client=self.opensearch_client,
            embeddings_client=self.embeddings_client,
            tracer=self.tracer,
            prompt_builder=self.prompt_builder,
            model_name=model,
            temperature=config.temperature,
            rewrite_temperature=config.rewrite_temperature,
            top_k=request.top_k,
            use_hybrid=request.use_hybrid,
            doc_types=list(request.doc_types) if request.doc_types else None,
            max_retrieval_attempts=config.max_retrieval_attempts,
            guardrail_threshold=config.guardrail_threshold,
        )
        state_input: AgentState = {
            "original_query": request.query.strip(),
            "previous_question": request.previous_question,
            "rewritten_query": None,
            "retrieval_attempts": 0,
            "guardrail_result": None,
            "guardrail_failed": False,
            "routing_decision": None,
            "chunks": [],
            "search_mode": "none",
            "grading_results": [],
            "raw_answer": None,
            "outcome": None,
        }
        return request_cache_key("agentic", request, model), context, state_input

    async def _store(self, key: str, state: dict[str, Any], response: AgenticAskResponse) -> None:
        # An outage answer must not be served again for six hours.
        if self.cache_client is not None and state.get("outcome") != "unavailable":
            await self.cache_client.set(key, response.model_dump(exclude={"cached", "trace_id", "execution_time"}))

    async def ask(self, request: AskRequest) -> AgenticAskResponse:
        """Raises SearchError when the search backend fails; the router maps it to 503."""
        started = time.perf_counter()
        timings: dict[str, float] = {}

        # Check for greetings first (no agent run needed)
        is_greet, greeting_response = is_greeting(request.query)
        if is_greet:
            return AgenticAskResponse(
                answer=greeting_response,
                sources=[],
                refused=False,
                not_found=False,
                cached=False,
                search_mode="none",
                retrieval_attempts=0,
                trace_id="",
                execution_time=int((time.perf_counter() - started) * 1000),
            )

        key, context, state_input = self._prepare(request)

        with self.tracer.span("agentic_rag_request", input=request.model_dump()) as root:
            trace_id = self.tracer.current_trace_id()
            if self.cache_client is not None:
                cache_start = time.perf_counter()
                with self.tracer.span("cache_lookup") as span:
                    cached = await self.cache_client.get(key)
                    span.update(output={"hit": cached is not None})
                timings["cache_lookup"] = (time.perf_counter() - cache_start) * 1000
                if cached is not None:
                    root.update(output={"answer": cached["answer"], "cached": True})
                    timings["total"] = (time.perf_counter() - started) * 1000
                    exec_time = round(timings["total"] / 1000, 3)
                    return AgenticAskResponse(
                        **{**cached, "cached": True, "trace_id": trace_id, "execution_time": exec_time, "timings": timings}
                    )

            state = await self.graph.ainvoke(state_input, context=context)
            timings["graph_invoke"] = (time.perf_counter() - started - sum(timings.values()) / 1000) * 1000
            response = self._build_response(request, state, trace_id, started, timings)
            root.update(output={"answer": response.answer, "outcome": state.get("outcome")})
            await self._store(key, state, response)
            return response

    async def ask_stream(self, request: AskRequest) -> AsyncIterator[dict[str, Any]]:
        """Yield the run as it happens: one "step" event per finished node, "token" events while the
        answer is written, then "final" with the same response ask() returns.

        No request-level trace span here: a span held open across the yields of an async generator
        cannot be closed reliably. The LLM calls inside the nodes are still traced.
        """
        started = time.perf_counter()
        key, context, state_input = self._prepare(request)
        timings: dict[str, float] = {}

        if self.cache_client is not None:
            cached = await self.cache_client.get(key)
            if cached is not None:
                timings["total"] = (time.perf_counter() - started) * 1000
                exec_time = round(timings["total"] / 1000, 3)
                response = AgenticAskResponse(**{**cached, "cached": True, "execution_time": exec_time, "timings": timings})
                yield {"type": "final", "response": response.model_dump()}
                return

        state: dict[str, Any] = dict(state_input)
        async for mode, chunk in self.graph.astream(state_input, context=context, stream_mode=["updates", "custom"]):
            if mode == "custom":
                if "token" in chunk:
                    yield {"type": "token", "text": chunk["token"]}
                continue
            for node, update in chunk.items():
                state.update(update or {})
                event = self._step_event(node, state)
                if event is not None:
                    yield event

        response = self._build_response(request, state, None, started, timings)
        await self._store(key, state, response)
        yield {"type": "final", "response": response.model_dump()}

    @staticmethod
    def _step_event(node: str, state: dict[str, Any]) -> dict[str, Any] | None:
        """What a finished node found, and which node runs next."""
        if node == "guardrail":
            result = state.get("guardrail_result")
            data = {"score": result.score if result else None, "reason": result.reason if result else None}
            next_node = "retrieve" if state["routing_decision"] == "continue" else None
            return {"type": "step", "node": node, "next": next_node, "data": data}
        if node == "retrieve":
            excerpts = []
            for hit in state["chunks"]:
                body = hit["chunk_text"].removeprefix(hit.get("title", "")).strip()
                excerpts.append(
                    {
                        "doc_id": hit["doc_id"],
                        "title": hit.get("title", ""),
                        "section": hit.get("section_title", ""),
                        "doc_type": hit.get("doc_type", ""),
                        "jurisdiction": hit.get("jurisdiction", ""),
                        "snippet": body[:260],
                    }
                )
            data = {
                "attempt": state["retrieval_attempts"],
                "query": state.get("rewritten_query") or state["original_query"],
                "search_mode": state["search_mode"],
                "excerpts": excerpts,
            }
            return {"type": "step", "node": node, "next": "grade_documents", "data": data}
        if node == "grade_documents":
            grading = state["grading_results"][-1]
            route = state["routing_decision"]
            data = {"attempt": grading.attempt, "relevant": grading.is_relevant, "reason": grading.reasoning}
            return {"type": "step", "node": node, "next": route if route != "not_found" else None, "data": data}
        if node == "rewrite_query":
            return {"type": "step", "node": node, "next": "retrieve", "data": {"query": state.get("rewritten_query")}}
        return None

    def _build_response(
        self,
        request: AskRequest,
        state: dict[str, Any],
        trace_id: str | None,
        started: float,
        timings: dict[str, float] | None = None,
    ) -> AgenticAskResponse:
        outcome = state.get("outcome")
        chunks = state.get("chunks") or []
        retrieved = unique_doc_ids(chunks)
        answer, cited, removed = state.get("raw_answer") or "", [], []
        if outcome == "answered":
            answer, cited, removed = sanitize_citations(answer, set(retrieved))
            if removed:
                logger.warning("Removed citations of documents that were not retrieved: %s", removed)

        guardrail = state.get("guardrail_result")
        steps = []
        if guardrail is not None:
            steps.append(f"Scope check: {guardrail.score}/100 ({guardrail.reason})")
        elif state.get("guardrail_failed"):
            steps.append("Scope check could not run")
        for grading in state.get("grading_results", []):
            verdict = "relevant" if grading.is_relevant else "not relevant"
            suffix = " (fallback)" if grading.by_fallback else ""
            steps.append(f"Retrieval {grading.attempt}: {verdict}{suffix} ({grading.reasoning})")
        if state.get("rewritten_query"):
            steps.append(f"Query rewritten: {state['rewritten_query']}")
        steps.append(f"Outcome: {outcome}")

        if timings is None:
            timings = {}
        timings["total"] = (time.perf_counter() - started) * 1000
        return AgenticAskResponse(
            query=request.query,
            answer=answer,
            sources=cited_sources(chunks, cited),
            retrieved_doc_ids=retrieved,
            chunks_used=len(chunks) if outcome == "answered" else 0,
            search_mode=state.get("search_mode", "none"),
            refused=outcome == "refused",
            not_found=outcome == "not_found",
            removed_citations=removed,
            trace_id=trace_id,
            reasoning_steps=steps,
            retrieval_attempts=state.get("retrieval_attempts", 0),
            rewritten_query=state.get("rewritten_query"),
            guardrail_score=guardrail.score if guardrail is not None else None,
            execution_time=round(timings["total"] / 1000, 3),
            timings=timings,
        )
