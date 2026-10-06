import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.db.interfaces.base import BaseDatabase
from src.exceptions import DatabaseError

logger = logging.getLogger(__name__)

# Declarative base written in the 1.4-compatible style: the Airflow image runs SQLAlchemy < 2.
Base = declarative_base()

# Arbitrary constant; serialises create_all across the Uvicorn workers that start together.
_SCHEMA_LOCK_ID = 7_041_905


class PostgreSQLDatabase(BaseDatabase):
    def __init__(self, database_url: str, pool_size: int = 20):
        self.database_url = database_url
        self.pool_size = pool_size
        self.engine = None
        self.session_factory = None

    def startup(self) -> None:
        try:
            self.engine = create_engine(self.database_url, pool_size=self.pool_size, max_overflow=0, pool_pre_ping=True)
            self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
            import src.models.document  # noqa: F401  registers the table on Base

            with self.engine.begin() as conn:
                conn.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": _SCHEMA_LOCK_ID})
                Base.metadata.create_all(bind=conn)
        except Exception as e:
            raise DatabaseError(f"Database startup failed: {e}") from e

    def teardown(self) -> None:
        if self.engine is not None:
            self.engine.dispose()

    @contextmanager
    def get_session(self) -> Iterator[Session]:
        if self.session_factory is None:
            raise DatabaseError("Database not started")
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def health_check(self) -> bool:
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.warning("Database health check failed: %s", e)
            return False
