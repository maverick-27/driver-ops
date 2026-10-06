"""Chunk, embed and index one document. Re-indexing deletes the document's old chunks first."""

import logging
from datetime import UTC, datetime
from typing import Any

from src.models.document import Document
from src.schemas.parser import Section
from src.services.embeddings.factory import EmbeddingsClient
from src.services.indexing.text_chunker import TextChunker
from src.services.opensearch.client import OpenSearchClient

logger = logging.getLogger(__name__)


class HybridIndexer:
    def __init__(self, chunker: TextChunker, opensearch_client: OpenSearchClient, embeddings_client: EmbeddingsClient | None):
        self.chunker = chunker
        self.opensearch_client = opensearch_client
        self.embeddings_client = embeddings_client

    async def index_document(self, document: Document) -> dict[str, Any]:
        sections = [Section(**s) for s in (document.sections or [])]
        chunks = self.chunker.chunk_document(document.title, document.raw_text or "", sections)
        if not chunks:
            return {"doc_id": document.doc_id, "chunks": 0, "indexed": 0, "error": "no chunks"}

        embeddings: list[list[float]] | None = None
        if self.embeddings_client is not None:
            embeddings = await self.embeddings_client.embed_passages([c.text for c in chunks])
            if len(embeddings) != len(chunks):
                return {"doc_id": document.doc_id, "chunks": len(chunks), "indexed": 0, "error": "embedding count mismatch"}

        now = datetime.now(UTC).isoformat()
        payload = []
        for i, chunk in enumerate(chunks):
            item: dict[str, Any] = {
                "chunk_id": f"{document.doc_id}_{chunk.chunk_index}",  # deterministic: a re-run overwrites
                "doc_id": document.doc_id,
                "document_uuid": str(document.id),
                "chunk_index": chunk.chunk_index,
                "chunk_word_count": chunk.word_count,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "chunk_text": chunk.text,
                "title": document.title,
                "doc_type": document.doc_type,
                "jurisdiction": document.jurisdiction,
                "section_title": chunk.section_title,
                "created_at": now,
            }
            if document.source_url:
                item["source_url"] = document.source_url
            if embeddings is not None:
                item["embedding"] = embeddings[i]
                item["embedding_model"] = self.embeddings_client.model
            payload.append(item)

        self.opensearch_client.delete_document_chunks(document.doc_id)
        indexed = self.opensearch_client.bulk_index_chunks(payload)
        return {"doc_id": document.doc_id, "chunks": len(chunks), "indexed": indexed, "embedded": embeddings is not None}
