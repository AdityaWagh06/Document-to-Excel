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
    total: str = "0.00"
    items: List[ParsedItem] = field(default_factory=list)
    confidence: float = 0.0
    ocr_confidence: float = 0.0
    raw_text: str = ""
    status: str = "Pending Verification"  # "Verified", "Pending Verification", "Flagged Error"
    erp_sync_status: str = "Not Synced"  # "Not Synced", "Synced", "Failed"
    validation_warnings: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
