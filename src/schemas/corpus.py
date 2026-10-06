from typing import Any, Literal

from pydantic import BaseModel, Field

DocType = Literal["regulation", "company_policy"]


class CorpusDocument(BaseModel):
    """One entry of the corpus: a manifest row or a company policy file."""

    doc_id: str
    title: str
    doc_type: DocType
    jurisdiction: str
    file_format: Literal["html", "pdf", "md"]
    source_url: str | None = None
    file_path: str
    extra: dict[str, Any] = Field(default_factory=dict)
