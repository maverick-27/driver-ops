from driver_ops_ingestion.common import get_database


def fetch_and_parse_documents(**context):
    """List the corpus, parse new or changed files, upsert every document to Postgres."""
    from src.services.corpus.factory import make_corpus_client
    from src.services.document_fetcher import DocumentFetcher
    from src.services.parser.factory import make_document_parser

    force = bool((context["dag_run"].conf or {}).get("force_reparse", False))
    fetcher = DocumentFetcher(make_corpus_client(), make_document_parser(), get_database())
    stats = fetcher.run(force=force)
    print(
        f"listed={stats['listed']} parsed={len(stats['parsed'])} unchanged={len(stats['unchanged'])} "
        f"failed={len(stats['failed'])} removed={len(stats['removed'])}"
    )
    for doc_id, reason in stats["failed"].items():
        print(f"  FAILED {doc_id}: {reason}")
    return stats
