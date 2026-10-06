"""Browser test fixtures: the real ui_server.py serves the page, and the API stream is mocked per test."""

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, Route

from src.services.agents.prompts import NOT_FOUND_MESSAGE as NOT_FOUND
from src.services.agents.prompts import OUT_OF_SCOPE_MESSAGE as OUT_OF_SCOPE
from src.services.agents.prompts import UNAVAILABLE_MESSAGE as UNAVAILABLE

ROOT = Path(__file__).resolve().parents[2]


HEALTH_OK = {
    "ok": True,
    "model": "gemma3:4b",
    "services": {"database": "healthy", "search": "healthy", "llm": "healthy", "cache": "healthy", "tracing": "disabled"},
}


def pytest_collection_modifyitems(items):
    for item in items:
        if "tests/e2e" in str(item.fspath).replace("\\", "/") and "live" not in item.keywords:
            item.add_marker(pytest.mark.e2e)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def ui_url():
    """Start ui_server.py (the real one) on a free port."""
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "ui_server:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(url + "/", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    else:
        proc.terminate()
        pytest.fail("ui_server did not start")
    yield url
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "permissions": ["clipboard-read", "clipboard-write"]}


# ---------- SSE helpers ----------


def sse(*events: dict, sep: str = "\n\n") -> str:
    return "".join(f"data: {json.dumps(e)}{sep}" for e in events)


def guardrail(score: int = 85, reason: str = "Trucking compliance question") -> dict:
    return {"type": "step", "node": "guardrail", "next": "retrieve", "data": {"score": score, "reason": reason}}


def retrieve(attempt: int = 1, doc_ids=("C05",), search_mode: str = "hybrid", query: str = "fuel card") -> dict:
    excerpts = [
        {
            "doc_id": d,
            "title": f"Doc {d}",
            "section": f"Section of {d}",
            "doc_type": "company_policy",
            "jurisdiction": "ON",
            "snippet": "text",
        }
        for d in doc_ids
    ]
    return {
        "type": "step", "node": "retrieve", "next": "grade_documents",
        "data": {"attempt": attempt, "query": query, "search_mode": search_mode, "excerpts": excerpts},
    }  # fmt: skip


def grade(relevant: bool = True, attempt: int = 1) -> dict:
    return {
        "type": "step", "node": "grade_documents", "next": "generate_answer" if relevant else "rewrite_query",
        "data": {"attempt": attempt, "relevant": relevant, "reason": "grader reason"},
    }  # fmt: skip


def final(**overrides) -> dict:
    response = {
        "query": "q", "answer": "Answer text.", "sources": [], "retrieved_doc_ids": [], "chunks_used": 0, "search_mode": "hybrid",
        "refused": False, "not_found": False, "removed_citations": [], "cached": False, "trace_id": None,
        "reasoning_steps": [], "retrieval_attempts": 1, "rewritten_query": None, "guardrail_score": 85, "execution_time": 1.0,
    }  # fmt: skip
    response.update(overrides)
    return {"type": "final", "response": response}


def source(doc_id="C05", title="Fuel Card Policy", doc_type="company_policy", jurisdiction="ON", url=None) -> dict:
    return {"doc_id": doc_id, "title": title, "doc_type": doc_type, "jurisdiction": jurisdiction, "source_url": url}


def answered_stream(answer="Use the fuel card for fuel only [C05].", mode="hybrid", **extra) -> str:
    return sse(
        guardrail(), retrieve(search_mode=mode), grade(),
        {"type": "token", "text": answer},
        final(answer=answer, sources=[source()], retrieved_doc_ids=["C05"], chunks_used=1, search_mode=mode, **extra),
    )  # fmt: skip


def refused_stream() -> str:
    return sse(
        guardrail(10, "Not trucking"),
        final(answer=OUT_OF_SCOPE, refused=True, search_mode="none", guardrail_score=10),
    )


def not_found_stream() -> str:
    step = {"type": "step", "node": "rewrite_query", "next": "retrieve", "data": {"query": "reworded"}}
    return sse(
        guardrail(), retrieve(), grade(False), step, retrieve(2), grade(False, 2),
        final(answer=NOT_FOUND, not_found=True, retrieval_attempts=2),
    )  # fmt: skip


def unavailable_stream() -> str:
    step = {"type": "step", "node": "guardrail", "next": None, "data": {"score": None, "reason": "unavailable"}}
    return sse(step, final(answer=UNAVAILABLE, search_mode="none", guardrail_score=None))


# ---------- Page fixtures ----------


class Chat:
    """Thin wrapper over the page that records the requests the UI sends."""

    def __init__(self, page: Page, url: str):
        self.page, self.url, self.requests = page, url, []
        self.stream_body: str | None = None
        self.stream_status = 200
        self.status_payload: dict | None = HEALTH_OK
        page.route("**/fonts.googleapis.com/**", lambda r: r.abort())
        page.route("**/fonts.gstatic.com/**", lambda r: r.abort())
        page.route("**/status", self._status)
        page.route("**/chat/stream", self._stream)

    def _status(self, route: Route):
        if self.status_payload is None:
            route.abort()
        else:
            route.fulfill(json=self.status_payload)

    def _stream(self, route: Route):
        self.requests.append(json.loads(route.request.post_data))
        route.fulfill(status=self.stream_status, content_type="text/event-stream", body=self.stream_body or "")

    def hang_stream(self):
        """Make the next /chat/stream request stay open until the page aborts it (a slow model)."""
        self.page.add_init_script(
            """
            const realFetch = window.fetch;
            window.fetch = (url, opts = {}) => {
              if (!String(url).includes('/chat/stream')) return realFetch(url, opts);
              return new Promise((resolve, reject) => {
                opts.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
              });
            };
            """
        )
        self.page.reload()

    def open(self):
        self.page.goto(self.url)
        return self

    def ask(self, question: str, body: str | None = None, status: int = 200):
        if body is not None:
            self.stream_body = body
        self.stream_status = status
        self.page.fill("#question", question)
        self.page.press("#question", "Enter")

    @property
    def last_answer(self):
        return self.page.locator("article.msg.a").last


@pytest.fixture
def chat(page: Page, ui_url: str) -> Chat:
    return Chat(page, ui_url).open()
