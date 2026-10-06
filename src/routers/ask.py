import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.dependencies import ApiKeyDep, get_rag_service
from src.exceptions import LLMError, SearchError
from src.schemas.api.ask import AskRequest, AskResponse
from src.services.rag import RAGService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ask"], dependencies=[ApiKeyDep])

RAGServiceDep = Annotated[RAGService, Depends(get_rag_service)]


@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest, rag_service: RAGServiceDep) -> AskResponse:
    try:
        return await rag_service.ask(request)
    except SearchError:
        logger.exception("Search backend error")
        raise HTTPException(status_code=503, detail="Search is temporarily unavailable") from None
    except LLMError:
        logger.exception("LLM error")
        raise HTTPException(status_code=503, detail="The answer service is temporarily unavailable") from None


@router.post("/stream")
async def stream(request: AskRequest, rag_service: RAGServiceDep) -> StreamingResponse:
    return StreamingResponse(
        rag_service.stream(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
