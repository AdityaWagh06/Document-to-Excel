"""
Currency detection and normalisation.

Amounts are always stored exactly as printed on the document; this module only
works out *which* currency they are in. Nothing is ever converted.
"""
import re
from collections import Counter

# ISO 4217 codes the app recognises when written on a document
KNOWN_CODES = {
    "INR", "USD", "EUR", "GBP", "AED", "SAR", "QAR", "OMR", "KWD", "BHD", "SGD", "MYR", "THB",
    "IDR", "PHP", "VND", "CNY", "HKD", "JPY", "KRW", "AUD", "NZD", "CAD", "CHF", "SEK", "NOK",
    "DKK", "PLN", "CZK", "HUF", "TRY", "ZAR", "NGN", "KES", "EGP", "BRL", "MXN", "ARS", "CLP",
    "COP", "PKR", "BDT", "LKR", "NPR", "RUB", "ILS",
}

# Symbols / words that identify a currency unambiguously
_MARKERS = (
    (re.compile(r"₹|\bRs\.?(?=\s*\d)|\bINR\b|\bRupees?\b", re.IGNORECASE), "INR"),
    (re.compile(r"\bUS\s?\$|\bUSD\b|\bUS\s+Dollars?\b", re.IGNORECASE), "USD"),
    (re.compile(r"\bC\$|\bCA\$|\bCAD\b"), "CAD"),
    (re.compile(r"\bA\$|\bAU\$|\bAUD\b"), "AUD"),
    (re.compile(r"\bS\$|\bSGD\b"), "SGD"),
    (re.compile(r"\bHK\$|\bHKD\b"), "HKD"),
    (re.compile(r"\bNZ\$|\bNZD\b"), "NZD"),
    (re.compile(r"€|\bEUR\b|\bEuros?\b", re.IGNORECASE), "EUR"),
    (re.compile(r"£|\bGBP\b"), "GBP"),
    (re.compile(r"\bAED\b|\bDirhams?\b|د\.إ", re.IGNORECASE), "AED"),
    (re.compile(r"¥|\bJPY\b|\bCNY\b|\bRMB\b"), "JPY_OR_CNY"),
)
_DOLLAR = re.compile(r"\$\s*\d|\d\s*\$")
_INDIAN_TAX_HINTS = re.compile(r"\bGSTIN\b|\bCGST\b|\bSGST\b|\bIGST\b", re.IGNORECASE)

_SYMBOL_TO_CODE = {"₹": "INR", "RS": "INR", "RS.": "INR", "$": "USD", "US$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}


def normalize_currency(value: str) -> str:
    """Turns '$', 'usd', 'Rs.' or 'INR' into an ISO code; unknown values become ''."""
    raw = (value or "").strip()
    if not raw:
        return ""
    upper = raw.upper()
    if upper in KNOWN_CODES:
        return upper
    if upper in _SYMBOL_TO_CODE:
        return _SYMBOL_TO_CODE[upper]
    match = re.search(r"\b([A-Z]{3})\b", upper)
    if match and match.group(1) in KNOWN_CODES:
        return match.group(1)
    return ""


def detect_currency(text: str, gstin: str = "") -> str:
    """
    Best-effort currency detection from document text. Returns '' when the
    text gives no reliable signal, so the UI shows plain numbers instead of a
    wrong symbol.
    """
    text = text or ""
    votes = Counter()
    for pattern, code in _MARKERS:
        hits = len(pattern.findall(text))
        if hits and code != "JPY_OR_CNY":
            votes[code] += hits
        elif hits:
            votes["CNY" if re.search(r"\bCNY\b|\bRMB\b|元", text) else "JPY"] += hits
    dollar_hits = len(_DOLLAR.findall(text))
    if dollar_hits and not any(c in votes for c in ("USD", "CAD", "AUD", "SGD", "HKD", "NZD")):
        votes["USD"] += dollar_hits
    if votes:
        return votes.most_common(1)[0][0]
    if gstin or _INDIAN_TAX_HINTS.search(text):
        return "INR"
    return ""
