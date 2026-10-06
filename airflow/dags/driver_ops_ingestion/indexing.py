import asyncio

from driver_ops_ingestion.common import get_database, get_opensearch_client


def index_documents(**context):
    """Chunk, embed and index every parsed document that is not in the index in its current version.

    Selection is by the indexed_at / parsed_at columns, not by row recency, so an updated old
    document is picked up and an unchanged one is skipped.
    """
    from src.config import get_settings
    from src.repositories.document import DocumentRepository
    from src.services.cache.client import flush_cache_sync
    from src.services.indexing.factory import make_hybrid_indexer

    conf = context["dag_run"].conf or {}
    force = bool(conf.get("force_reindex", False))
    database = get_database()
    opensearch_client = get_opensearch_client()
    fetch_stats = context["ti"].xcom_pull(task_ids="fetch_and_parse_documents") or {}

    # Chunks of documents that left the corpus or no longer parse must not stay searchable.
    stale = list(fetch_stats.get("removed", [])) + list(fetch_stats.get("failed", {}).keys())
    for doc_id in stale:
        opensearch_client.delete_document_chunks(doc_id)

    async def run() -> list[dict]:
        indexer = make_hybrid_indexer()
        results = []
        try:
            with database.get_session() as session:
                documents = DocumentRepository(session).pending_index(force=force)
                session.expunge_all()
            for document in documents:
                try:
                    result = await indexer.index_document(document)
                except Exception as e:
                    result = {"doc_id": document.doc_id, "chunks": 0, "indexed": 0, "error": str(e)[:300]}
                if result.get("indexed"):
                    with database.get_session() as session:
                        DocumentRepository(session).mark_indexed(document.doc_id)
                print(result)
                results.append(result)
        finally:
            if indexer.embeddings_client is not None:
                await indexer.embeddings_client.close()
        return results

    results = asyncio.run(run())
    stats = {
        "documents": len(results),
        "chunks_indexed": sum(r.get("indexed", 0) for r in results),
        "errors": {r["doc_id"]: r["error"] for r in results if r.get("error")},
        "embedded": all(r.get("embedded", False) for r in results) if results else None,
        "stale_removed": stale,
    }

    # Cached answers were built from the old index.
    if stats["chunks_indexed"] or stale:
        try:
            stats["cache_keys_flushed"] = flush_cache_sync(get_settings().redis)
        except Exception as e:
            print(f"cache flush skipped: {e}")
    return stats
