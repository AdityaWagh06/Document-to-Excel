import json
import logging
import re
from typing import Any, List, Dict

import requests

from backend.app.models.document import ParsedItem, ParsedDocument
from backend.app.config.settings import settings
from backend.app.config.ai_constants import AI_TIMEOUT, DEFAULT_AI_CONFIDENCE, build_prompt
from backend.app.config.regex_patterns import (
    GSTIN_PATTERNS,
    INVOICE_NO_PATTERNS,
    DATE_PATTERNS,
    DUE_DATE_PATTERNS,
    SUBTOTAL_PATTERNS,
    CGST_PATTERNS,
    SGST_PATTERNS,
    IGST_PATTERNS,
    TOTAL_PATTERNS,
    HSN_SAC_PATTERN,
    ITEM_PATTERN,
    AMOUNT_RE,
    BASE_CONFIDENCE,
    SCORE_COMPONENT_WEIGHT,
    MAX_CONFIDENCE_CAP,
)
from backend.app.utils.text_utils import (
    first_match,
    normalize_amount,
    normalize_date,
    strip_code_fences,
)

logger = logging.getLogger(__name__)

FREE_MODELS_LIST = [
    "openrouter/auto",
    "inclusionai/ling-3.0-flash:free",
    "google/gemma-4-26b-a4b-it:free",
]

def _extract_vendor(text: str) -> str:
    # Filter out page delimiters and page numbering lines
    lines = [
        line.strip() for line in text.splitlines()
        if line.strip()
        and not re.match(r"^---\s*Page\s*\d+\s*---$", line.strip(), re.IGNORECASE)
        and not re.match(r"^Page\s*\d+(?:\s*(?:of|/)\s*\d+)?$", line.strip(), re.IGNORECASE)
    ]
    if not lines:
        return ""
    for line in lines[:8]:
        v_match = re.search(r"(?:Vendor|Supplier|Company|From)\s*[:\-]?\s*([A-Za-z0-9\s.,&\-]{3,40})", line, re.IGNORECASE)
        if v_match:
            return v_match.group(1).strip()
    for line in lines[:8]:
        if len(line) >= 3 and not re.search(r"\b(invoice|bill|receipt|date|total|subtotal|tax|amount|gstin|gst|phone|email)\b", line, re.IGNORECASE):
            return line
    candidate = lines[0]
    candidate = re.sub(r"^(?:Vendor|Supplier|From|Company)\s*[:\-]?\s*", "", candidate, flags=re.IGNORECASE)
    return candidate.strip()

def _extract_items(text: str) -> List[ParsedItem]:
    items: List[ParsedItem] = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    skip_keywords = r"\b(total|subtotal|tax|cgst|sgst|igst|balance|due|cash|card|change|gstin|invoice|bill|date|thank)\b"
    header_keywords = [
        ("description", "item", "particular", "product"),
        ("qty", "quantity", "nos", "qnty"),
        ("rate", "price", "unit price", "cost"),
        ("amount", "total", "val", "value", "hsn", "sac"),
    ]

    for idx, line in enumerate(lines):
        # 1. Skip page boundaries (e.g. '--- Page 1 ---')
        if re.match(r"^---\s*Page\s*\d+\s*---$", line, re.IGNORECASE):
            continue

        # 2. Skip page numbering (e.g. 'Page 2 of 3', 'Page 1')
        if re.match(r"^Page\s*\d+(?:\s*(?:of|/)\s*\d+)?$", line, re.IGNORECASE):
            continue

        # 3. Skip summary / tax / payment keywords
        if re.search(skip_keywords, line, re.IGNORECASE):
            continue

        # 4. Skip repeated table column headers across pages
        lower_line = line.lower()
        matched_groups = sum(1 for grp in header_keywords if any(w in lower_line for w in grp))
        if matched_groups >= 2:
            continue
        
        matches = list(AMOUNT_RE.finditer(line))
        if matches:
            last_match = matches[-1]
            amount_str = normalize_amount(last_match.group(1).strip())
            desc = (line[: last_match.start()] + line[last_match.end():]).strip()

            if not desc and idx > 0:
                prev = lines[idx - 1]
                if (
                    not re.search(r"\b(items|qty|quantity|price|rate|description)\b", prev, re.IGNORECASE)
                    and not re.match(r"^---\s*Page\s*\d+\s*---$", prev, re.IGNORECASE)
                    and not re.match(r"^Page\s*\d+", prev, re.IGNORECASE)
                ):
                    desc = prev

            desc = re.sub(r"^[\-\u2022\*\s\:\.]+", "", desc).strip()
            desc = re.sub(r"[\-\:\.]+$", "", desc).strip()

            if not desc:
                continue

            # Try to extract Qty and Unit Price from line if numbers exist before total amount
            num_tokens = re.findall(r"\b\d+(?:\.\d+)?\b", desc)
            qty = "1"
            unit_price = amount_str
            hsn = ""

            # Check if there is an HSN/SAC code
            hsn_match = HSN_SAC_PATTERN.search(desc)
            if hsn_match and len(hsn_match.group(0)) in (4, 6, 8):
                hsn = hsn_match.group(0)
                desc = desc.replace(hsn, "").strip()

            if len(num_tokens) >= 2:
                try:
                    candidate_qty = float(num_tokens[0])
                    candidate_rate = float(num_tokens[1])
                    if candidate_qty > 0 and candidate_rate > 0:
                        qty = str(int(candidate_qty) if candidate_qty.is_integer() else candidate_qty)
                        unit_price = f"{candidate_rate:.2f}"
                except ValueError:
                    pass
            elif len(num_tokens) == 1:
                try:
                    candidate_qty = float(num_tokens[0])
                    if 0 < candidate_qty <= 1000:
                        qty = str(int(candidate_qty) if candidate_qty.is_integer() else candidate_qty)
                        if float(qty) > 0:
                            unit_price = f"{(float(re.sub(r'[^0-9.]', '', amount_str) or 0) / float(qty)):.2f}"
                except (ValueError, ZeroDivisionError):
                    pass

            items.append(
                ParsedItem(
                    description=desc,
                    hsn_sac=hsn,
                    qty=qty,
                    unit_price=unit_price,
                    tax_rate="18%" if ("cgst" in text.lower() or "sgst" in text.lower()) else "0%",
                    tax_amount="0.00",
                    amount=amount_str,
                )
            )

    return items[:250]

def regex_parse(text: str) -> ParsedDocument:
    vendor = _extract_vendor(text)
    gstin = first_match(GSTIN_PATTERNS, text)
    invoice_no = first_match(INVOICE_NO_PATTERNS, text)
    date = first_match(DATE_PATTERNS, text)
    due_date = first_match(DUE_DATE_PATTERNS, text)
    
    subtotal = normalize_amount(first_match(SUBTOTAL_PATTERNS, text))
    cgst = normalize_amount(first_match(CGST_PATTERNS, text))
    sgst = normalize_amount(first_match(SGST_PATTERNS, text))
    igst = normalize_amount(first_match(IGST_PATTERNS, text))
    
    # Calculate tax_total if individual components are available
    tax_total_val = 0.0
    for tax_item in (cgst, sgst, igst):
        try:
            tax_total_val += float(re.sub(r"[^\d.]", "", tax_item) or 0)
        except ValueError:
            pass
    tax_total = f"{tax_total_val:.2f}" if tax_total_val > 0 else "0.00"

    total = normalize_amount(first_match(TOTAL_PATTERNS, text))
    items = _extract_items(text)

    # If subtotal missing but total & tax exist, derive subtotal
    try:
        total_float = float(re.sub(r"[^\d.]", "", total) or 0)
        if (not subtotal or subtotal == "0.00") and total_float > 0 and tax_total_val > 0:
            subtotal = f"{(total_float - tax_total_val):.2f}"
    except Exception:
        pass

    confidence = BASE_CONFIDENCE
    score_components = [
        bool(vendor),
        bool(gstin),
        bool(invoice_no),
        bool(date),
        bool(total and total != "0.00"),
        bool(items),
    ]
    confidence += SCORE_COMPONENT_WEIGHT * sum(score_components)

    return ParsedDocument(
        vendor=vendor,
        gstin=gstin,
        invoice_number=invoice_no,
        date=normalize_date(date),
        due_date=normalize_date(due_date),
        subtotal=subtotal or "0.00",
        cgst=cgst or "0.00",
        sgst=sgst or "0.00",
        igst=igst or "0.00",
        tax_total=tax_total,
        total=total or "0.00",
        items=items,
        confidence=min(confidence, MAX_CONFIDENCE_CAP),
        raw_text=text,
    )

def _call_openrouter(text: str) -> Dict[str, Any]:
    api_key = settings.openrouter_api_key
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    target_models = [settings.openrouter_model] if settings.openrouter_model else []
    for fm in FREE_MODELS_LIST:
        if fm not in target_models:
            target_models.append(fm)

    last_exc = None
    for model in target_models:
        try:
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
                        {"role": "system", "content": "You extract structured JSON for invoices: vendor, gstin, invoice_number, date, due_date, subtotal, cgst, sgst, igst, tax_total, total, items (description, hsn_sac, qty, unit_price, tax_rate, tax_amount, amount)."},
                        {"role": "user", "content": build_prompt(text)},
                    ],
                },
                timeout=AI_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            return json.loads(strip_code_fences(content))
        except Exception as exc:
            last_exc = exc
            logger.warning("Call to OpenRouter model '%s' failed: %s", model, exc)

    if last_exc:
        raise last_exc
    raise RuntimeError("OpenRouter API call failed")

def _validate_ai_payload(payload: Dict[str, Any], raw_text: str) -> ParsedDocument:
    items = payload.get("items") or []
    normalized_items = []
    for item in items:
        if isinstance(item, dict):
            normalized_items.append(
                ParsedItem(
                    description=str(item.get("description", "")),
                    hsn_sac=str(item.get("hsn_sac", "")),
                    qty=str(item.get("qty", "1")),
                    unit_price=str(item.get("unit_price", "0.00")),
                    tax_rate=str(item.get("tax_rate", "0%")),
                    tax_amount=str(item.get("tax_amount", "0.00")),
                    amount=normalize_amount(str(item.get("amount", "0.00"))),
                )
            )
        else:
            normalized_items.append(ParsedItem(description=str(item), amount="0.00"))

    return ParsedDocument(
        vendor=str(payload.get("vendor", "")),
        gstin=str(payload.get("gstin", "")),
        invoice_number=str(payload.get("invoice_number", "")),
        date=normalize_date(str(payload.get("date", ""))),
        due_date=normalize_date(str(payload.get("due_date", ""))),
        subtotal=normalize_amount(str(payload.get("subtotal", "0.00"))),
        cgst=normalize_amount(str(payload.get("cgst", "0.00"))),
        sgst=normalize_amount(str(payload.get("sgst", "0.00"))),
        igst=normalize_amount(str(payload.get("igst", "0.00"))),
        tax_total=normalize_amount(str(payload.get("tax_total", "0.00"))),
        total=normalize_amount(str(payload.get("total", "0.00"))),
        items=normalized_items,
        confidence=DEFAULT_AI_CONFIDENCE,
        raw_text=raw_text,
    )

def parse_document(text: str, ocr_confidence: float = 0.0) -> ParsedDocument:
    # 1. Primary: Send raw OCR text to Free LLM models first if key exists
    if settings.openrouter_api_key:
        logger.info("Sending OCR text to Free LLM models for smart extraction...")
        try:
            payload = _call_openrouter(text)
            ai_doc = _validate_ai_payload(payload, text)
            ai_doc.ocr_confidence = ocr_confidence
            if ai_doc.vendor or ai_doc.total or ai_doc.items:
                logger.info("Free LLM extraction succeeded with %d line items.", len(ai_doc.items))
                return ai_doc
        except Exception as exc:
            logger.warning("Free LLM extraction failed: %s", exc)

    # 2. Secondary: Fallback to fast local Regex & heuristic parser
    logger.info("Falling back to local Regex parser...")
    parsed_doc = regex_parse(text)
    parsed_doc.ocr_confidence = ocr_confidence
    return parsed_doc
