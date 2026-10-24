import re
import logging
from typing import List, Dict, Any

from backend.app.utils.text_utils import amount_to_float

logger = logging.getLogger(__name__)

# GSTIN Regex Pattern for India (15 characters)
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$", re.IGNORECASE)
GSTIN_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# GST state codes 01-38 plus 97 (Other Territory) and 99 (Centre Jurisdiction)
VALID_GST_STATE_CODES = {f"{i:02d}" for i in range(1, 39)} | {"97", "99"}

LOW_EXTRACTION_CONFIDENCE = 0.6
LOW_OCR_CONFIDENCE = 0.5


def gstin_checksum_valid(gstin: str) -> bool:
    """Validates the 15th (check) character of a GSTIN using the official mod-36 algorithm."""
    gstin = gstin.upper()
    if len(gstin) != 15 or any(c not in GSTIN_CHARSET for c in gstin):
        return False
    total = 0
    for idx, char in enumerate(gstin[:14]):
        product = GSTIN_CHARSET.index(char) * (2 if idx % 2 else 1)
        total += product // 36 + product % 36
    check = GSTIN_CHARSET[(36 - total % 36) % 36]
    return check == gstin[14]


def _amount(value) -> float:
    try:
        return abs(amount_to_float(value))
    except Exception:
        return 0.0

class ValidationEngine:
    @staticmethod
    def validate_document(document_data: Dict[str, Any], existing_documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        warnings: List[Dict[str, Any]] = []

        vendor = str(document_data.get("vendor", "")).strip()
        invoice_number = str(document_data.get("invoice_number", "")).strip()
        date = str(document_data.get("date", "")).strip()
        total_str = str(document_data.get("total", "0")).replace(",", "").strip()
        gstin = str(document_data.get("gstin", "")).strip()
        subtotal_str = str(document_data.get("subtotal", "0")).replace(",", "").strip()
        cgst_str = str(document_data.get("cgst", "0")).replace(",", "").strip()
        sgst_str = str(document_data.get("sgst", "0")).replace(",", "").strip()
        igst_str = str(document_data.get("igst", "0")).replace(",", "").strip()
        tax_total_str = str(document_data.get("tax_total", "0")).replace(",", "").strip()
        items = document_data.get("items", [])
        current_id = document_data.get("id")
        currency = str(document_data.get("currency") or "").strip().upper()
        discount_val = _amount(document_data.get("discount"))
        other_charges_val = _amount(document_data.get("other_charges"))

        # 1. Missing Fields Check
        if not vendor:
            warnings.append({
                "code": "MISSING_VENDOR",
                "type": "error",
                "field": "vendor",
                "message": "Vendor name is missing or could not be detected."
            })
        if not invoice_number:
            # Shop receipts often have no bill number; Indian GST invoices must have one
            warnings.append({
                "code": "MISSING_INVOICE_NO",
                "type": "warning" if currency in ("", "INR") else "info",
                "field": "invoice_number",
                "message": "Invoice/Bill number is missing."
            })
        if not date:
            warnings.append({
                "code": "MISSING_DATE",
                "type": "warning",
                "field": "date",
                "message": "Invoice date is missing."
            })

        try:
            total_val = float(re.sub(r"[^\d.]", "", total_str)) if total_str else 0.0
        except ValueError:
            total_val = 0.0

        if total_val <= 0:
            warnings.append({
                "code": "MISSING_TOTAL",
                "type": "error",
                "field": "total",
                "message": "Invoice total amount is 0 or unreadable."
            })

        # 2. GST Format Validation
        if gstin:
            clean_gstin = gstin.upper().replace(" ", "")
            if not GSTIN_REGEX.match(clean_gstin):
                warnings.append({
                    "code": "INVALID_GST_FORMAT",
                    "type": "warning",
                    "field": "gstin",
                    "message": f"GSTIN '{gstin}' does not match standard 15-character GSTIN format."
                })
            elif clean_gstin[:2] not in VALID_GST_STATE_CODES:
                warnings.append({
                    "code": "INVALID_GST_STATE_CODE",
                    "type": "warning",
                    "field": "gstin",
                    "message": f"GSTIN '{gstin}' starts with '{clean_gstin[:2]}', which is not a valid GST state code."
                })
            elif not gstin_checksum_valid(clean_gstin):
                warnings.append({
                    "code": "INVALID_GST_CHECKSUM",
                    "type": "warning",
                    "field": "gstin",
                    "message": f"GSTIN '{gstin}' fails the check-digit validation; it may have been misread. Please verify."
                })
        elif currency in ("", "INR"):
            warnings.append({
                "code": "MISSING_GSTIN",
                "type": "info",
                "field": "gstin",
                "message": "GST Number is absent on this invoice."
            })

        # 3. Duplicate Invoice Check
        if invoice_number and vendor:
            for doc in existing_documents:
                if doc.get("id") != current_id:
                    other_inv = str(doc.get("invoice_number", "")).strip()
                    other_vendor = str(doc.get("vendor", "")).strip()
                    if other_inv and other_vendor:
                        if other_inv.lower() == invoice_number.lower() and other_vendor.lower() == vendor.lower():
                            warnings.append({
                                "code": "DUPLICATE_INVOICE",
                                "type": "error",
                                "field": "invoice_number",
                                "message": f"Duplicate invoice detected! Invoice #{invoice_number} from '{vendor}' already exists."
                            })
                            break

        # 4. Tax Mismatch & Math Checks
        try:
            subtotal_val = float(re.sub(r"[^\d.]", "", subtotal_str)) if subtotal_str else 0.0
            cgst_val = float(re.sub(r"[^\d.]", "", cgst_str)) if cgst_str else 0.0
            sgst_val = float(re.sub(r"[^\d.]", "", sgst_str)) if sgst_str else 0.0
            igst_val = float(re.sub(r"[^\d.]", "", igst_str)) if igst_str else 0.0
            tax_total_val = float(re.sub(r"[^\d.]", "", tax_total_str)) if tax_total_str else (cgst_val + sgst_val + igst_val)

            if subtotal_val > 0 and total_val > 0 and (tax_total_val > 0 or discount_val > 0 or other_charges_val > 0):
                calc_total = subtotal_val + tax_total_val + other_charges_val - discount_val
                if abs(calc_total - total_val) > 1.0:  # allow rounding margin of 1.0
                    parts = f"Subtotal ({subtotal_val:.2f}) + Tax ({tax_total_val:.2f})"
                    if other_charges_val:
                        parts += f" + Other charges ({other_charges_val:.2f})"
                    if discount_val:
                        parts += f" - Discount ({discount_val:.2f})"
                    warnings.append({
                        "code": "TAX_MISMATCH",
                        "type": "warning",
                        "field": "tax_total",
                        "message": f"Totals do not add up: {parts} = {calc_total:.2f}, but Total is {total_val:.2f}."
                    })
        except Exception:
            pass

        # 4b. Indian GST structure rules
        cgst_amt, sgst_amt, igst_amt = _amount(cgst_str), _amount(sgst_str), _amount(igst_str)
        if igst_amt > 0 and (cgst_amt > 0 or sgst_amt > 0):
            warnings.append({
                "code": "GST_TYPE_CONFLICT",
                "type": "warning",
                "field": "igst",
                "message": "Invoice has both IGST and CGST/SGST. Inter-state supplies use IGST only; intra-state supplies use CGST + SGST."
            })
        if (cgst_amt > 0 or sgst_amt > 0) and abs(cgst_amt - sgst_amt) > 1.0:
            warnings.append({
                "code": "CGST_SGST_MISMATCH",
                "type": "warning",
                "field": "cgst",
                "message": f"CGST ({cgst_amt:.2f}) and SGST ({sgst_amt:.2f}) should normally be equal for intra-state supplies."
            })

        # 5. Line Item Calculation Errors Check
        if items:
            items_sum = 0.0
            for idx, item in enumerate(items):
                try:
                    qty = float(item.get("qty", 1) or 1)
                    unit_price = float(re.sub(r"[^\d.]", "", str(item.get("unit_price", 0))) or 0)
                    amount = float(re.sub(r"[^\d.]", "", str(item.get("amount", 0))) or 0)

                    items_sum += amount
                    if qty > 0 and unit_price > 0 and amount > 0:
                        calc_amt = qty * unit_price
                        if abs(calc_amt - amount) > 0.5:
                            warnings.append({
                                "code": "CALCULATION_ERROR",
                                "type": "warning",
                                "field": f"items[{idx}]",
                                "message": f"Item '{item.get('description', '')}' calculation error: Qty ({qty}) * Rate ({unit_price:.2f}) = {calc_amt:.2f}, but Amount is {amount:.2f}."
                            })
                except Exception:
                    continue

            if items_sum > 0 and total_val > 0:
                gap = min(abs(items_sum - total_val), abs(items_sum - (subtotal_val or total_val)))
                if gap > 2.0:
                    # A large gap usually means a misread total (e.g. "$25.97" read as "525.97")
                    big_gap = gap > 0.05 * max(items_sum, total_val)
                    warnings.append({
                        "code": "ITEM_SUM_MISMATCH",
                        "type": "warning" if big_gap else "info",
                        "field": "items",
                        "message": f"Sum of line items ({items_sum:.2f}) differs from stated document total ({total_val:.2f})."
                    })

        # 5b. Currency
        if not currency:
            warnings.append({
                "code": "MISSING_CURRENCY",
                "type": "info",
                "field": "currency",
                "message": "Currency could not be detected. Set it (e.g. INR, USD) so amounts are shown correctly."
            })

        # 6. Extraction quality: low confidence and AI review notes
        try:
            confidence = float(document_data.get("confidence") or 0)
            ocr_confidence = float(document_data.get("ocr_confidence") or 0)
        except (TypeError, ValueError):
            confidence, ocr_confidence = 0.0, 0.0
        if 0 < confidence < LOW_EXTRACTION_CONFIDENCE:
            warnings.append({
                "code": "LOW_CONFIDENCE",
                "type": "warning",
                "field": "confidence",
                "message": f"Extraction confidence is low ({confidence:.0%}). Review every field before exporting."
            })
        if 0 < ocr_confidence < LOW_OCR_CONFIDENCE:
            warnings.append({
                "code": "LOW_OCR_QUALITY",
                "type": "warning",
                "field": "ocr_confidence",
                "message": f"OCR quality is low ({ocr_confidence:.0%}). A sharper scan or photo will improve accuracy."
            })
        for note in document_data.get("extraction_notes") or []:
            warnings.append({
                "code": "EXTRACTION_NOTE",
                "type": "info",
                "field": "extraction",
                "message": str(note)[:300]
            })

        return warnings
