import logging
import re
from typing import List, Optional, Tuple

from backend.app.ai import AIProviderError, InvoiceExtraction, get_provider
from backend.app.models.document import ParsedItem, ParsedDocument
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
from backend.app.utils.currency import detect_currency, normalize_currency
from backend.app.utils.text_utils import (
    first_match,
    normalize_amount,
    normalize_date,
)

logger = logging.getLogger(__name__)

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

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

            # Detect an HSN/SAC code first so it is not mistaken for a quantity
            hsn = ""
            hsn_match = HSN_SAC_PATTERN.search(desc)
            if hsn_match and len(hsn_match.group(0)) in (4, 6, 8) and re.search(r"[A-Za-z]", desc[: hsn_match.start()]):
                hsn = hsn_match.group(0)
                desc = (desc[: hsn_match.start()] + desc[hsn_match.end():]).strip()

            # Remaining numbers before the amount are usually "qty rate"
            num_tokens = [
                normalize_amount(t)
                for t in re.findall(r"(?<![A-Za-z\d])(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?(?![A-Za-z\d])", desc)
            ]
            qty = "1"
            unit_price = amount_str
            amount_val = _safe_float(amount_str)

            if len(num_tokens) >= 2:
                try:
                    candidate_qty = float(num_tokens[-2])
                    candidate_rate = float(num_tokens[-1])
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
                        unit_price = f"{(amount_val / float(qty)):.2f}"
                except (ValueError, ZeroDivisionError):
                    pass

            # Drop the trailing qty/rate numbers from the description text
            cleaned_desc = re.sub(r"(?:\s+(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?)+\s*$", "", desc).strip()
            desc = cleaned_desc or desc

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

def _safe_float(value: str) -> float:
    try:
        return float(re.sub(r"[^0-9.]", "", value or "") or 0)
    except ValueError:
        return 0.0


# OCR often glues adjacent amounts together: "2,100.008,400.00" -> "2,100.00 8,400.00"
_GLUED_AMOUNTS = re.compile(r"(\d[.,]\d{2})(?=\d{1,3}(?:,\d{2,3})+\.\d{2})")


def regex_parse(text: str) -> ParsedDocument:
    text = _GLUED_AMOUNTS.sub(r"\1 ", text or "")
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
            tax_total_val += _safe_float(tax_item)
        except ValueError:
            pass
    tax_total = f"{tax_total_val:.2f}" if tax_total_val > 0 else "0.00"

    total = normalize_amount(first_match(TOTAL_PATTERNS, text))
    items = _extract_items(text)

    # If subtotal missing but total & tax exist, derive subtotal
    try:
        total_float = _safe_float(total)
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
        currency=detect_currency(text, gstin),
        confidence=min(confidence, MAX_CONFIDENCE_CAP),
        raw_text=text,
    )

def _clean_amount(value: str) -> str:
    """Normalizes an AI-returned amount; empty stays empty (never invented)."""
    norm = normalize_amount(value or "")
    if not norm:
        return ""
    try:
        return f"{float(norm):.2f}"
    except ValueError:
        return ""


def _ai_extraction_to_document(extraction: InvoiceExtraction, raw_text: str) -> ParsedDocument:
    gstin = extraction.gstin.upper().replace(" ", "")
    items = []
    for item in extraction.items:
        if not (item.description or item.amount):
            continue
        items.append(
            ParsedItem(
                description=item.description,
                hsn_sac=item.hsn_sac,
                qty=normalize_amount(item.qty) or "1",
                unit_price=_clean_amount(item.unit_price) or "0.00",
                tax_rate=item.tax_rate or "0%",
                tax_amount=_clean_amount(item.tax_amount) or "0.00",
                amount=_clean_amount(item.amount) or "0.00",
            )
        )

    cgst = _clean_amount(extraction.cgst)
    sgst = _clean_amount(extraction.sgst)
    igst = _clean_amount(extraction.igst)
    tax_total = _clean_amount(extraction.tax_total)
    if not tax_total and (cgst or sgst or igst):
        tax_total = f"{sum(float(x or 0) for x in (cgst, sgst, igst)):.2f}"

    return ParsedDocument(
        vendor=extraction.vendor,
        gstin=gstin,
        invoice_number=extraction.invoice_number,
        date=normalize_date(extraction.date),
        due_date=normalize_date(extraction.due_date),
        subtotal=_clean_amount(extraction.subtotal) or "0.00",
        cgst=cgst or "0.00",
        sgst=sgst or "0.00",
        igst=igst or "0.00",
        tax_total=tax_total or "0.00",
        discount=_clean_amount(extraction.discount) or "0.00",
        other_charges=_clean_amount(extraction.other_charges) or "0.00",
        total=_clean_amount(extraction.total) or "0.00",
        currency=normalize_currency(extraction.currency) or detect_currency(raw_text, gstin),
        items=items,
        raw_text=raw_text,
    )


def _digits(value: str) -> str:
    return re.sub(r"[^0-9]", "", value or "")


def _value_in_text(value: str, text_compact: str, text_digits: str, numeric: bool = False) -> bool:
    if not value:
        return True
    if numeric:
        try:
            num = float(value)
        except ValueError:
            return False
        if num == 0:
            return True
        # Accept the integer part appearing anywhere in the OCR digits (formatting varies)
        return str(int(num)) in text_digits
    compact = re.sub(r"\s+", "", value).lower()
    return compact in text_compact


def _score_ai_document(doc: ParsedDocument, source_text: str, read_from_image: bool = False) -> Tuple[float, List[str]]:
    """
    Confidence for an AI extraction: field completeness, reduced for any value
    that cannot be found in the OCR text (possible hallucination). When the AI
    also saw the page image, OCR misreads are expected, so the penalty is small.
    """
    notes: List[str] = []
    # GSTIN only counts for Indian invoices
    present = [
        bool(doc.vendor), bool(doc.invoice_number), bool(doc.date),
        doc.total not in ("", "0.00"), bool(doc.items), bool(doc.currency),
    ]
    if doc.currency == "INR":
        present.append(bool(doc.gstin))
    confidence = 0.5 + 0.48 * sum(present) / len(present)
    if not source_text.strip():
        return min(confidence, 0.85), notes

    text_compact = re.sub(r"\s+", "", source_text).lower()
    text_digits = _digits(source_text)
    checks = (
        ("invoice_number", doc.invoice_number, False),
        ("gstin", doc.gstin, False),
        ("total", doc.total, True),
    )
    for field_name, value, numeric in checks:
        if value and not _value_in_text(value, text_compact, text_digits, numeric):
            if read_from_image:
                confidence -= 0.03
                notes.append(
                    f"'{field_name}' ({value}) was read from the image and differs from the OCR text; please verify."
                )
            else:
                confidence -= 0.15
                notes.append(f"AI value for '{field_name}' ({value}) was not found in the OCR text; please verify.")
    return max(0.1, min(confidence, MAX_CONFIDENCE_CAP)), notes


def _fill_missing_from_rules(ai_doc: ParsedDocument, rules_doc: ParsedDocument, include_amounts: bool = True) -> List[str]:
    """
    Fills fields the AI left empty with values the rule parser read from the
    same text. Amounts are skipped when the AI saw the page image, because the
    OCR text is then the less reliable source.
    """
    filled = []
    for field_name in ("vendor", "gstin", "invoice_number", "date", "due_date"):
        value = getattr(rules_doc, field_name)
        if field_name in ("date", "due_date") and not ISO_DATE_RE.match(value or ""):
            continue
        if not getattr(ai_doc, field_name) and value:
            setattr(ai_doc, field_name, value)
            filled.append(field_name)
    if not include_amounts:
        return filled
    for field_name in ("subtotal", "cgst", "sgst", "igst", "tax_total", "total"):
        if getattr(ai_doc, field_name) in ("", "0.00") and getattr(rules_doc, field_name) not in ("", "0.00"):
            setattr(ai_doc, field_name, getattr(rules_doc, field_name))
            filled.append(field_name)
    return filled


def _rules_only(text: str, ocr_confidence: float, notes: List[str]) -> ParsedDocument:
    parsed_doc = regex_parse(text)
    parsed_doc.ocr_confidence = ocr_confidence
    parsed_doc.extraction_method = "rules"
    parsed_doc.extraction_notes = notes
    return parsed_doc


def parse_document(text: str, ocr_confidence: float = 0.0, images_b64_png: Optional[List[str]] = None) -> ParsedDocument:
    """
    Extracts structured invoice fields from OCR text.

    1. If an AI provider is configured, ask it for schema-validated JSON. When
       page images are given (photos, scans) they are sent with the OCR text so
       the model can correct OCR misreads; if the model cannot take images the
       call is repeated with text only.
    2. On any AI failure (or when AI is disabled) fall back to the local
       rule-based parser and record why, so the UI can tell the user.
    AI output is never trusted blindly: values absent from the OCR text lower
    the confidence score and are surfaced as review notes.
    """
    notes: List[str] = []
    try:
        provider = get_provider()
    except AIProviderError as exc:
        logger.error("AI provider misconfigured, using rule-based parser: %s", exc)
        return _rules_only(text, ocr_confidence, [f"AI extraction unavailable: {exc}"])

    if provider is None:
        return _rules_only(text, ocr_confidence, [])

    if not (text or "").strip() and not images_b64_png:
        return _rules_only(text, ocr_confidence, ["No text could be read from the document."])

    used_images = bool(images_b64_png)
    try:
        try:
            result = provider.extract_invoice(text, images_b64_png or None)
        except AIProviderError as exc:
            # Text-only models reject image input; retry with the OCR text alone
            if not used_images or exc.kind not in ("bad_request", "invalid_response", "model_not_found") or not text.strip():
                raise
            logger.info("Model could not use page images (%s); retrying with OCR text only.", exc.kind)
            used_images = False
            result = provider.extract_invoice(text)
    except AIProviderError as exc:
        logger.warning("AI extraction failed (%s); falling back to rule-based parser.", exc.kind)
        return _rules_only(text, ocr_confidence, [f"AI extraction failed, used rule-based parser instead: {exc}"])

    ai_doc = _ai_extraction_to_document(result.extraction, text)
    if not (ai_doc.vendor or ai_doc.total != "0.00" or ai_doc.items):
        notes.append("AI returned no usable invoice fields; used rule-based parser instead.")
        return _rules_only(text, ocr_confidence, notes)

    rules_doc = regex_parse(text)
    filled = _fill_missing_from_rules(ai_doc, rules_doc, include_amounts=not used_images)
    if filled:
        notes.append("Filled from rule-based parser: " + ", ".join(filled) + ".")

    confidence, score_notes = _score_ai_document(ai_doc, text, read_from_image=used_images)
    ai_doc.confidence = round(confidence, 4)
    ai_doc.ocr_confidence = ocr_confidence
    ai_doc.extraction_method = f"ai-image:{result.provider}" if used_images else f"ai:{result.provider}"
    ai_doc.ai_model = result.model
    ai_doc.extraction_notes = notes + score_notes
    logger.info("AI extraction (%s/%s) produced %d line items.", result.provider, result.model, len(ai_doc.items))
    return ai_doc


def parse_document_from_images(images_b64_png: List[str]) -> ParsedDocument:
    """
    Vision fallback: extracts invoice fields directly from page images when OCR
    produced no text. Raises AIProviderError when AI is unavailable.
    """
    provider = get_provider()
    if provider is None:
        raise AIProviderError("No AI provider is configured for image-based extraction.", "config")
    result = provider.extract_invoice_from_images(images_b64_png)
    doc = _ai_extraction_to_document(result.extraction, "")
    confidence, _ = _score_ai_document(doc, "")
    doc.confidence = round(min(confidence, 0.75), 4)
    doc.extraction_method = f"ai-vision:{result.provider}"
    doc.ai_model = result.model
    doc.extraction_notes = [
        "No OCR text was available; fields were read by the AI model directly from the page image. Verify all values."
    ]
    return doc
