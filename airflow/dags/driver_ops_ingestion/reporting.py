from driver_ops_ingestion.common import get_database, get_opensearch_client


def generate_report(**context):
    """Combine task stats with what is actually in Postgres and the index. Fails the run on indexing errors."""
    from src.repositories.document import DocumentRepository

    ti = context["ti"]
    fetch_stats = ti.xcom_pull(task_ids="fetch_and_parse_documents") or {}
    index_stats = ti.xcom_pull(task_ids="index_documents") or {}

    with get_database().get_session() as session:
        repository = DocumentRepository(session)
        counts = repository.counts()
        unprocessed = {d.doc_id: d.failure_reason for d in repository.unprocessed()}

    report = {
        "documents_in_db": counts,
        "chunks_in_index": get_opensearch_client().count(),
        "parsed_this_run": fetch_stats.get("parsed", []),
        "unprocessed_documents": unprocessed,
        "indexed_this_run": index_stats.get("documents", 0),
        "chunks_indexed_this_run": index_stats.get("chunks_indexed", 0),
        "indexing_errors": index_stats.get("errors", {}),
    }
    print("=== Driver Ops ingestion report ===")
    for key, value in report.items():
        print(f"{key}: {value}")
    if unprocessed:
        print(f"WARNING: {len(unprocessed)} document(s) are stored but NOT searchable: {sorted(unprocessed)}")
    if report["indexing_errors"]:
        raise RuntimeError(f"Indexing errors: {report['indexing_errors']}")
    return report
