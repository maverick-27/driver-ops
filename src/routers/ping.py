import asyncio

from fastapi import APIRouter

from src.dependencies import CacheDep, DatabaseDep, OllamaDep, OpenSearchDep, SettingsDep, TracerDep
from src.schemas.api.health import HealthResponse, ServiceStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(
    settings: SettingsDep,
    database: DatabaseDep,
    opensearch_client: OpenSearchDep,
    ollama_client: OllamaDep,
    cache_client: CacheDep,
    tracer: TracerDep,
) -> HealthResponse:
    services: dict[str, ServiceStatus] = {}

    # Parallel health checks for db, search, llm, cache
    async def db_check() -> bool:
        return await asyncio.to_thread(database.health_check)

    def search_status_sync() -> ServiceStatus:
        if not opensearch_client.health_check():
            return ServiceStatus(status="unhealthy")
        try:
            return ServiceStatus(status="healthy", message=f"{opensearch_client.count()} chunks indexed")
        except Exception:
            return ServiceStatus(status="unhealthy", message="index missing")

    async def search_check() -> ServiceStatus:
        return await asyncio.to_thread(search_status_sync)

    async def cache_check() -> ServiceStatus:
        if cache_client is None:
            return ServiceStatus(status="unhealthy", message="not connected; answers are not cached")
        return ServiceStatus(status="healthy" if await cache_client.ping() else "unhealthy")

    db_ok, search_status_obj, llm_health, cache_status_obj = await asyncio.gather(
        db_check(),
        search_check(),
        ollama_client.health_check(),
        cache_check(),
    )

    services["database"] = ServiceStatus(status="healthy" if db_ok else "unhealthy")
    services["search"] = search_status_obj

    llm = llm_health
    if llm["status"] != "healthy":
        services["llm"] = ServiceStatus(status="unhealthy")
    else:
        needed = [settings.ollama_model] + ([settings.embeddings.model] if settings.embeddings.provider == "ollama" else [])
        missing = [m for m in needed if not any(name == m or name.startswith(m + ":") for name in llm["models"])]
        services["llm"] = ServiceStatus(
            status="unhealthy" if missing else "healthy",
            message=f"models not pulled: {', '.join(missing)}" if missing else ", ".join(needed),
        )

    services["cache"] = cache_status_obj
    services["tracing"] = ServiceStatus(status="healthy" if tracer.enabled else "disabled")

    # Cache and tracing are optional: only the three the answer path needs decide the overall status.
    required_ok = all(services[name].status == "healthy" for name in ("database", "search", "llm"))
    return HealthResponse(
        status="ok" if required_ok else "degraded",
        version=settings.app_version,
        environment=settings.environment,
        services=services,
    )
