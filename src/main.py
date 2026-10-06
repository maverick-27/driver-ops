import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import get_settings
from src.db.factory import make_database
from src.routers import agentic_ask, ask, hybrid_search, ping
from src.services.agents.factory import make_agentic_rag_service
from src.services.cache.factory import make_cache_client
from src.services.embeddings.factory import make_embeddings_client
from src.services.langfuse.factory import make_langfuse_tracer
from src.services.ollama.factory import make_ollama_client
from src.services.opensearch.factory import make_opensearch_client
from src.services.rag import RAGService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build every client once. Runs once per Uvicorn worker."""
    settings = get_settings()
    app.state.settings = settings
    app.state.database = make_database(pool_size=settings.database_pool_size)

    app.state.opensearch_client = make_opensearch_client()
    if app.state.opensearch_client.health_check():
        app.state.opensearch_client.setup_indices(force=False)
    else:
        logger.warning("OpenSearch not reachable at startup; index setup skipped")

    try:
        app.state.embeddings_client = make_embeddings_client()
    except Exception as e:
        logger.warning("Embeddings client not available, search is BM25 only: %s", e)
        app.state.embeddings_client = None
    app.state.ollama_client = make_ollama_client()
    app.state.langfuse_tracer = make_langfuse_tracer()

    # Redis is optional: without it requests are simply not cached.
    cache_client = None
    try:
        cache_client = make_cache_client(settings)
        if not await cache_client.ping():
            await cache_client.close()
            cache_client = None
    except Exception as e:
        logger.warning("Cache not available: %s", e)
        cache_client = None
    app.state.cache_client = cache_client

    clients = (
        app.state.opensearch_client,
        app.state.embeddings_client,
        app.state.ollama_client,
        app.state.langfuse_tracer,
        cache_client,
    )
    app.state.rag_service = RAGService(settings, *clients)
    # Built once here: the graph is compiled in the constructor.
    app.state.agentic_rag_service = make_agentic_rag_service(settings, *clients)

    yield

    app.state.langfuse_tracer.flush()
    if app.state.cache_client is not None:
        await app.state.cache_client.close()
    if app.state.embeddings_client is not None:
        await app.state.embeddings_client.close()
    await app.state.ollama_client.close()
    app.state.database.teardown()


app = FastAPI(title="Driver Ops", version=get_settings().app_version, lifespan=lifespan)
app.include_router(ping.router, prefix="/api/v1")
app.include_router(hybrid_search.router, prefix="/api/v1")
app.include_router(ask.router, prefix="/api/v1")
app.include_router(agentic_ask.router, prefix="/api/v1")
