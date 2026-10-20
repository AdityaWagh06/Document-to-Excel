import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Dict, Any, List, Optional

from backend.app.config.settings import settings
from backend.app.db.connection import get_db, init_db

logger = logging.getLogger(__name__)

# Legacy JSON path for migration and backward compatibility
LEGACY_DATA_FILE = Path(__file__).resolve().parent.parent / "temp" / "documents.json"

KNOWN_DOCUMENT_COLUMNS = {
    "id", "vendor", "gstin", "invoice_number", "date", "due_date",
    "subtotal", "cgst", "sgst", "igst", "tax_total", "total",
    "items", "confidence", "ocr_confidence", "raw_text", "status",
    "erp_sync_status", "validation_warnings", "source", "extra_data",
    "created_at", "updated_at"
}


class SyncedList(list):
    """
    A list subclass that transparently synchronizes in-memory mutations
    (such as .append() or .clear()) with the underlying SQLite database.
    Preserves backwards compatibility with legacy test suites.
    """
    def __init__(self, iterable=None, repo=None):
        super().__init__(iterable or [])
        self._repo = repo

    def append(self, item):
        super().append(item)
        if self._repo is not None:
            self._repo.save(item)

    def insert(self, index, item):
        super().insert(index, item)
        if self._repo is not None:
            self._repo.save(item)

    def extend(self, iterable):
        items = list(iterable)
        super().extend(items)
        if self._repo is not None:
            for item in items:
                self._repo.save(item)

    def clear(self):
        super().clear()
        if self._repo is not None:
            self._repo._clear_db()


class DocumentRepository:
    """
    SQLite-backed Document Repository with thread-safe operations,
    atomic transactions, and JSON persistence compatibility.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._lock = RLock()
        self.db_path = db_path
        self._ensure_schema()
        self._auto_migrate_legacy_json_if_needed()

    def _ensure_schema(self) -> None:
        try:
            init_db(self.db_path)
        except Exception as exc:
            logger.warning("Could not auto-initialize database schema: %s", exc)

    def _auto_migrate_legacy_json_if_needed(self) -> None:
        """
        If the SQLite database is currently empty and a legacy documents.json
        file exists, import it automatically on startup.
        """
        try:
            if LEGACY_DATA_FILE.exists():
                with get_db(self.db_path) as conn:
                    cur = conn.execute("SELECT COUNT(*) AS cnt FROM documents")
                    row = cur.fetchone()
                    count = row["cnt"] if row else 0

                if count == 0:
                    from backend.app.db.migrate_json_to_sqlite import migrate_json_to_sqlite
                    logger.info("Empty database detected with existing legacy JSON data. Running migration...")
                    migrate_json_to_sqlite(
                        json_path=LEGACY_DATA_FILE,
                        db_path=self.db_path or settings.database_path,
                        backup=True
                    )
        except Exception as exc:
            logger.warning("Auto-migration of legacy JSON skipped or encountered error: %s", exc)

    # ----------------------------------------------------------------------
    # Backward Compatibility Hooks for Existing Tests
    # ----------------------------------------------------------------------
    @property
    def _documents(self) -> SyncedList:
        """
        Provides backwards compatibility for test fixtures accessing `_documents`.
        Returns a SyncedList reflecting the current contents of the SQLite database.
        """
        with self._lock:
            docs = self._get_all_from_db()
            return SyncedList(docs, repo=self)

    @_documents.setter
    def _documents(self, docs: List[Dict[str, Any]]):
        """
        Allows test fixtures to reassign or clear `_documents` (e.g. `document_repo._documents = []`).
        Clears the database and repopulates it with the supplied documents.
        """
        with self._lock:
            self._clear_db()
            for doc in docs:
                self.save(doc)

    def _save_to_disk(self) -> None:
        """
        Preserved method for existing test mocks that patch `_save_to_disk`.
        """
        pass

    def _load_from_disk(self) -> None:
        """
        Preserved method for existing test mocks.
        """
        pass

    def _clear_db(self) -> None:
        """
        Deletes all documents from the SQLite table.
        """
        try:
            with get_db(self.db_path) as conn:
                conn.execute("DELETE FROM documents")
        except Exception as exc:
            logger.error("Failed to clear documents from database: %s", exc)

    # ----------------------------------------------------------------------
    # Database Row Serialization / Deserialization
    # ----------------------------------------------------------------------
    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        doc = dict(row)

        # Deserialize items
        raw_items = doc.get("items")
        if isinstance(raw_items, str):
            try:
                doc["items"] = json.loads(raw_items)
            except Exception:
                doc["items"] = []
        elif not isinstance(raw_items, list):
            doc["items"] = []

        # Deserialize validation warnings
        raw_warnings = doc.get("validation_warnings")
        if isinstance(raw_warnings, str):
            try:
                doc["validation_warnings"] = json.loads(raw_warnings)
            except Exception:
                doc["validation_warnings"] = []
        elif not isinstance(raw_warnings, list):
            doc["validation_warnings"] = []

        # Unpack extra_data if present
        raw_extra = doc.get("extra_data")
        if isinstance(raw_extra, str) and raw_extra.strip():
            try:
                extra_dict = json.loads(raw_extra)
                if isinstance(extra_dict, dict):
                    for k, v in extra_dict.items():
                        if k not in doc:
                            doc[k] = v
            except Exception:
                pass

        doc.pop("extra_data", None)
        return doc

    def _get_all_from_db(self) -> List[Dict[str, Any]]:
        try:
            with get_db(self.db_path) as conn:
                cur = conn.execute(
                    "SELECT * FROM documents ORDER BY created_at DESC, rowid DESC"
                )
                rows = cur.fetchall()
                return [self._row_to_dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to query documents from database: %s", exc)
            return []

    # ----------------------------------------------------------------------
    # Public Repository API
    # ----------------------------------------------------------------------
    def get_latest(self) -> Dict[str, Any]:
        """
        Returns the most recently created document, or default empty structure if none exist.
        """
        with self._lock:
            try:
                with get_db(self.db_path) as conn:
                    cur = conn.execute(
                        "SELECT * FROM documents ORDER BY created_at DESC, rowid DESC LIMIT 1"
                    )
                    row = cur.fetchone()
                    if row:
                        return self._row_to_dict(row)
            except Exception as exc:
                logger.error("Failed to retrieve latest document: %s", exc)

            return {
                "id": "",
                "vendor": "",
                "gstin": "",
                "invoice_number": "",
                "date": "",
                "due_date": "",
                "subtotal": "0.00",
                "cgst": "0.00",
                "sgst": "0.00",
                "igst": "0.00",
                "tax_total": "0.00",
                "total": "0.00",
                "items": [],
                "confidence": 0.0,
                "ocr_confidence": 0.0,
                "raw_text": "",
                "status": "Pending Verification",
                "erp_sync_status": "Not Synced",
                "validation_warnings": [],
            }

    def get_all(self) -> List[Dict[str, Any]]:
        """
        Returns all stored documents sorted by creation date descending.
        """
        with self._lock:
            return self._get_all_from_db()

    def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a document by its unique identifier.
        """
        if not doc_id:
            return None

        with self._lock:
            try:
                with get_db(self.db_path) as conn:
                    cur = conn.execute(
                        "SELECT * FROM documents WHERE id = ? LIMIT 1",
                        (str(doc_id).strip(),)
                    )
                    row = cur.fetchone()
                    if row:
                        return self._row_to_dict(row)
                    return None
            except Exception as exc:
                logger.error("Failed to retrieve document '%s': %s", doc_id, exc)
                return None

    def save(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inserts or updates a document record atomically in SQLite.
        """
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a dictionary.")

        with self._lock:
            doc_id = payload.get("id")
            if not doc_id or not str(doc_id).strip():
                doc_id = str(uuid.uuid4())
                payload["id"] = doc_id
            else:
                doc_id = str(doc_id).strip()
                payload["id"] = doc_id

            # Check if document already exists to merge fields and preserve created_at
            existing = None
            try:
                with get_db(self.db_path) as conn:
                    cur = conn.execute(
                        "SELECT * FROM documents WHERE id = ? LIMIT 1",
                        (doc_id,)
                    )
                    row = cur.fetchone()
                    if row:
                        existing = self._row_to_dict(row)
            except Exception as exc:
                logger.error("Failed to check existing document: %s", exc)

            merged = dict(existing) if existing else {}
            merged.update(payload)

            now_iso = datetime.utcnow().isoformat()
            if not merged.get("created_at"):
                merged["created_at"] = now_iso
            merged["updated_at"] = now_iso

            # Extract recognized fields
            items_json = json.dumps(merged.get("items", []), ensure_ascii=False)
            warnings_json = json.dumps(merged.get("validation_warnings", []), ensure_ascii=False)

            # Preserve arbitrary custom attributes in extra_data
            extra_data = {k: v for k, v in merged.items() if k not in KNOWN_DOCUMENT_COLUMNS}
            extra_data_json = json.dumps(extra_data, ensure_ascii=False) if extra_data else "{}"

            try:
                with get_db(self.db_path) as conn:
                    conn.execute(
                        """
                        INSERT INTO documents (
                            id, vendor, gstin, invoice_number, date, due_date,
                            subtotal, cgst, sgst, igst, tax_total, total,
                            items, confidence, ocr_confidence, raw_text,
                            status, erp_sync_status, validation_warnings, source,
                            extra_data, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            vendor = excluded.vendor,
                            gstin = excluded.gstin,
                            invoice_number = excluded.invoice_number,
                            date = excluded.date,
                            due_date = excluded.due_date,
                            subtotal = excluded.subtotal,
                            cgst = excluded.cgst,
                            sgst = excluded.sgst,
                            igst = excluded.igst,
                            tax_total = excluded.tax_total,
                            total = excluded.total,
                            items = excluded.items,
                            confidence = excluded.confidence,
                            ocr_confidence = excluded.ocr_confidence,
                            raw_text = excluded.raw_text,
                            status = excluded.status,
                            erp_sync_status = excluded.erp_sync_status,
                            validation_warnings = excluded.validation_warnings,
                            source = excluded.source,
                            extra_data = excluded.extra_data,
                            updated_at = excluded.updated_at
                        """,
                        (
                            doc_id,
                            str(merged.get("vendor", "") or ""),
                            str(merged.get("gstin", "") or ""),
                            str(merged.get("invoice_number", "") or ""),
                            str(merged.get("date", "") or ""),
                            str(merged.get("due_date", "") or ""),
                            str(merged.get("subtotal", "0.00") or "0.00"),
                            str(merged.get("cgst", "0.00") or "0.00"),
                            str(merged.get("sgst", "0.00") or "0.00"),
                            str(merged.get("igst", "0.00") or "0.00"),
                            str(merged.get("tax_total", "0.00") or "0.00"),
                            str(merged.get("total", "0.00") or "0.00"),
                            items_json,
                            float(merged.get("confidence") or 0.0),
                            float(merged.get("ocr_confidence") or 0.0),
                            str(merged.get("raw_text", "") or ""),
                            str(merged.get("status", "Pending Verification") or "Pending Verification"),
                            str(merged.get("erp_sync_status", "Not Synced") or "Not Synced"),
                            warnings_json,
                            str(merged.get("source", "Manual Upload") or "Manual Upload"),
                            extra_data_json,
                            merged["created_at"],
                            merged["updated_at"]
                        )
                    )
                logger.info("Persisted document '%s' to SQLite database.", doc_id)
                return self.get_by_id(doc_id) or merged

            except Exception as exc:
                logger.exception("Failed to save document '%s' to database: %s", doc_id, exc)
                raise

    def update(self, doc_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Updates an existing document with the given partial updates.
        Returns the updated document dictionary or None if not found.
        """
        if not doc_id or not isinstance(updates, dict):
            return None

        with self._lock:
            existing = self.get_by_id(doc_id)
            if not existing:
                return None
            merged = dict(existing)
            merged.update(updates)
            return self.save(merged)

    def delete(self, doc_id: str) -> bool:
        """
        Deletes a document from the SQLite database.
        """
        if not doc_id:
            return False

        with self._lock:
            try:
                with get_db(self.db_path) as conn:
                    cur = conn.execute(
                        "DELETE FROM documents WHERE id = ?",
                        (str(doc_id).strip(),)
                    )
                    deleted = cur.rowcount > 0
                if deleted:
                    logger.info("Deleted document '%s' from SQLite database.", doc_id)
                return deleted
            except Exception as exc:
                logger.error("Failed to delete document '%s': %s", doc_id, exc)
                return False

    def get_analytics(self) -> Dict[str, Any]:
        """
        Aggregates financial and verification metrics across all documents.
        """
        with self._lock:
            docs = self._get_all_from_db()

            total_invoices = len(docs)
            total_spend = 0.0
            total_tax = 0.0
            pending_verification = 0
            verified_count = 0
            flagged_errors = 0
            synced_erp = 0

            vendors_map: Dict[str, Dict[str, Any]] = {}

            for doc in docs:
                total_str = str(doc.get("total", "0")).replace(",", "")
                try:
                    val = float(total_str) if total_str else 0.0
                    total_spend += val
                except ValueError:
                    val = 0.0

                tax_str = str(doc.get("tax_total", "0")).replace(",", "")
                try:
                    total_tax += float(tax_str) if tax_str else 0.0
                except ValueError:
                    pass

                st = doc.get("status", "Pending Verification")
                if st == "Verified":
                    verified_count += 1
                elif st == "Flagged Error":
                    flagged_errors += 1
                else:
                    pending_verification += 1

                if doc.get("erp_sync_status") == "Synced":
                    synced_erp += 1

                vname = str(doc.get("vendor", "Unknown Vendor")).strip() or "Unknown Vendor"
                if vname not in vendors_map:
                    vendors_map[vname] = {"vendor": vname, "count": 0, "total_spend": 0.0}
                vendors_map[vname]["count"] += 1
                vendors_map[vname]["total_spend"] += val

            vendor_list = sorted(list(vendors_map.values()), key=lambda x: x["total_spend"], reverse=True)

            return {
                "total_invoices": total_invoices,
                "total_spend": round(total_spend, 2),
                "total_tax": round(total_tax, 2),
                "pending_verification": pending_verification,
                "verified_count": verified_count,
                "flagged_errors": flagged_errors,
                "synced_erp": synced_erp,
                "vendors_summary": vendor_list[:10],
            }


document_repo = DocumentRepository()
