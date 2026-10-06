from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.models.document import Document


class DocumentRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_doc_id(self, doc_id: str) -> Document | None:
        return self.session.execute(select(Document).where(Document.doc_id == doc_id)).scalars().first()

    def upsert(self, doc_id: str, fields: dict[str, Any]) -> Document:
        document = self.get_by_doc_id(doc_id)
        if document is None:
            document = Document(doc_id=doc_id, **fields)
            self.session.add(document)
        else:
            for key, value in fields.items():
                setattr(document, key, value)
        self.session.flush()
        return document

    def all_doc_ids(self) -> list[str]:
        return list(self.session.execute(select(Document.doc_id)).scalars())

    def delete_by_doc_id(self, doc_id: str) -> None:
        document = self.get_by_doc_id(doc_id)
        if document is not None:
            self.session.delete(document)

    def pending_index(self, force: bool = False) -> list[Document]:
        """Parsed documents that are not in the index yet, or were re-parsed since they were indexed."""
        query = select(Document).where(Document.content_processed.is_(True))
        if not force:
            query = query.where(or_(Document.indexed_at.is_(None), Document.indexed_at < Document.parsed_at))
        return list(self.session.execute(query.order_by(Document.doc_id)).scalars())

    def mark_indexed(self, doc_id: str) -> None:
        document = self.get_by_doc_id(doc_id)
        if document is not None:
            document.indexed_at = datetime.now(UTC)

    def counts(self) -> dict[str, int]:
        total = self.session.execute(select(func.count()).select_from(Document)).scalar() or 0
        processed = (
            self.session.execute(select(func.count()).select_from(Document).where(Document.content_processed.is_(True))).scalar()
            or 0
        )
        indexed = (
            self.session.execute(select(func.count()).select_from(Document).where(Document.indexed_at.isnot(None))).scalar() or 0
        )
        return {"total": total, "processed": processed, "unprocessed": total - processed, "indexed": indexed}

    def unprocessed(self) -> list[Document]:
        return list(
            self.session.execute(select(Document).where(Document.content_processed.is_(False)).order_by(Document.doc_id)).scalars()
        )
