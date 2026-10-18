import os
import json
import logging
from pathlib import Path
from threading import Lock
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent / "temp" / "documents.json"

class DocumentRepository:
    def __init__(self):
        self._lock = Lock()
        self._documents: List[Dict[str, Any]] = []
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        try:
            if DATA_FILE.exists():
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    self._documents = json.load(f)
                logger.info("Loaded %d documents from repository store.", len(self._documents))
        except Exception as exc:
            logger.warning("Could not load document repository from disk: %s", exc)
            self._documents = []

    def _save_to_disk(self) -> None:
        try:
            DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self._documents, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.warning("Could not save document repository to disk: %s", exc)

    def get_latest(self) -> Dict[str, Any]:
        with self._lock:
            if self._documents:
                return dict(self._documents[0])
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
        with self._lock:
            return [dict(d) for d in self._documents]

    def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for d in self._documents:
                if d.get("id") == doc_id:
                    return dict(d)
            return None

    def save(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            doc_id = payload.get("id")
            existing_idx = None
            if doc_id:
                for idx, d in enumerate(self._documents):
                    if d.get("id") == doc_id:
                        existing_idx = idx
                        break

            if existing_idx is not None:
                self._documents[existing_idx].update(payload)
                result = self._documents[existing_idx]
            else:
                self._documents.insert(0, payload)
                result = payload

            self._save_to_disk()
            return dict(result)

    def delete(self, doc_id: str) -> bool:
        with self._lock:
            initial_len = len(self._documents)
            self._documents = [d for d in self._documents if d.get("id") != doc_id]
            if len(self._documents) < initial_len:
                self._save_to_disk()
                return True
            return False

    def get_analytics(self) -> Dict[str, Any]:
        with self._lock:
            total_invoices = len(self._documents)
            total_spend = 0.0
            total_tax = 0.0
            pending_verification = 0
            verified_count = 0
            flagged_errors = 0
            synced_erp = 0

            vendors_map: Dict[str, Dict[str, Any]] = {}

            for doc in self._documents:
                # Sum total spend
                total_str = str(doc.get("total", "0")).replace(",", "")
                try:
                    val = float(total_str) if total_str else 0.0
                    total_spend += val
                except ValueError:
                    val = 0.0

                # Sum tax
                tax_str = str(doc.get("tax_total", "0")).replace(",", "")
                try:
                    total_tax += float(tax_str) if tax_str else 0.0
                except ValueError:
                    pass

                # Status counts
                st = doc.get("status", "Pending Verification")
                if st == "Verified":
                    verified_count += 1
                elif st == "Flagged Error":
                    flagged_errors += 1
                else:
                    pending_verification += 1

                if doc.get("erp_sync_status") == "Synced":
                    synced_erp += 1

                # Vendor Stats
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
