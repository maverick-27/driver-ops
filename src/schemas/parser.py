from typing import Any

from pydantic import BaseModel, Field


class Section(BaseModel):
    title: str
    content: str
    level: int = 1


class ParsedContent(BaseModel):
    """Parser output, the same shape for PDF, HTML and Markdown."""

    raw_text: str
    sections: list[Section] = Field(default_factory=list)
    parser_used: str
    metadata: dict[str, Any] = Field(default_factory=dict)
