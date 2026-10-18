from io import StringIO
import csv
from typing import Dict, Any, List

def export_document_to_csv_string(document: Dict[str, Any]) -> str:
    output = StringIO()
    writer = csv.writer(output)

    # Document Header Summary
    writer.writerow(["INVOICE SUMMARY"])
    writer.writerow(["Vendor Name", document.get("vendor", "")])
    writer.writerow(["GSTIN", document.get("gstin", "")])
    writer.writerow(["Invoice Number", document.get("invoice_number", "")])
    writer.writerow(["Invoice Date", document.get("date", "")])
    writer.writerow(["Due Date", document.get("due_date", "")])
    writer.writerow(["Subtotal", document.get("subtotal", "0.00")])
    writer.writerow(["CGST", document.get("cgst", "0.00")])
    writer.writerow(["SGST", document.get("sgst", "0.00")])
    writer.writerow(["IGST", document.get("igst", "0.00")])
    writer.writerow(["Tax Total", document.get("tax_total", "0.00")])
    writer.writerow(["Grand Total", document.get("total", "0.00")])
    writer.writerow(["Status", document.get("status", "Pending Verification")])
    writer.writerow([])

    # Line Items Table
    writer.writerow(["LINE ITEMS"])
    writer.writerow(["Item #", "Description", "HSN/SAC", "Qty", "Unit Price", "Tax Rate", "Tax Amount", "Total Amount"])
    
    items = document.get("items") or []
    for idx, item in enumerate(items, 1):
        if isinstance(item, dict):
            writer.writerow([
                idx,
                item.get("description", ""),
                item.get("hsn_sac", ""),
                item.get("qty", "1"),
                item.get("unit_price", "0.00"),
                item.get("tax_rate", "0%"),
                item.get("tax_amount", "0.00"),
                item.get("amount", "0.00")
            ])

    return output.getvalue()
