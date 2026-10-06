from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.api.search import DocTypeFilter


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    previous_question: str | None = Field(None, max_length=1000, description="The question asked just before, for follow-ups")
    top_k: int = Field(5, ge=1, le=10)
    use_hybrid: bool = True
    model: str | None = Field(None, max_length=100)
    doc_types: list[DocTypeFilter] | None = None


class SourceItem(BaseModel):
    doc_id: str
    title: str
    doc_type: str
    jurisdiction: str
    source_url: str | None = None


class AskResponse(BaseModel):
    query: str
    answer: str
    sources: list[SourceItem] = Field(default_factory=list, description="Documents the answer cites")
    retrieved_doc_ids: list[str] = Field(default_factory=list, description="Documents of the retrieved chunks, in rank order")
    chunks_used: int = 0
    search_mode: Literal["bm25", "hybrid", "none"] = "none"
    refused: bool = False
    not_found: bool = False
    removed_citations: list[str] = Field(default_factory=list, description="Cited ids dropped because they were not retrieved")
    cached: bool = False
    trace_id: str | None = None


class AgenticAskResponse(AskResponse):
    reasoning_steps: list[str] = Field(default_factory=list)
    retrieval_attempts: int = 0
    rewritten_query: str | None = None
    guardrail_score: int | None = None
    execution_time: float = 0.0


class FeedbackRequest(BaseModel):
    trace_id: str = Field(..., min_length=1, max_length=100)
    score: float = Field(..., ge=0.0, le=1.0)
    comment: str | None = Field(None, max_length=1000)


class FeedbackResponse(BaseModel):
    recorded: bool
