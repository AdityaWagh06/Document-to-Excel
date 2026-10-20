import json
import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from backend.app.db.connection import get_db

logger = logging.getLogger(__name__)


class WebhookEventRepository:
    """
    Manages webhook idempotency and audit events in SQLite.
    Provides atomic, durable deduplication across multiple workers and restarts.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def record_event(
        self,
        message_id: str,
        sender: Optional[str] = None,
        event_type: str = "whatsapp_message",
        payload: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> bool:
        """
        Atomically records a webhook message ID.
        Returns True if the message was successfully registered.
        Returns False if the message_id is a duplicate (unique constraint violation).
        """
        if not message_id or not str(message_id).strip():
            return True  # If no identifier can be extracted, do not block processing

        clean_id = str(message_id).strip()
        created_at = datetime.utcnow().isoformat()
        payload_str = json.dumps(payload, ensure_ascii=False) if payload else "{}"

        try:
            with get_db(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO webhook_events (message_id, sender, event_type, status, payload, created_at)
                    VALUES (?, ?, ?, 'processed', ?, ?)
                    """,
                    (clean_id, sender or kwargs.get("source") or "", event_type, payload_str, created_at)
                )
            logger.info("Recorded webhook event message_id '%s' into audit log.", clean_id)
            return True

        except sqlite3.IntegrityError:
            logger.warning("Duplicate webhook event '%s' rejected by unique constraint.", clean_id)
            return False
        except Exception as exc:
            logger.error("Database error while recording webhook event '%s': %s", clean_id, exc)
            # Fail closed or handle gracefully; re-raise to protect against silent bypass
            raise

    def is_event_processed(self, message_id: str) -> bool:
        if not message_id:
            return False

        try:
            with get_db(self.db_path) as conn:
                cur = conn.execute(
                    "SELECT 1 FROM webhook_events WHERE message_id = ? LIMIT 1",
                    (str(message_id).strip(),)
                )
                return cur.fetchone() is not None
        except Exception as exc:
            logger.error("Failed to query webhook event status: %s", exc)
            return False


webhook_event_repo = WebhookEventRepository()
