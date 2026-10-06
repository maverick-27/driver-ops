from typing import Literal

from pydantic import BaseModel, Field


class GuardrailScoring(BaseModel):
    score: int = Field(..., ge=0, le=100, description="How clearly the question is in scope, 0-100")
    reason: str = Field(..., description="One short sentence")


class GradeDocuments(BaseModel):
    binary_score: Literal["yes", "no"] = Field(..., description="'yes' if the excerpts help answer the question")
    reasoning: str = Field(..., description="One short sentence")


class QueryRewriteOutput(BaseModel):
    rewritten_query: str = Field(..., description="The search query, in English")
    reasoning: str = Field(..., description="One short sentence")


class GradingResult(BaseModel):
    attempt: int
    is_relevant: bool
    reasoning: str
    by_fallback: bool = False
