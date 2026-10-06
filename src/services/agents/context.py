from dataclasses import dataclass

from src.services.embeddings.factory import EmbeddingsClient
from src.services.langfuse.tracer import LangfuseTracer
from src.services.ollama.client import OllamaClient
from src.services.ollama.prompts import RAGPromptBuilder
from src.services.opensearch.client import OpenSearchClient


@dataclass
class Context:
    """Read-only dependencies and settings for one run. Built per request from GraphConfig plus request overrides."""

    ollama_client: OllamaClient
    opensearch_client: OpenSearchClient
    embeddings_client: EmbeddingsClient | None
    tracer: LangfuseTracer
    prompt_builder: RAGPromptBuilder
    model_name: str
    temperature: float = 0.0
    rewrite_temperature: float = 0.3
    top_k: int = 5
    use_hybrid: bool = True
    doc_types: list[str] | None = None
    max_retrieval_attempts: int = 2
    guardrail_threshold: int = 60
