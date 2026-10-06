from src.config import Settings
from src.services.agents.agentic_rag import AgenticRAGService
from src.services.agents.config import GraphConfig
from src.services.cache.client import CacheClient
from src.services.embeddings.factory import EmbeddingsClient
from src.services.langfuse.tracer import LangfuseTracer
from src.services.ollama.client import OllamaClient
from src.services.opensearch.client import OpenSearchClient


def make_agentic_rag_service(
    settings: Settings,
    opensearch_client: OpenSearchClient,
    embeddings_client: EmbeddingsClient | None,
    ollama_client: OllamaClient,
    tracer: LangfuseTracer,
    cache_client: CacheClient | None,
) -> AgenticRAGService:
    graph_config = GraphConfig(
        model=settings.ollama_model,
        temperature=settings.agent.temperature,
        rewrite_temperature=settings.agent.rewrite_temperature,
        top_k=settings.agent.top_k,
        max_retrieval_attempts=settings.agent.max_retrieval_attempts,
        guardrail_threshold=settings.agent.guardrail_threshold,
    )
    return AgenticRAGService(opensearch_client, embeddings_client, ollama_client, tracer, cache_client, graph_config)
