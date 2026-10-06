"""Service bundle for DAG tasks. /opt/airflow is on sys.path so tasks import the application's src package."""

import sys
from functools import lru_cache

if "/opt/airflow" not in sys.path:
    sys.path.insert(0, "/opt/airflow")


@lru_cache(maxsize=1)
def get_database():
    from src.db.factory import make_database

    return make_database(pool_size=2)


def get_opensearch_client():
    from src.services.opensearch.factory import make_opensearch_client

    return make_opensearch_client()
