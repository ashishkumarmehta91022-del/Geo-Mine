"""Database layer: engine, session factory, FastAPI dependency, health probe.

Connections open lazily and are time-bounded, so the API never hangs when
PostgreSQL is unavailable. Schema creation happens exclusively through
Alembic migrations (see alembic/versions).
"""

import logging
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# Bound connection attempts so a stalled/unreachable PostgreSQL can never
# hang a request (e.g. firewall silently dropping packets).
DB_CONNECT_TIMEOUT_SECONDS = 3
DB_PROBE_WALL_CLOCK_SECONDS = 5

# pool_pre_ping avoids stale connections after PostgreSQL restarts; no
# connection is opened until a session actually issues a statement.
engine = create_engine(
    settings.effective_database_url,
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


def probe_database() -> tuple[bool, str]:
    """Actual `SELECT 1` round-trip. Returns (connected, detail).

    Never raises and never blocks longer than DB_PROBE_WALL_CLOCK_SECONDS,
    so health checks stay fast even when PostgreSQL is down.
    """

    def _probe() -> None:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    executor = ThreadPoolExecutor(max_workers=1)
    try:
        executor.submit(_probe).result(timeout=DB_PROBE_WALL_CLOCK_SECONDS)
        return True, "connected"
    except FutureTimeoutError:
        logger.warning("Database probe timed out after %ss", DB_PROBE_WALL_CLOCK_SECONDS)
        return False, "timeout"
    except Exception as exc:  # noqa: BLE001 — health check must not crash the request
        logger.warning("Database connectivity check failed: %s", exc.__class__.__name__)
        return False, "unavailable"
    finally:
        # Never block the caller on a stuck connection thread.
        executor.shutdown(wait=False)
