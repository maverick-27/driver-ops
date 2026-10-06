import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.dependencies import ApiKeyDep, TracerDep, get_agentic_rag_service
from src.exceptions import SearchError
from src.schemas.api.ask import AgenticAskResponse, AskRequest, FeedbackRequest, FeedbackResponse
from src.services.agents.agentic_rag import AgenticRAGService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agentic"], dependencies=[ApiKeyDep])

AgenticRAGDep = Annotated[AgenticRAGService, Depends(get_agentic_rag_service)]


@router.post("/ask-agentic", response_model=AgenticAskResponse)
async def ask_agentic(request: AskRequest, service: AgenticRAGDep) -> AgenticAskResponse:
    try:
        return await service.ask(request)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    except SearchError:
        logger.exception("Search backend error")
        raise HTTPException(status_code=503, detail="Search is temporarily unavailable") from None
    except Exception:
        logger.exception("Agent run failed")
        raise HTTPException(status_code=500, detail="Internal error") from None


@router.post("/ask-agentic/stream")
async def ask_agentic_stream(request: AskRequest, service: AgenticRAGDep) -> StreamingResponse:
    """Server-sent events: "step" per finished node, "token" while the answer is written, then "final"."""

    async def events() -> AsyncIterator[str]:
        try:
            async for event in service.ask_stream(request):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except SearchError:
            logger.exception("Search backend error")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Search is temporarily unavailable'})}\n\n"
        except Exception:
            logger.exception("Agent run failed")
            yield f"data: {json.dumps({'type': 'error', 'message': 'The run failed'})}\n\n"

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.post("/feedback", response_model=FeedbackResponse)
async def feedback(request: FeedbackRequest, tracer: TracerDep) -> FeedbackResponse:
    recorded = tracer.score(request.trace_id, "user-feedback", request.score, request.comment)
    await asyncio.to_thread(tracer.flush)
    return FeedbackResponse(recorded=recorded)
