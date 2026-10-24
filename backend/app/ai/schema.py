"""
Typed schema for LLM invoice extraction.

The same schema is used to (1) request OpenAI Structured Outputs and
(2) validate whatever any provider returns before it reaches the database.
"""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _to_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


class InvoiceLineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str = ""
    hsn_sac: str = ""
    qty: str = ""
    unit_price: str = ""
    tax_rate: str = ""
    tax_amount: str = ""
    amount: str = ""

    @field_validator("*", mode="before")
    @classmethod
    def _coerce(cls, value):
        return _to_str(value)


class InvoiceExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    vendor: str = ""
    gstin: str = ""
    invoice_number: str = ""
    date: str = ""
    due_date: str = ""
    subtotal: str = ""
    cgst: str = ""
    sgst: str = ""
    igst: str = ""
    tax_total: str = ""
    discount: str = ""
    other_charges: str = ""
    total: str = ""
    currency: str = ""
    items: List[InvoiceLineItem] = Field(default_factory=list)

    @field_validator(
        "vendor", "gstin", "invoice_number", "date", "due_date", "subtotal",
        "cgst", "sgst", "igst", "tax_total", "discount", "other_charges", "total", "currency",
        mode="before",
    )
    @classmethod
    def _coerce(cls, value):
        return _to_str(value)

    @field_validator("items", mode="before")
    @classmethod
    def _coerce_items(cls, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("items must be a list")
        # Tolerate bare strings from weaker models without inventing amounts
        return [v if isinstance(v, dict) else {"description": _to_str(v)} for v in value]


_STRING = {"type": "string"}
_ITEM_FIELDS = ["description", "hsn_sac", "qty", "unit_price", "tax_rate", "tax_amount", "amount"]
_DOC_FIELDS = [
    "vendor", "gstin", "invoice_number", "date", "due_date", "subtotal",
    "cgst", "sgst", "igst", "tax_total", "discount", "other_charges", "total", "currency",
]

# JSON Schema for OpenAI Structured Outputs (strict mode requires every
# property to be listed in "required" and additionalProperties=false).
INVOICE_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        **{name: _STRING for name in _DOC_FIELDS},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {name: _STRING for name in _ITEM_FIELDS},
                "required": _ITEM_FIELDS,
            },
        },
    },
    "required": _DOC_FIELDS + ["items"],
}

SYSTEM_PROMPT = (
    "You are an accounts-payable assistant that extracts data from invoices, bills and receipts "
    "from any country (many are Indian GST invoices). Return ONLY data that is printed on the document.\n"
    "Rules:\n"
    "- Never guess or invent values. If a field is not present, return an empty string.\n"
    "- Amounts: plain decimal numbers exactly as printed, without currency symbols or thousands "
    "separators, e.g. 11800.00. Never convert between currencies.\n"
    "- currency: the ISO 4217 code of the currency the amounts are printed in, judged from symbols, "
    "codes and the country of the address: $ in the USA -> USD, CA$ -> CAD, A$ -> AUD, "
    "₹ / Rs / INR / GSTIN present -> INR, € -> EUR, £ -> GBP, AED -> AED. Empty only if there is no clue.\n"
    "- Dates: ISO format YYYY-MM-DD when the date is unambiguous; otherwise copy it as printed.\n"
    "- gstin: the SUPPLIER's 15-character Indian GSTIN (not the buyer's), uppercase; empty for non-Indian bills.\n"
    "- vendor: the supplier / seller / shop / restaurant name, not the buyer.\n"
    "- invoice_number: invoice, bill, receipt, order or check number if printed.\n"
    "- subtotal: amount before tax. cgst / sgst / igst: Indian GST amounts only. tax_total: total of all "
    "taxes (GST, VAT, sales tax). discount: total discount as a positive number. other_charges: tip, "
    "service charge, delivery, shipping, round-off and similar charges added to the bill.\n"
    "- total: the final amount payable as printed (grand total / amount due / total).\n"
    "- tax_rate: percentage such as '18%'. qty and unit_price as printed numbers; if a line shows only "
    "an amount, use qty '1' and leave unit_price empty.\n"
    "- items: one entry per line item; do not include tax, subtotal, discount, tip or total rows.\n"
    "- When page images are provided, the image is the source of truth. The OCR text may contain "
    "misreadings (for example '$' read as '5' or 'S', 'O' read as '0'); correct them from the image."
)


def build_user_prompt(ocr_text: str, max_chars: Optional[int] = None, with_images: bool = False) -> str:
    text = ocr_text or ""
    truncated = False
    if max_chars and len(text) > max_chars:
        text = text[:max_chars]
        truncated = True
    note = "\n[Text truncated to fit the model input limit.]" if truncated else ""
    intro = (
        "Extract the invoice fields from the attached page image(s). The OCR text of the same pages is "
        "included below as a hint only; it may contain errors."
        if with_images else
        "Extract the invoice fields from the OCR text below."
    )
    return (
        intro + " Respond with a JSON object only.\n"
        "Required keys: " + ", ".join(_DOC_FIELDS) + ", items (each item has keys: "
        + ", ".join(_ITEM_FIELDS) + ").\n\n"
        "OCR TEXT START\n" + text + note + "\nOCR TEXT END"
    )
