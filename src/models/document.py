import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.db.interfaces.postgresql import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Document(Base):
    """One corpus document: a regulation (R01..) or a company policy (C01..)."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(String, unique=True, nullable=False, index=True)  # natural key, also the citation id
    title = Column(String, nullable=False)
    doc_type = Column(String, nullable=False, index=True)  # "regulation" | "company_policy"
    jurisdiction = Column(String, nullable=False)
    file_format = Column(String, nullable=False)  # html | pdf | md
    source_url = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)
    extra = Column(JSONB, nullable=True)  # front matter of company documents (version, owner, effective date)

    raw_text = Column(Text, nullable=True)
    sections = Column(JSONB, nullable=True)
    parser_used = Column(String, nullable=True)
    parser_metadata = Column(JSONB, nullable=True)
    content_processed = Column(Boolean, default=False, nullable=False)
    failure_reason = Column(Text, nullable=True)
    parsed_at = Column(DateTime(timezone=True), nullable=True)
    indexed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)
