"""HTTP-level failure mapping, with stub services on app.state (no Docker, Ollama or OpenSearch needed)."""

import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from src.exceptions import LLMError, SearchError
from src.routers import agentic_ask, ask, hybrid_search

KEY = "test-key"
HEADERS = {"X-API-Key": KEY}


class Boom:
    """A service whose every call raises the given error."""

    def __init__(self, error: Exception):
        self.error = error

    async def ask(self, request):
        raise self.error

    async def ask_stream(self, request):
        raise self.error
        yield  # pragma: no cover

    async def stream(self, request):
        yield json.dumps({"never": "reached"})


def make_app(agentic: object, rag: object | None = None) -> FastAPI:
    app = FastAPI()
    for router in (hybrid_search.router, ask.router, agentic_ask.router):
        app.include_router(router, prefix="/api/v1")
    app.state.settings = SimpleNamespace(api_key=KEY)
    app.state.agentic_rag_service = agentic
    app.state.rag_service = rag or agentic
    app.state.opensearch_client = None
    app.state.embeddings_client = None
    return app


def client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.parametrize("path", ["/api/v1/ask", "/api/v1/ask-agentic", "/api/v1/ask-agentic/stream", "/api/v1/hybrid-search/"])
async def test_missing_or_wrong_key_is_401(path):
    async with client(make_app(Boom(SearchError()))) as c:
        assert (await c.post(path, json={"query": "x"})).status_code == 401
        assert (await c.post(path, json={"query": "x"}, headers={"X-API-Key": "wrong"})).status_code == 401


@pytest.mark.parametrize("path", ["/api/v1/ask", "/api/v1/ask-agentic", "/api/v1/ask-agentic/stream"])
@pytest.mark.parametrize(
    "body", [{}, {"query": ""}, {"query": "x" * 1001}, {"query": "ok", "top_k": 0}, {"query": "ok", "top_k": 11}]
)
async def test_invalid_body_is_422(path, body):
    async with client(make_app(Boom(SearchError()))) as c:
        assert (await c.post(path, json=body, headers=HEADERS)).status_code == 422


async def test_whitespace_query_is_422_on_agentic():
    async with client(make_app(Boom(ValueError("Query is empty")))) as c:
        r = await c.post("/api/v1/ask-agentic", json={"query": "   "}, headers=HEADERS)
    assert r.status_code == 422


async def test_agentic_search_error_is_503_without_internals():
    async with client(make_app(Boom(SearchError("opensearch at 10.0.0.5 refused")))) as c:
        r = await c.post("/api/v1/ask-agentic", json={"query": "x"}, headers=HEADERS)
    assert r.status_code == 503
    assert r.json() == {"detail": "Search is temporarily unavailable"}


async def test_agentic_unexpected_error_is_500_without_internals():
    async with client(make_app(Boom(RuntimeError("secret detail")))) as c:
        r = await c.post("/api/v1/ask-agentic", json={"query": "x"}, headers=HEADERS)
    assert r.status_code == 500
    assert "secret" not in r.text


async def test_plain_ask_maps_search_and_llm_errors_to_503():
    for error, detail in [
        (SearchError(), "Search is temporarily unavailable"),
        (LLMError(), "The answer service is temporarily unavailable"),
    ]:
        async with client(make_app(Boom(error))) as c:
            r = await c.post("/api/v1/ask", json={"query": "x"}, headers=HEADERS)
        assert (r.status_code, r.json()["detail"]) == (503, detail)


@pytest.mark.parametrize(
    ("error", "message"),
    [(SearchError(), "Search is temporarily unavailable"), (RuntimeError("secret"), "The run failed")],
)
async def test_agentic_stream_failure_is_an_error_event_with_status_200(error, message):
    async with client(make_app(Boom(error))) as c:
        r = await c.post("/api/v1/ask-agentic/stream", json={"query": "x"}, headers=HEADERS)
    assert r.status_code == 200
    events = [json.loads(line[5:]) for line in r.text.split("\n\n") if line.startswith("data:")]
    assert events == [{"type": "error", "message": message}]
    assert "secret" not in r.text


async def test_hybrid_search_validation_limits():
    async with client(make_app(Boom(SearchError()))) as c:
        for body in (
            {"query": "x", "size": 0},
            {"query": "x", "size": 21},
            {"query": "x", "from": 201},
            {"query": "x", "doc_types": ["memo"]},
        ):
            assert (await c.post("/api/v1/hybrid-search/", json=body, headers=HEADERS)).status_code == 422


async def test_no_key_configured_skips_auth():
    app = make_app(Boom(SearchError()))
    app.state.settings = SimpleNamespace(api_key="")
    async with client(app) as c:
        assert (await c.post("/api/v1/ask-agentic", json={"query": "x"})).status_code == 503
