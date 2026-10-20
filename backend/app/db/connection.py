import os
import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Generator
from flask import has_request_context, g

from backend.app.config.settings import settings

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_db_path(db_path: Optional[str] = None) -> str:
    if db_path:
        return db_path
    return settings.database_path


def create_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Creates and configures a new SQLite connection with WAL mode and row factory.
    """
    target_path = get_db_path(db_path)

    # Ensure parent directory exists for file-based databases
    if target_path != ":memory:":
        parent_dir = Path(target_path).parent
        parent_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        target_path,
        timeout=10.0,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row

    # Performance, integrity, and concurrency pragmas
    conn.execute("PRAGMA foreign_keys = ON;")
    if target_path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA synchronous = NORMAL;")

    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """
    Applies the base schema definitions idempotently.
    Safe to run repeatedly on startup or during tests.
    """
    target_path = get_db_path(db_path)
    if not SCHEMA_PATH.exists():
        logger.error("Database schema file not found at %s", SCHEMA_PATH)
        raise FileNotFoundError(f"Schema file missing: {SCHEMA_PATH}")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = create_connection(target_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
        logger.info("SQLite database schema verified/initialized at %s", target_path)
    except Exception as exc:
        conn.rollback()
        logger.exception("Failed to initialize database schema: %s", exc)
        raise
    finally:
        conn.close()


@contextmanager
def get_db(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager yielding a transactional SQLite connection.
    Automatically commits on normal exit and rolls back on unhandled exceptions.
    """
    conn = create_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_flask_db() -> sqlite3.Connection:
    """
    Retrieves or establishes a request-scoped database connection inside Flask request context.
    """
    if has_request_context():
        if not hasattr(g, "_database") or g._database is None:
            g._database = create_connection()
        return g._database
    return create_connection()


def close_flask_db(e=None) -> None:
    """
    Closes the request-scoped database connection at the end of the Flask request lifecycle.
    """
    if has_request_context():
        db = getattr(g, "_database", None)
        if db is not None:
            try:
                db.close()
            except Exception as exc:
                logger.warning("Error closing Flask database connection: %s", exc)
            g._database = None
