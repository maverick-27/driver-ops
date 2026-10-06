import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from src.config import Settings
from src.db.interfaces.base import BaseDatabase
from src.services.agents.agentic_rag import AgenticRAGService
from src.services.cache.client import CacheClient
from src.services.embeddings.factory import EmbeddingsClient
from src.services.langfuse.tracer import LangfuseTracer
from src.services.ollama.client import OllamaClient
from src.services.opensearch.client import OpenSearchClient
from src.services.rag import RAGService


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> BaseDatabase:
    return request.app.state.database


def get_opensearch_client(request: Request) -> OpenSearchClient:
    return request.app.state.opensearch_client


def get_embeddings_client(request: Request) -> EmbeddingsClient | None:
    return request.app.state.embeddings_client


def get_ollama_client(request: Request) -> OllamaClient:
    return request.app.state.ollama_client


def get_cache_client(request: Request) -> CacheClient | None:
    return request.app.state.cache_client


def get_tracer(request: Request) -> LangfuseTracer:
    return request.app.state.langfuse_tracer


def get_rag_service(request: Request) -> RAGService:
    return request.app.state.rag_service


def get_agentic_rag_service(request: Request) -> AgenticRAGService:
    return request.app.state.agentic_rag_service


def require_api_key(request: Request, x_api_key: Annotated[str | None, Header()] = None) -> None:
    expected = request.app.state.settings.api_key
    if not expected:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid API key")


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
DatabaseDep = Annotated[BaseDatabase, Depends(get_database)]
OpenSearchDep = Annotated[OpenSearchClient, Depends(get_opensearch_client)]
EmbeddingsDep = Annotated[EmbeddingsClient | None, Depends(get_embeddings_client)]
OllamaDep = Annotated[OllamaClient, Depends(get_ollama_client)]
CacheDep = Annotated[CacheClient | None, Depends(get_cache_client)]
TracerDep = Annotated[LangfuseTracer, Depends(get_tracer)]
RAGServiceDep = Annotated[RAGService, Depends(get_rag_service)]
AgenticRAGServiceDep = Annotated[AgenticRAGService, Depends(get_agentic_rag_service)]
ApiKeyDep = Depends(require_api_key)
