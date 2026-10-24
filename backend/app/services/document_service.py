import base64
import logging
from dataclasses import asdict
from io import BytesIO
from typing import Dict, Any, List, Optional

from PIL import Image

from backend.app.ai import AIProviderError
from backend.app.config.settings import settings
from backend.app.models.document import OCRResult
from backend.app.ocr.ocr_engine import (
    OCREngineUnavailableError,
    _has_usable_text_layer,
    extract_text,
    iter_pdf_pages,
    read_pdf_text_layers,
)
from backend.app.utils.currency import normalize_currency
from backend.app.parsers.document_parser import parse_document, parse_document_from_images
from backend.app.services.validation_service import ValidationEngine
from backend.app.repository.document_repository import document_repo

logger = logging.getLogger(__name__)

VALID_STATUSES = ("Verified", "Pending Verification", "Flagged Error")
VALID_ERP_STATUSES = ("Not Synced", "Synced", "XML Generated", "Failed")


class DocumentProcessingError(Exception):
    """A processing failure with a message that is safe to show to the user."""

    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def _page_images_b64(file_path: str, max_pages: int) -> List[str]:
    """Renders up to max_pages pages (or the image) to base64 PNG for AI vision."""
    images: List[Image.Image] = []
    if file_path.lower().endswith(".pdf"):
        for page_num, img in iter_pdf_pages(file_path, max_pages=None):
            if page_num > max_pages:
                break
            images.append(img)
    else:
        with Image.open(file_path) as img:
            images.append(img.convert("RGB"))

    encoded = []
    for img in images:
        img.thumbnail((2000, 2000))
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        encoded.append(base64.b64encode(buf.getvalue()).decode("ascii"))
    return encoded


def _is_digital_pdf(file_path: str) -> bool:
    """True when every page has an embedded text layer (no OCR involved)."""
    if not file_path.lower().endswith(".pdf"):
        return False
    try:
        layers = read_pdf_text_layers(file_path)
    except Exception:
        return False
    return bool(layers) and all(_has_usable_text_layer(t) for t in layers)


def _images_for_ai(file_path: str) -> Optional[List[str]]:
    """Page images to send with OCR text, or None when text alone is reliable."""
    if not settings.ai_send_images or settings.resolved_ai_provider == "none" or _is_digital_pdf(file_path):
        return None
    try:
        return _page_images_b64(file_path, max(1, settings.ai_vision_max_pages))
    except Exception as exc:
        logger.warning("Could not render page images for AI: %s", exc)
        return None


def _vision_fallback(temp_path: str, reason: str) -> Dict[str, Any]:
    if not settings.ai_vision_fallback:
        raise DocumentProcessingError(f"{reason} AI vision fallback is disabled (AI_VISION_FALLBACK=false).")
    try:
        images = _page_images_b64(temp_path, max(1, settings.ai_vision_max_pages))
        parsed = parse_document_from_images(images)
    except AIProviderError as exc:
        if exc.kind == "config":
            raise DocumentProcessingError(
                f"{reason} Configure OPENAI_API_KEY to let the AI read the image directly, "
                "or install the local OCR engines (backend/requirements-ocr.txt).",
                503,
            )
        raise DocumentProcessingError(f"{reason} AI image extraction also failed: {exc}", 502)
    payload = asdict(parsed)
    payload["raw_text"] = ""
    payload["ocr_confidence"] = 0.0
    return payload


class DocumentService:
    @staticmethod
    def process_document(temp_path: str, filename: str = "", source: str = "Manual Upload") -> Dict[str, Any]:
        # Step 1: Read text (PDF text layer or OCR); fall back to AI vision if no OCR engine/text
        try:
            ocr_result: Optional[OCRResult] = extract_text(temp_path)
        except OCREngineUnavailableError as exc:
            logger.warning("OCR unavailable for '%s': %s", filename, exc)
            document_payload = _vision_fallback(temp_path, "No OCR engine is installed on the server.")
            ocr_result = None
        else:
            if not ocr_result.text.strip():
                logger.info("OCR returned no text for '%s'; trying AI vision fallback.", filename)
                try:
                    document_payload = _vision_fallback(temp_path, "No readable text was found in the document.")
                except DocumentProcessingError as exc:
                    if exc.status_code == 503:
                        raise DocumentProcessingError(
                            "No readable text was found in the document. Upload a clearer, well-lit image or a "
                            "higher resolution scan. (Setting OPENAI_API_KEY enables AI image reading as a fallback.)"
                        )
                    raise
            else:
                # Step 2: Parse raw text to structured format
                parsed_document = parse_document(
                    ocr_result.text, ocr_result.confidence, images_b64_png=_images_for_ai(temp_path)
                )
                document_payload = asdict(parsed_document)
                document_payload["raw_text"] = ocr_result.text
                document_payload["ocr_confidence"] = ocr_result.confidence

        document_payload["source"] = source or "Manual Upload"
        if filename:
            document_payload["original_filename"] = filename

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
            "subtotal", "cgst", "sgst", "igst", "tax_total", "discount", "other_charges", "total",
            "currency", "erp_sync_status", "raw_text"
        )
        if "erp_sync_status" in sanitized_updates and sanitized_updates["erp_sync_status"] not in VALID_ERP_STATUSES:
            raise ValueError(f"erp_sync_status must be one of: {', '.join(VALID_ERP_STATUSES)}.")
        if "status" in sanitized_updates and sanitized_updates["status"] not in VALID_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(VALID_STATUSES)}.")

        for field in string_fields:
            if field in sanitized_updates:
                val = sanitized_updates[field]
                if isinstance(val, (dict, list)):
                    raise ValueError(f"Field '{field}' must be a string or number, not {type(val).__name__}.")
                working_doc[field] = str(val) if val is not None else ""

        if "currency" in sanitized_updates:
            raw_currency = str(sanitized_updates.get("currency") or "").strip()
            code = normalize_currency(raw_currency)
            if raw_currency and not code:
                raise ValueError("currency must be an ISO 4217 code such as INR, USD, EUR or GBP.")
            working_doc["currency"] = code

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
            elif client_status == "Pending Verification":
                working_doc["status"] = "Pending Verification"
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
