from io import BytesIO
from typing import Dict, Any, List
import pandas as pd

from backend.app.config.excel_constants import EXCEL_ENGINE, SHEET_EXTRACTED_DATA, SHEET_SUMMARY

def document_to_dataframe(document: Dict[str, Any]) -> pd.DataFrame:
    items = document.get("items") or []
    item_rows = []
    
    vendor = document.get("vendor", "")
    gstin = document.get("gstin", "")
    invoice_number = document.get("invoice_number", "")
    date = document.get("date", "")
    due_date = document.get("due_date", "")
    subtotal = document.get("subtotal", "")
    cgst = document.get("cgst", "")
    sgst = document.get("sgst", "")
    igst = document.get("igst", "")
    tax_total = document.get("tax_total", "")
    total = document.get("total", "")
    status = document.get("status", "")

    for idx, item in enumerate(items, 1):
        if isinstance(item, dict):
            item_rows.append({
                "Item #": idx,
                "Vendor Name": vendor,
                "GSTIN": gstin,
                "Invoice Number": invoice_number,
                "Invoice Date": date,
                "Item Description": item.get("description", ""),
                "HSN/SAC": item.get("hsn_sac", ""),
                "Quantity": item.get("qty", "1"),
                "Unit Price (₹)": item.get("unit_price", "0.00"),
                "Tax Rate": item.get("tax_rate", "0%"),
                "Tax Amount (₹)": item.get("tax_amount", "0.00"),
                "Item Total (₹)": item.get("amount", "0.00"),
            })

    if not item_rows:
        item_rows.append({
            "Item #": 1,
            "Vendor Name": vendor,
            "GSTIN": gstin,
            "Invoice Number": invoice_number,
            "Invoice Date": date,
            "Item Description": "N/A",
            "HSN/SAC": "",
            "Quantity": "1",
            "Unit Price (₹)": total,
            "Tax Rate": "0%",
            "Tax Amount (₹)": tax_total,
            "Item Total (₹)": total,
        })

    return pd.DataFrame(item_rows)

def export_document_to_excel_bytes(document: Dict[str, Any]) -> bytes:
    dataframe = document_to_dataframe(document)
    buffer = BytesIO()

    summary_row = [{
        "Vendor Name": document.get("vendor", ""),
        "GSTIN": document.get("gstin", ""),
        "Invoice Number": document.get("invoice_number", ""),
        "Invoice Date": document.get("date", ""),
        "Due Date": document.get("due_date", ""),
        "Subtotal (₹)": document.get("subtotal", "0.00"),
        "CGST (₹)": document.get("cgst", "0.00"),
        "SGST (₹)": document.get("sgst", "0.00"),
        "IGST (₹)": document.get("igst", "0.00"),
        "Tax Total (₹)": document.get("tax_total", "0.00"),
        "Grand Total (₹)": document.get("total", "0.00"),
        "Verification Status": document.get("status", "Pending Verification"),
        "ERP Sync Status": document.get("erp_sync_status", "Not Synced"),
        "Extraction Confidence": f"{round((document.get('confidence', 0.0) * 100), 1)}%",
        "OCR Confidence": f"{round((document.get('ocr_confidence', 0.0) * 100), 1)}%",
    }]

    warnings = document.get("validation_warnings", [])
    warnings_rows = []
    for w in warnings:
        warnings_rows.append({
            "Warning Code": w.get("code", ""),
            "Type": w.get("type", "").upper(),
            "Field": w.get("field", ""),
            "Message": w.get("message", "")
        })
    if not warnings_rows:
        warnings_rows.append({"Warning Code": "NONE", "Type": "PASS", "Field": "ALL", "Message": "No validation issues detected."})

    with pd.ExcelWriter(buffer, engine=EXCEL_ENGINE) as writer:
        pd.DataFrame(summary_row).to_excel(writer, index=False, sheet_name=SHEET_SUMMARY)
        dataframe.to_excel(writer, index=False, sheet_name=SHEET_EXTRACTED_DATA)
        pd.DataFrame(warnings_rows).to_excel(writer, index=False, sheet_name="Validation Audit")

    buffer.seek(0)
    return buffer.read()
