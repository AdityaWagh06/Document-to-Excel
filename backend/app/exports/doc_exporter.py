from typing import Dict, Any

def export_document_to_doc_summary(document: Dict[str, Any]) -> str:
    vendor = document.get("vendor", "N/A")
    gstin = document.get("gstin", "N/A")
    inv_no = document.get("invoice_number", "N/A")
    date = document.get("date", "N/A")
    subtotal = document.get("subtotal", "0.00")
    tax_total = document.get("tax_total", "0.00")
    total = document.get("total", "0.00")
    status = document.get("status", "Pending Verification")
    warnings = document.get("validation_warnings", [])

    items = document.get("items") or []

    lines = [
        "==========================================================================",
        "                      INVOICE & DOCUMENT SUMMARY                          ",
        "==========================================================================",
        f" Vendor / Supplier : {vendor}",
        f" GSTIN / Tax ID    : {gstin}",
        f" Invoice Number    : {inv_no}",
        f" Invoice Date      : {date}",
        f" Verification      : {status}",
        "--------------------------------------------------------------------------",
        f" Subtotal          : ₹ {subtotal}",
        f" CGST              : ₹ {document.get('cgst', '0.00')}",
        f" SGST              : ₹ {document.get('sgst', '0.00')}",
        f" IGST              : ₹ {document.get('igst', '0.00')}",
        f" Tax Total         : ₹ {tax_total}",
        f" GRAND TOTAL       : ₹ {total}",
        "==========================================================================",
        "                              LINE ITEMS                                  ",
        "==========================================================================",
    ]

    for idx, item in enumerate(items, 1):
        if isinstance(item, dict):
            desc = item.get("description", "")
            qty = item.get("qty", "1")
            price = item.get("unit_price", "0.00")
            amt = item.get("amount", "0.00")
            lines.append(f" {idx}. {desc:<35} | Qty: {qty:<5} | Rate: ₹{price:<8} | Total: ₹{amt}")

    lines.append("==========================================================================")
    lines.append("                           VALIDATION AUDIT                               ")
    lines.append("==========================================================================")
    if warnings:
        for w in warnings:
            lines.append(f" [{w.get('type', 'info').upper()}] ({w.get('code', '')}): {w.get('message', '')}")
    else:
        lines.append(" [PASS] All automated validation checks passed successfully.")

    lines.append("==========================================================================")
    lines.append("                             RAW OCR TEXT                                 ")
    lines.append("==========================================================================")
    lines.append(document.get("raw_text", ""))

    return "\n".join(lines)
