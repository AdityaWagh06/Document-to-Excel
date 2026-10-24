import re
from datetime import datetime
from typing import Iterable

def first_match(patterns: Iterable[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1) if match.groups() else match.group(0)
    return ""

def normalize_amount(value: str) -> str:
    """
    Normalizes a printed amount to a plain decimal string without thousands
    separators. Handles Indian (1,18,000.00), international (118,000.00) and
    European (118.000,00 / 1180,00) formats. Returns "" for empty input and
    the stripped input unchanged when it contains no digits.
    """
    if value is None:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    negative = raw.startswith("-") or (raw.startswith("(") and raw.endswith(")"))
    cleaned = re.sub(r"[^0-9.,]", "", raw)
    if not re.search(r"\d", cleaned):
        return raw

    last_dot = cleaned.rfind(".")
    last_comma = cleaned.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        # Whichever separator appears last is the decimal separator
        if last_comma > last_dot:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif last_comma >= 0:
        # Only commas: a single comma followed by exactly 1-2 digits is a decimal comma
        decimals = cleaned[last_comma + 1:]
        if cleaned.count(",") == 1 and 1 <= len(decimals) <= 2:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif cleaned.count(".") > 1:
        # 1.180.000 style thousands separators (or 1.180.000.50)
        head, _, tail = cleaned.rpartition(".")
        if len(tail) == 3:
            cleaned = cleaned.replace(".", "")
        else:
            cleaned = head.replace(".", "") + "." + tail

    cleaned = cleaned.strip(".")
    if not cleaned:
        return raw
    return ("-" if negative else "") + cleaned


def amount_to_float(value) -> float:
    """Parses an amount string (any common format) to float; returns 0.0 if unreadable."""
    try:
        return float(normalize_amount(str(value if value is not None else "")) or 0)
    except ValueError:
        return 0.0

def normalize_date(value: str) -> str:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value

def strip_code_fences(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped
