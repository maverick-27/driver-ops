from pydantic import BaseModel


class GraphConfig(BaseModel):
    """Service-level defaults. A request may override model, top_k, use_hybrid and doc_types."""

    model: str
    temperature: float = 0.0
    rewrite_temperature: float = 0.3
    top_k: int = 5
    use_hybrid: bool = True
    max_retrieval_attempts: int = 2
    guardrail_threshold: int = 60
