from dataclasses import dataclass, field
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

@dataclass
class OCRResult:
    text: str
    confidence: float
    raw_lines: list[str]

@dataclass
class ParsedItem:
    description: str = ""
    hsn_sac: str = ""
    qty: str = "1"
    unit_price: str = "0.00"
    tax_rate: str = "0%"
    tax_amount: str = "0.00"
    amount: str = "0.00"

@dataclass
class ValidationWarning:
    code: str
    type: str  # "error", "warning", "info"
    field: str
    message: str

@dataclass
class ParsedDocument:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    vendor: str = ""
    gstin: str = ""
    invoice_number: str = ""
    date: str = ""
    due_date: str = ""
    subtotal: str = "0.00"
    cgst: str = "0.00"
    sgst: str = "0.00"
    igst: str = "0.00"
    tax_total: str = "0.00"
    discount: str = "0.00"
    other_charges: str = "0.00"  # tip, service charge, shipping, round-off
    total: str = "0.00"
    currency: str = ""  # ISO 4217 code as printed on the document; never converted
    items: List[ParsedItem] = field(default_factory=list)
    confidence: float = 0.0
    ocr_confidence: float = 0.0
    raw_text: str = ""
    status: str = "Pending Verification"  # "Verified", "Pending Verification", "Flagged Error"
    erp_sync_status: str = "Not Synced"  # "Not Synced", "Synced", "Failed"
    validation_warnings: List[Dict[str, Any]] = field(default_factory=list)
    extraction_method: str = "rules"  # "rules", "ai:openai", "ai:openrouter", "ai-vision:openai"
    ai_model: str = ""
    extraction_notes: List[str] = field(default_factory=list)
    source: str = "Manual Upload"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
