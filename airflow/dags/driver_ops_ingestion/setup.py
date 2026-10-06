from driver_ops_ingestion.common import get_database, get_opensearch_client


def setup_environment(**_):
    """Verify Postgres and OpenSearch, create the tables, the chunk index and the RRF pipeline if missing."""
    database = get_database()
    if not database.health_check():
        raise RuntimeError("Postgres is not reachable")
    opensearch_client = get_opensearch_client()
    if not opensearch_client.health_check():
        raise RuntimeError("OpenSearch is not reachable")
    created = opensearch_client.setup_indices(force=False)
    return {"database": "ok", "opensearch": "ok", "created": created}
