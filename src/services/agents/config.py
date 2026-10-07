from pydantic import BaseModel


class GraphConfig(BaseModel):
    """Service-level defaults. A request may override model, top_k, use_hybrid and doc_types.

    Optimized for Phase 1:
    - max_retrieval_attempts: 1 (skip retry loop for speed)
    - top_k: 3 (reduced from 5; fewer chunks to grade)
    - guardrail_threshold: 65 (higher confidence gate)
    - use_hybrid: True (BM25 + vector search is fast)
    """

    model: str
    temperature: float = 0.0
    rewrite_temperature: float = 0.3
    top_k: int = 3  # Reduced from 5 for speed
    use_hybrid: bool = True
    max_retrieval_attempts: int = 1  # Reduced from 2: skip retry for speed
    guardrail_threshold: int = 65  # Increased from 60: higher confidence
