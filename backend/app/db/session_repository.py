import logging
from datetime import datetime, timedelta
from typing import Optional

from backend.app.db.connection import get_db

logger = logging.getLogger(__name__)


class SessionRepository:
    """
    Manages server-side session revocation state in SQLite.
    Allows immediate, durable invalidation of sessions upon logout.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def revoke_session(
        self,
        session_id: str,
        user: Optional[str] = None,
        lifetime_hours: int = 24,
        **kwargs
    ) -> bool:
        if not session_id:
            return False

        user_name = user or kwargs.get("user_id") or "anonymous"
        expires_at = (datetime.utcnow() + timedelta(hours=lifetime_hours)).isoformat()
        revoked_at = datetime.utcnow().isoformat()

        try:
            with get_db(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO revoked_sessions (session_id, user, revoked_at, expires_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session_id, user_name, revoked_at, expires_at)
                )
            logger.info("Session '%s' successfully recorded in revocation store.", session_id[:8] + "...")
            return True
        except Exception as exc:
            logger.error("Failed to revoke session '%s': %s", session_id[:8] + "...", exc)
            return False

    def is_session_revoked(self, session_id: str) -> bool:
        if not session_id:
            return False

        try:
            with get_db(self.db_path) as conn:
                cur = conn.execute(
                    "SELECT 1 FROM revoked_sessions WHERE session_id = ? LIMIT 1",
                    (session_id,)
                )
                return cur.fetchone() is not None
        except Exception as exc:
            logger.error("Failed to check revocation status for session: %s", exc)
            return False

    def cleanup_expired_sessions(self) -> int:
        now_iso = datetime.utcnow().isoformat()
        try:
            with get_db(self.db_path) as conn:
                cur = conn.execute(
                    "DELETE FROM revoked_sessions WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (now_iso,)
                )
                deleted_count = cur.rowcount
            if deleted_count > 0:
                logger.info("Cleaned up %d expired revoked session records.", deleted_count)
            return deleted_count
        except Exception as exc:
            logger.error("Failed to clean up expired sessions: %s", exc)
            return 0


session_repo = SessionRepository()
