"""Plain RAG: cache, embed, search, prompt, generate. One trace span per step."""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from src.config import Settings
from src.schemas.api.ask import AskRequest, AskResponse, SourceItem
from src.services.cache.client import CacheClient, cache_key
from src.services.citations import compose_retrieval_query, sanitize_citations
from src.services.embeddings.factory import EmbeddingsClient
from src.services.langfuse.tracer import LangfuseTracer
from src.services.ollama.client import OllamaClient
from src.services.ollama.prompts import NO_RESULTS_ANSWER, RAGPromptBuilder
from src.services.opensearch.client import OpenSearchClient
from src.services.retrieval import embed_query_or_none, search

logger = logging.getLogger(__name__)


def unique_doc_ids(chunks: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for chunk in chunks:
        if chunk["doc_id"] not in seen:
            seen.append(chunk["doc_id"])
    return seen


def cited_sources(chunks: list[dict[str, Any]], cited: list[str]) -> list[SourceItem]:
    by_id = {c["doc_id"]: c for c in reversed(chunks)}
    return [
        SourceItem(
            doc_id=doc_id,
            title=by_id[doc_id].get("title", ""),
            doc_type=by_id[doc_id].get("doc_type", ""),
            jurisdiction=by_id[doc_id].get("jurisdiction", ""),
            source_url=by_id[doc_id].get("source_url"),
        )
        for doc_id in cited
        if doc_id in by_id
    ]


def request_cache_key(mode: str, request: AskRequest, model: str) -> str:
    normalized_query = " ".join(request.query.strip().split()).lower()
    normalized_prev = (" ".join(request.previous_question.strip().split()).lower() if request.previous_question else None)
    return cache_key(
        mode=mode,
        query=normalized_query,
        previous_question=normalized_prev,
        model=model,
        top_k=request.top_k,
        use_hybrid=request.use_hybrid,
        doc_types=sorted(request.doc_types or []),
    )


class RAGService:
    def __init__(
        self,
        settings: Settings,
        opensearch_client: OpenSearchClient,
        embeddings_client: EmbeddingsClient | None,
        ollama_client: OllamaClient,
        tracer: LangfuseTracer,
        cache_client: CacheClient | None,
    ):
        self.settings = settings
        self.opensearch_client = opensearch_client
        self.embeddings_client = embeddings_client
        self.ollama_client = ollama_client
        self.tracer = tracer
        self.cache_client = cache_client
        self.prompt_builder = RAGPromptBuilder()

    async def _cached(self, key: str) -> AskResponse | None:
        if self.cache_client is None:
            return None
        with self.tracer.span("cache_lookup") as span:
            data = await self.cache_client.get(key)
            span.update(output={"hit": data is not None})
        if data is None:
            return None
        return AskResponse(**{**data, "cached": True, "trace_id": self.tracer.current_trace_id()})

    async def _retrieve(self, request: AskRequest) -> dict[str, Any]:
        search_query = compose_retrieval_query(request.query, request.previous_question)
        with self.tracer.span("embed_query", input=search_query) as span:
            embedding = await embed_query_or_none(self.embeddings_client, search_query, request.use_hybrid)
            span.update(output={"embedded": embedding is not None})
        with self.tracer.span("search", input={"query": search_query, "top_k": request.top_k}) as span:
            results = await search(
                self.opensearch_client,
                search_query,
                embedding,
                size=request.top_k,
                doc_types=request.doc_types,
                use_hybrid=request.use_hybrid,
            )
            span.update(
                output={"mode": results["search_mode"], "chunks": [h["chunk_id"] for h in results["hits"]]},
            )
        return results

    def _finish(self, request: AskRequest, raw_answer: str, results: dict[str, Any]) -> AskResponse:
        chunks = results["hits"]
        retrieved = unique_doc_ids(chunks)
        answer, cited, removed = sanitize_citations(raw_answer, set(retrieved))
        if removed:
            logger.warning("Removed citations of documents that were not retrieved: %s", removed)
        return AskResponse(
            query=request.query,
            answer=answer,
            sources=cited_sources(chunks, cited),
            retrieved_doc_ids=retrieved,
            chunks_used=len(chunks),
            search_mode=results["search_mode"],
            removed_citations=removed,
            trace_id=self.tracer.current_trace_id(),
        )

    def _no_results(self, request: AskRequest, results: dict[str, Any]) -> AskResponse:
        return AskResponse(
            query=request.query,
            answer=NO_RESULTS_ANSWER,
            search_mode=results["search_mode"],
            not_found=True,
            trace_id=self.tracer.current_trace_id(),
        )

    async def _store(self, key: str, response: AskResponse) -> None:
        if self.cache_client is not None:
            await self.cache_client.set(key, response.model_dump(exclude={"cached", "trace_id"}))

    async def ask(self, request: AskRequest) -> AskResponse:
        """Raises SearchError or LLMError; the router maps them to 503."""
        model = request.model or self.settings.ollama_model
        key = request_cache_key("ask", request, model)
        with self.tracer.span("rag_request", input=request.model_dump()) as root:
            cached = await self._cached(key)
            if cached is not None:
                root.update(output={"answer": cached.answer, "cached": True})
                return cached

            results = await self._retrieve(request)
            if not results["hits"]:
                response = self._no_results(request, results)
                root.update(output={"answer": response.answer, "not_found": True})
                return response

            with self.tracer.span("build_prompt") as span:
                prompt = self.prompt_builder.build(request.query, results["hits"], request.previous_question)
                span.update(output={"prompt_chars": len(prompt)})
            with self.tracer.generation("generate", model=model, input=prompt) as generation:
                raw_answer = await self.ollama_client.generate(prompt, model=model, temperature=0.0)
                generation.update(output=raw_answer)

            response = self._finish(request, raw_answer, results)
            await self._store(key, response)
            root.update(output={"answer": response.answer, "cited": [s.doc_id for s in response.sources]})
            return response

    async def stream(self, request: AskRequest) -> AsyncIterator[str]:
        """Server-sent events: metadata, then text chunks, then the final (citation-checked) answer."""

        def event(data: dict[str, Any]) -> str:
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        model = request.model or self.settings.ollama_model
        key = request_cache_key("ask", request, model)
        try:
            with self.tracer.span("rag_stream_request", input=request.model_dump()) as root:
                cached = await self._cached(key)
                if cached is not None:
                    yield event({"retrieved_doc_ids": cached.retrieved_doc_ids, "search_mode": cached.search_mode, "cached": True})
                    for word in cached.answer.split(" "):
                        yield event({"chunk": word + " "})
                    yield event({**cached.model_dump(), "done": True})
                    return

                results = await self._retrieve(request)
                if not results["hits"]:
                    yield event({**self._no_results(request, results).model_dump(), "done": True})
                    return

                yield event(
                    {
                        "retrieved_doc_ids": unique_doc_ids(results["hits"]),
                        "chunks_used": len(results["hits"]),
                        "search_mode": results["search_mode"],
                    }
                )
                prompt = self.prompt_builder.build(request.query, results["hits"], request.previous_question)
                parts: list[str] = []
                with self.tracer.generation("generate", model=model, input=prompt) as generation:
                    async for text in self.ollama_client.generate_stream(prompt, model=model, temperature=0.0):
                        parts.append(text)
                        yield event({"chunk": text})
                    generation.update(output="".join(parts))

                response = self._finish(request, "".join(parts), results)
                await self._store(key, response)
                root.update(output={"answer": response.answer})
                yield event({**response.model_dump(), "done": True})
        except Exception:
            logger.exception("Streaming request failed")
            yield event({"error": "The service is temporarily unavailable. Please try again.", "done": True})
