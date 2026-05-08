import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Iterable

import requests
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class ParsedItem(BaseModel):
    description: str = ""
    amount: str = ""


class ParsedDocument(BaseModel):
    vendor: str = ""
    date: str = ""
    total: str = ""
    items: list[ParsedItem] = Field(default_factory=list)
    confidence: float = 0.0
    raw_text: str = ""


DATE_PATTERNS = (
    r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2})\b",
    r"\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b",
    r"\b(?:\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})\b",
)

TOTAL_PATTERNS = (
    r"(?:grand\s+total|total|amount\s+due|balance\s+due)\s*[:\-]?\s*[$€£]?\s*([0-9]+(?:[.,][0-9]{2})?)",
    r"[$€£]\s*([0-9]+(?:[.,][0-9]{2})?)",
)

ITEM_PATTERN = re.compile(r"(?m)^\s*(.+?)\s+([0-9]+(?:[.,][0-9]{2})?)\s*$")


def _first_match(patterns: Iterable[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1) if match.groups() else match.group(0)
    return ""


def _extract_vendor(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    for line in lines[:5]:
        if len(line) >= 3 and not re.search(r"\b(invoice|receipt|date|total|tax)\b", line, re.IGNORECASE):
            return line
    return lines[0]


def _extract_items(text: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for match in ITEM_PATTERN.finditer(text):
        description = match.group(1).strip()
        amount = match.group(2).strip()
        if description and amount:
            items.append({"description": description, "amount": amount})
    return items[:20]


def regex_parse(text: str) -> ParsedDocument:
    vendor = _extract_vendor(text)
    date = _first_match(DATE_PATTERNS, text)
    total = _first_match(TOTAL_PATTERNS, text)
    items = [ParsedItem(**item) for item in _extract_items(text)]

    confidence = 0.35
    score_components = [bool(vendor), bool(date), bool(total), bool(items)]
    confidence += 0.15 * sum(score_components)

    return ParsedDocument(
        vendor=vendor,
        date=_normalize_date(date),
        total=_normalize_amount(total),
        items=items,
        confidence=min(confidence, 0.95),
        raw_text=text,
    )


def _normalize_amount(value: str) -> str:
    return value.replace(",", ".").strip()


def _normalize_date(value: str) -> str:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value


def _build_prompt(text: str) -> str:
    return (
        "You extract structured invoice or receipt data. Return ONLY valid JSON with this exact schema:\n"
        '{"vendor":"","date":"","total":"","items":[]}\n'
        "Rules:\n"
        "- Output must be raw JSON only. No markdown, no code fences, no commentary.\n"
        "- vendor, date, and total must be strings.\n"
        "- items must be an array. Use objects with description and amount when possible.\n"
        "- If data is missing, use empty strings or empty arrays.\n"
        "OCR TEXT:\n"
        f"{text}"
    )


def _call_openrouter(text: str) -> dict[str, Any]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat:free")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "Document to Excel MVP",
        },
        json={
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": "You extract structured JSON from OCR text."},
                {"role": "user", "content": _build_prompt(text)},
            ],
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    return json.loads(_strip_code_fences(content))


def _strip_code_fences(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped


def _validate_ai_payload(payload: dict[str, Any]) -> ParsedDocument:
    try:
        items = payload.get("items") or []
        normalized_items = []
        for item in items:
            if isinstance(item, dict):
                normalized_items.append(
                    ParsedItem(
                        description=str(item.get("description", "")),
                        amount=str(item.get("amount", "")),
                    )
                )
            else:
                normalized_items.append(ParsedItem(description=str(item), amount=""))

        return ParsedDocument(
            vendor=str(payload.get("vendor", "")),
            date=_normalize_date(str(payload.get("date", ""))),
            total=_normalize_amount(str(payload.get("total", ""))),
            items=normalized_items,
            confidence=0.9,
            raw_text=str(payload.get("raw_text", "")),
        )
    except ValidationError as exc:
        raise ValueError("AI payload validation failed") from exc


def parse_document(text: str, confidence: float) -> ParsedDocument:
    regex_result = regex_parse(text)
    if confidence >= 0.5 and regex_result.vendor and regex_result.date and regex_result.total:
        return regex_result

    last_error: Exception | None = None
    for _ in range(2):
        try:
            payload = _call_openrouter(text)
            return _validate_ai_payload(payload)
        except Exception as exc:
            last_error = exc
            logger.warning("AI parsing attempt failed: %s", exc)
    logger.info("Falling back to regex parse after AI failure")
    if last_error:
        logger.warning("Returning regex parse after error: %s", last_error)
    return regex_result
