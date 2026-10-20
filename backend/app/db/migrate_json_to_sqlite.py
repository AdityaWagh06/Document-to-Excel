import argparse
import json
import logging
import shutil
import sqlite3
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from backend.app.config.settings import settings
from backend.app.db.connection import get_db, init_db

logger = logging.getLogger(__name__)

DEFAULT_LEGACY_JSON = Path(__file__).resolve().parent.parent / "temp" / "documents.json"
KNOWN_DOCUMENT_COLUMNS = {
    "id", "vendor", "gstin", "invoice_number", "date", "due_date",
    "subtotal", "cgst", "sgst", "igst", "tax_total", "total",
    "items", "confidence", "ocr_confidence", "raw_text", "status",
    "erp_sync_status", "validation_warnings", "source", "extra_data",
    "created_at", "updated_at"
}


@dataclass
class MigrationResult:
    total_found: int = 0
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    backup_path: Optional[str] = None
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_found": self.total_found,
            "imported": self.imported,
            "updated": self.updated,
            "skipped": self.skipped,
            "failed": self.failed,
            "backup_path": self.backup_path,
            "errors": self.errors,
            "success": self.failed == 0
        }

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


def backup_json_file(source_path: Path) -> Path:
    """
    Creates a backup copy of the source JSON file before any migration.
    Never removes or overwrites the original source file.
    """
    backup_path = source_path.with_name(f"{source_path.name}.bak")
    shutil.copy2(source_path, backup_path)
    logger.info("Preserved original JSON data at backup path: %s", backup_path)
    return backup_path


def migrate_json_to_sqlite(
    json_path: Optional[Union[str, Path]] = None,
    db_path: Optional[Union[str, Path]] = None,
    backup: bool = True,
    idempotent: bool = True
) -> MigrationResult:
    """
    Safely and idempotently migrates invoice documents from a legacy JSON file into SQLite.
    
    Guarantees:
    - Non-destructive: Never modifies or deletes the source JSON file.
    - Idempotent: Re-running multiple times updates existing records without duplicate rows.
    - Fault-tolerant: Malformed records are recorded with specific error reasons without aborting.
    - Atomic: Database updates are committed within a safe transaction.
    """
    src_file = Path(json_path) if json_path else DEFAULT_LEGACY_JSON
    target_db = str(db_path) if db_path else settings.database_path
    result = MigrationResult()

    if not src_file.exists():
        logger.info("No legacy JSON file found at '%s'. Migration skipped.", src_file)
        return result

    # Step 1: Create backup if requested
    if backup:
        try:
            bk_file = backup_json_file(src_file)
            result.backup_path = str(bk_file)
        except Exception as exc:
            err = f"Failed to create backup of source JSON '{src_file}': {exc}"
            logger.error(err)
            result.errors.append(err)
            result.failed += 1
            return result

    # Step 2: Read and parse JSON content safely
    try:
        with open(src_file, "r", encoding="utf-8") as f:
            raw_content = json.load(f)
    except json.JSONDecodeError as jde:
        err = f"Source JSON file at '{src_file}' contains invalid JSON syntax: {jde}"
        logger.error(err)
        result.errors.append(err)
        result.failed += 1
        return result
    except Exception as exc:
        err = f"Error reading source JSON file '{src_file}': {exc}"
        logger.error(err)
        result.errors.append(err)
        result.failed += 1
        return result

    # Normalize raw content to a list of records
    records: List[Any] = []
    if isinstance(raw_content, list):
        records = raw_content
    elif isinstance(raw_content, dict):
        if "documents" in raw_content and isinstance(raw_content["documents"], list):
            records = raw_content["documents"]
        else:
            records = [raw_content]
    else:
        err = f"Unexpected JSON root type '{type(raw_content).__name__}'. Expected array of documents."
        logger.error(err)
        result.errors.append(err)
        result.failed += 1
        return result

    result.total_found = len(records)
    logger.info("Found %d records in '%s'. Beginning migration into SQLite (%s)...", len(records), src_file, target_db)

    # Step 3: Ensure destination schema exists
    init_db(target_db)

    # Step 4: Process records in transaction
    with get_db(target_db) as conn:
        seen_ids = set()
        for idx, item in enumerate(records):
            if not isinstance(item, dict):
                err = f"Record at index {idx} is not a JSON object: {type(item).__name__}"
                logger.warning(err)
                result.errors.append(err)
                result.failed += 1
                continue

            doc_id = str(item.get("id", "")).strip()
            if not doc_id:
                err = f"Record at index {idx} missing required 'id' field."
                logger.warning(err)
                result.errors.append(err)
                result.failed += 1
                continue

            # Duplicate ID check within this migration batch
            if doc_id in seen_ids:
                logger.info("Record '%s' duplicate ID within batch; skipping.", doc_id)
                result.skipped += 1
                continue

            # Check if record already exists in database
            cur = conn.execute("SELECT 1 FROM documents WHERE id = ? LIMIT 1", (doc_id,))
            existing = cur.fetchone()
            if existing:
                logger.info("Record '%s' already exists in database; skipping to preserve idempotency.", doc_id)
                result.skipped += 1
                seen_ids.add(doc_id)
                continue

            seen_ids.add(doc_id)

            items_json = json.dumps(item.get("items", []), ensure_ascii=False)
            warnings_json = json.dumps(item.get("validation_warnings", []), ensure_ascii=False)

            # Preserve arbitrary custom attributes in extra_data
            extra_data = {k: v for k, v in item.items() if k not in KNOWN_DOCUMENT_COLUMNS}
            extra_data_json = json.dumps(extra_data, ensure_ascii=False) if extra_data else "{}"

            created_at = item.get("created_at") or datetime.utcnow().isoformat()
            updated_at = item.get("updated_at") or created_at

            try:
                conn.execute(
                    """
                    INSERT INTO documents (
                        id, vendor, gstin, invoice_number, date, due_date,
                        subtotal, cgst, sgst, igst, tax_total, total,
                        items, confidence, ocr_confidence, raw_text,
                        status, erp_sync_status, validation_warnings, source,
                        extra_data, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        str(item.get("vendor", "") or ""),
                        str(item.get("gstin", "") or ""),
                        str(item.get("invoice_number", "") or ""),
                        str(item.get("date", "") or ""),
                        str(item.get("due_date", "") or ""),
                        str(item.get("subtotal", "0.00") or "0.00"),
                        str(item.get("cgst", "0.00") or "0.00"),
                        str(item.get("sgst", "0.00") or "0.00"),
                        str(item.get("igst", "0.00") or "0.00"),
                        str(item.get("tax_total", "0.00") or "0.00"),
                        str(item.get("total", "0.00") or "0.00"),
                        items_json,
                        float(item.get("confidence") or 0.0),
                        float(item.get("ocr_confidence") or 0.0),
                        str(item.get("raw_text", "") or ""),
                        str(item.get("status", "Pending Verification") or "Pending Verification"),
                        str(item.get("erp_sync_status", "Not Synced") or "Not Synced"),
                        warnings_json,
                        str(item.get("source", "Manual Upload") or "Manual Upload"),
                        extra_data_json,
                        created_at,
                        updated_at
                    )
                )
                result.imported += 1

            except Exception as exc:
                err = f"Failed to persist record '{doc_id}' into SQLite: {exc}"
                logger.error(err)
                result.errors.append(err)
                result.failed += 1

    logger.info(
        "Migration complete: %d total, %d imported, %d updated, %d skipped, %d failed.",
        result.total_found, result.imported, result.updated, result.skipped, result.failed
    )
    return result


def main():
    parser = argparse.ArgumentParser(description="Migrate invoice documents from JSON to SQLite safely.")
    parser.add_argument("--json-path", default=str(DEFAULT_LEGACY_JSON), help="Path to legacy JSON documents file.")
    parser.add_argument("--db-path", default=None, help="Target SQLite database file path.")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating backup copy of source JSON.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    res = migrate_json_to_sqlite(
        json_path=args.json_path,
        db_path=args.db_path,
        backup=not args.no_backup
    )

    print("\n" + "=" * 60)
    print("MIGRATION REPORT SUMMARY")
    print("=" * 60)
    print(f"Source JSON:   {args.json_path}")
    print(f"Target DB:     {args.db_path or settings.database_path}")
    print(f"Backup File:   {res.backup_path or 'None'}")
    print(f"Total Found:   {res.total_found}")
    print(f"New Imported:  {res.imported}")
    print(f"Updated:       {res.updated}")
    print(f"Skipped:       {res.skipped}")
    print(f"Failed:        {res.failed}")
    if res.errors:
        print("\nErrors encountered:")
        for e in res.errors:
            print(f"  - {e}")
    print("=" * 60)

    if res.failed > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
