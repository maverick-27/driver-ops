"""Driver Ops chat page for trying the agent without Telegram.

    uv run python ui_server.py        ->  http://127.0.0.1:7861

Serves ui/index.html and forwards questions to the API, adding the API key here so it never reaches the browser.
"""

from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from src.config import get_settings

API_BASE_URL = "http://localhost:8000"
INDEX = Path(__file__).parent / "ui" / "index.html"

settings = get_settings()
app = FastAPI(title="Driver Ops chat", docs_url=None, redoc_url=None)
client = httpx.AsyncClient(
    base_url=API_BASE_URL, headers={"X-API-Key": settings.api_key} if settings.api_key else {}, timeout=180
)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    previous_question: str | None = Field(None, max_length=1000)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(INDEX, headers={"Cache-Control": "no-store"})


@app.get("/status")
async def status() -> dict:
    try:
        response = await client.get("/api/v1/health", timeout=8)
        response.raise_for_status()
        health = response.json()
        services = {name: s["status"] for name, s in health.get("services", {}).items()}
        return {"ok": health.get("status") == "ok", "services": services, "model": settings.ollama_model}
    except httpx.HTTPError:
        return {"ok": False, "services": {}, "model": settings.ollama_model}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Pass the API's event stream through unchanged."""

    async def events():
        try:
            async with client.stream("POST", "/api/v1/ask-agentic/stream", json=request.model_dump()) as response:
                response.raise_for_status()
                async for chunk in response.aiter_raw():
                    yield chunk
        except httpx.HTTPError:
            yield b'data: {"type": "error", "message": "The Driver Ops API did not answer"}\n\n'

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/chat")
async def chat(request: ChatRequest) -> dict:
    try:
        response = await client.post("/api/v1/ask-agentic", json=request.model_dump())
        response.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="The Driver Ops API did not answer") from None
    return response.json()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=7861, log_level="warning")
