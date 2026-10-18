import re

# Regex matching patterns for document parsing

GSTIN_PATTERNS = (
    r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b",
    r"(?:GSTIN|GST|GST\s*NO|GST\s*NUMBER|GSTIN/UIN)\s*[:\-]?\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
)

INVOICE_NO_PATTERNS = (
    r"(?:Invoice\s*No|Invoice\s*#|Inv\s*#|Inv\s*No|Bill\s*No|Bill\s*#|Voucher\s*No)\s*[:\-]?\s*([A-Za-z0-9/\-_]{3,25})",
    r"\bINV[-/][0-9A-Za-z\-_]{3,20}\b",
    r"\b[0-9]{3,8}/[2-9][0-9]-[2-9][0-9]\b",
)

DATE_PATTERNS = (
    r"(?:Date|Invoice\s*Date|Bill\s*Date)\s*[:\-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
    r"(?:Date|Invoice\s*Date|Bill\s*Date)\s*[:\-]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
    r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2})\b",
    r"\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b",
    r"\b(?:\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})\b",
)

DUE_DATE_PATTERNS = (
    r"(?:Due\s*Date|Pay\s*By)\s*[:\-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
    r"(?:Due\s*Date|Pay\s*By)\s*[:\-]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
)

SUBTOTAL_PATTERNS = (
    r"(?:Sub\s*Total|Subtotal|Net\s*Amount|Taxable\s*Value)\s*[:\-]?\s*[₹S\$€£]?\s*([0-9,]+(?:\.[0-9]{2})?)",
)

CGST_PATTERNS = (
    r"(?:CGST|Central\s*GST)\s*(?:\(\s*\d+\.?\d*%\s*\))?\s*[:\-]?\s*[₹S\$€£]?\s*([0-9,]+(?:\.[0-9]{2})?)",
)

SGST_PATTERNS = (
    r"(?:SGST|State\s*GST)\s*(?:\(\s*\d+\.?\d*%\s*\))?\s*[:\-]?\s*[₹S\$€£]?\s*([0-9,]+(?:\.[0-9]{2})?)",
)

IGST_PATTERNS = (
    r"(?:IGST|Integrated\s*GST)\s*(?:\(\s*\d+\.?\d*%\s*\))?\s*[:\-]?\s*[₹S\$€£]?\s*([0-9,]+(?:\.[0-9]{2})?)",
)

TOTAL_PATTERNS = (
    r"\b(?:grand\s+total|total\s+due|total\s+amount|net\s+payable|total)\b.*?[₹S\$€£]?\s*([0-9,]+(?:\.[0-9]{2})?)",
    r"[₹S\$€£]\s*([0-9,]+(?:\.[0-9]{2})?)",
)

HSN_SAC_PATTERN = re.compile(r"\b\d{4,8}\b")
ITEM_PATTERN = re.compile(r"(?m)^\s*(.+?)\s+([0-9]+(?:[.,][0-9]{2})?)\s*$")
AMOUNT_RE = re.compile(r"([₹€$£]?\s*\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))")

# Scoring constants
BASE_CONFIDENCE = 0.40
SCORE_COMPONENT_WEIGHT = 0.10
MAX_CONFIDENCE_CAP = 0.98
