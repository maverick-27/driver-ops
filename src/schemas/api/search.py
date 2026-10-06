from typing import Literal

from pydantic import BaseModel, Field

DocTypeFilter = Literal["regulation", "company_policy"]


class HybridSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    size: int = Field(5, ge=1, le=20)
    from_: int = Field(0, ge=0, le=200, alias="from")
    doc_types: list[DocTypeFilter] | None = Field(None, description="Restrict to regulations or company policies")
    use_hybrid: bool = True
    min_score: float = Field(0.0, ge=0.0)

    model_config = {"populate_by_name": True}


class SearchHit(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    doc_type: str
    jurisdiction: str
    section_title: str = ""
    source_url: str | None = None
    chunk_text: str
    score: float
    highlights: dict[str, list[str]] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    total: int
    hits: list[SearchHit]
    search_mode: Literal["bm25", "hybrid"]
    size: int
