"""Database connection architecture (SQLAlchemy engine + session factory).

Step 1 scope: connection management only. No ORM models or schema are
created yet — later steps will add them. Connections are opened lazily,
so the API starts fine without a running PostgreSQL server.
"""

import logging
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# Bound connection attempts so a stalled/unreachable PostgreSQL can never
# hang a request (e.g. something non-PG squatting on the port).
DB_CONNECT_TIMEOUT_SECONDS = 3
DB_PROBE_WALL_CLOCK_SECONDS = 5

# pool_pre_ping avoids stale connections after PostgreSQL restarts;
# no connection is actually opened until a session is used.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": DB_CONNECT_TIMEOUT_SECONDS},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session (always closed after use)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """Cheap connectivity probe used by the health endpoint. Never raises,
    never blocks longer than DB_PROBE_WALL_CLOCK_SECONDS."""
    def _probe() -> bool:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        return True

    executor = ThreadPoolExecutor(max_workers=1)
    try:
        return bool(executor.submit(_probe).result(timeout=DB_PROBE_WALL_CLOCK_SECONDS))
    except FutureTimeoutError:
        logger.warning("Database probe timed out after %ss", DB_PROBE_WALL_CLOCK_SECONDS)
        return False
    except Exception:  # noqa: BLE001 — health check must not crash the request
        logger.warning("Database connectivity check failed", exc_info=True)
        return False
    finally:
        # Never block the caller on a stuck connection thread.
        executor.shutdown(wait=False)
