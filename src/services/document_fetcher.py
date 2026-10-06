"""Ingestion orchestrator: list the corpus, parse what changed, upsert to Postgres."""

import logging
from datetime import UTC, datetime
from typing import Any

from src.db.interfaces.base import BaseDatabase
from src.repositories.document import DocumentRepository
from src.schemas.corpus import CorpusDocument
from src.services.corpus.client import CorpusClient
from src.services.parser.parser import DocumentParser

logger = logging.getLogger(__name__)


class DocumentFetcher:
    def __init__(self, corpus_client: CorpusClient, parser: DocumentParser, database: BaseDatabase):
        self.corpus_client = corpus_client
        self.parser = parser
        self.database = database

    def run(self, force: bool = False) -> dict[str, Any]:
        documents = self.corpus_client.list_documents()
        stats: dict[str, Any] = {"listed": len(documents), "parsed": [], "unchanged": [], "failed": {}, "removed": []}
        for document in documents:
            self._process(document, force, stats)

        # Deletion path: rows whose document left the corpus.
        listed = {d.doc_id for d in documents}
        with self.database.get_session() as session:
            repository = DocumentRepository(session)
            for doc_id in repository.all_doc_ids():
                if doc_id not in listed:
                    repository.delete_by_doc_id(doc_id)
                    stats["removed"].append(doc_id)
        return stats

    def _process(self, document: CorpusDocument, force: bool, stats: dict[str, Any]) -> None:
        fields: dict[str, Any] = {
            "title": document.title,
            "doc_type": document.doc_type,
            "jurisdiction": document.jurisdiction,
            "file_format": document.file_format,
            "source_url": document.source_url,
            "file_path": document.file_path,
            "extra": document.extra or None,
        }
        try:
            path = self.corpus_client.ensure_local(document)
            content_hash = self.corpus_client.content_hash(path)
            with self.database.get_session() as session:
                existing = DocumentRepository(session).get_by_doc_id(document.doc_id)
                unchanged = existing is not None and existing.content_processed and existing.content_hash == content_hash
            if unchanged and not force:
                stats["unchanged"].append(document.doc_id)
                return
            parsed = self.parser.parse(path, document.file_format)
            fields.update(
                content_hash=content_hash,
                raw_text=parsed.raw_text,
                sections=[s.model_dump() for s in parsed.sections],
                parser_used=parsed.parser_used,
                parser_metadata=parsed.metadata,
                content_processed=True,
                failure_reason=None,
                parsed_at=datetime.now(UTC),
            )
            stats["parsed"].append(document.doc_id)
        except Exception as e:
            # Still stored, metadata only, so the gap is visible in the database and the report.
            logger.warning("%s not processed: %s", document.doc_id, e)
            fields.update(content_processed=False, failure_reason=str(e)[:500], raw_text=None, sections=None, indexed_at=None)
            stats["failed"][document.doc_id] = str(e)[:300]
        with self.database.get_session() as session:
            DocumentRepository(session).upsert(document.doc_id, fields)
