import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# GSTIN Regex Pattern for India (15 characters)
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$", re.IGNORECASE)

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

        # 1. Missing Fields Check
        if not vendor:
            warnings.append({
                "code": "MISSING_VENDOR",
                "type": "error",
                "field": "vendor",
                "message": "Vendor name is missing or could not be detected."
            })
        if not invoice_number:
            warnings.append({
                "code": "MISSING_INVOICE_NO",
                "type": "warning",
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
        else:
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

            if subtotal_val > 0 and tax_total_val > 0 and total_val > 0:
                calc_total = subtotal_val + tax_total_val
                if abs(calc_total - total_val) > 1.0:  # allow rounding margin of 1.0
                    warnings.append({
                        "code": "TAX_MISMATCH",
                        "type": "warning",
                        "field": "tax_total",
                        "message": f"Tax mismatch: Subtotal ({subtotal_val:.2f}) + Tax ({tax_total_val:.2f}) = {calc_total:.2f}, but Total is {total_val:.2f}."
                    })
        except Exception:
            pass

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
                if abs(items_sum - total_val) > 2.0 and abs(items_sum - (subtotal_val or total_val)) > 2.0:
                    warnings.append({
                        "code": "ITEM_SUM_MISMATCH",
                        "type": "info",
                        "field": "items",
                        "message": f"Sum of line items ({items_sum:.2f}) differs from stated document total ({total_val:.2f})."
                    })

        return warnings
