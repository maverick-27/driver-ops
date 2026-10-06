from src.config import get_settings
from src.db.interfaces.base import BaseDatabase
from src.db.interfaces.postgresql import PostgreSQLDatabase


def make_database(pool_size: int = 20) -> BaseDatabase:
    database = PostgreSQLDatabase(get_settings().postgres_database_url, pool_size=pool_size)
    database.startup()
    return database
