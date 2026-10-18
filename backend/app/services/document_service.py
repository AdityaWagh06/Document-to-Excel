from dataclasses import asdict
from typing import Dict, Any, List, Optional

from backend.app.ocr.ocr_engine import extract_text
from backend.app.parsers.document_parser import parse_document
from backend.app.services.validation_service import ValidationEngine
from backend.app.repository.document_repository import document_repo

class DocumentService:
    @staticmethod
    def process_document(temp_path: str, filename: str = "") -> Dict[str, Any]:
        # Step 1: Run OCR on the document image/PDF
        ocr_result = extract_text(temp_path)
        
        # Step 2: Parse raw text to structured format
        parsed_document = parse_document(ocr_result.text, ocr_result.confidence)
        document_payload = asdict(parsed_document)
        document_payload["raw_text"] = ocr_result.text
        document_payload["ocr_confidence"] = ocr_result.confidence

        # Step 3: Run Validation Engine on extracted fields
        existing_docs = document_repo.get_all()
        warnings = ValidationEngine.validate_document(document_payload, existing_docs)
        document_payload["validation_warnings"] = warnings

        # Determine initial verification status
        has_errors = any(w.get("type") == "error" for w in warnings)
        if has_errors:
            document_payload["status"] = "Flagged Error"
        else:
            document_payload["status"] = "Pending Verification"

        # Step 4: Write into repository
        saved_doc = document_repo.save(document_payload)
        return saved_doc

    @staticmethod
    def get_latest_document() -> Dict[str, Any]:
        return document_repo.get_latest()

    @staticmethod
    def get_all_documents() -> List[Dict[str, Any]]:
        return document_repo.get_all()

    @staticmethod
    def get_document_by_id(doc_id: str) -> Optional[Dict[str, Any]]:
        return document_repo.get_by_id(doc_id)

    @staticmethod
    def update_document(doc_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(updates, dict):
            raise ValueError("Payload must be a JSON object.")

        existing = document_repo.get_by_id(doc_id)
        if not existing:
            return None

        # Create working copy to ensure atomicity (no partial modification on failure)
        working_doc = dict(existing)

        # Disallow modification of immutable fields
        sanitized_updates = dict(updates)
        sanitized_updates.pop("id", None)
        sanitized_updates.pop("created_at", None)
        sanitized_updates.pop("validation_warnings", None)  # Client cannot forge warnings

        # Field type validation
        string_fields = (
            "vendor", "gstin", "invoice_number", "date", "due_date",
            "subtotal", "cgst", "sgst", "igst", "tax_total", "total",
            "erp_sync_status", "raw_text"
        )
        for field in string_fields:
            if field in sanitized_updates:
                val = sanitized_updates[field]
                if isinstance(val, (dict, list)):
                    raise ValueError(f"Field '{field}' must be a string or number, not {type(val).__name__}.")
                working_doc[field] = str(val) if val is not None else ""

        # Items validation
        if "items" in sanitized_updates:
            items_val = sanitized_updates["items"]
            if not isinstance(items_val, list):
                raise ValueError("Field 'items' must be a list of item objects.")

            validated_items = []
            for idx, item in enumerate(items_val):
                if not isinstance(item, dict):
                    raise ValueError(f"Item at index {idx} must be a JSON object.")
                validated_items.append({
                    "description": str(item.get("description", "")),
                    "hsn_sac": str(item.get("hsn_sac", "")),
                    "qty": str(item.get("qty", "1")),
                    "unit_price": str(item.get("unit_price", "0.00")),
                    "tax_rate": str(item.get("tax_rate", "0%")),
                    "tax_amount": str(item.get("tax_amount", "0.00")),
                    "amount": str(item.get("amount", "0.00")),
                })
            working_doc["items"] = validated_items

        # Re-run backend validation engine
        all_docs = document_repo.get_all()
        warnings = ValidationEngine.validate_document(working_doc, all_docs)
        working_doc["validation_warnings"] = warnings

        # Recalculate status authoritatively
        has_errors = any(w.get("type") == "error" for w in warnings)
        if has_errors:
            working_doc["status"] = "Flagged Error"
        else:
            client_status = sanitized_updates.get("status")
            if client_status == "Verified":
                working_doc["status"] = "Verified"
            elif working_doc.get("status") == "Flagged Error":
                working_doc["status"] = "Pending Verification"
            elif not working_doc.get("status") or working_doc.get("status") not in ("Verified", "Pending Verification"):
                working_doc["status"] = "Pending Verification"

        return document_repo.save(working_doc)

    @staticmethod
    def delete_document(doc_id: str) -> bool:
        return document_repo.delete(doc_id)

    @staticmethod
    def get_analytics() -> Dict[str, Any]:
        return document_repo.get_analytics()
