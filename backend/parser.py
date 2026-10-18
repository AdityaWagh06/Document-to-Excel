# Compatibility Wrapper for Document Parser
from backend.app.models.document import ParsedItem, ParsedDocument
from backend.app.config.regex_patterns import DATE_PATTERNS, TOTAL_PATTERNS, ITEM_PATTERN
from backend.app.utils.text_utils import (
    first_match as _first_match,
    normalize_amount as _normalize_amount,
    normalize_date as _normalize_date,
    strip_code_fences as _strip_code_fences,
)
from backend.app.config.ai_constants import build_prompt as _build_prompt
from backend.app.parsers.document_parser import (
    _extract_vendor,
    _extract_items,
    regex_parse,
    _call_openrouter,
    _validate_ai_payload,
    parse_document,
)
