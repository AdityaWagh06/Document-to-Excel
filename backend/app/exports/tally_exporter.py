import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Dict, Any

def export_document_to_tally_xml(document: Dict[str, Any], voucher_type: str = "Purchase") -> str:
    vendor = document.get("vendor", "Cash Vendor")
    date_str = str(document.get("date", "")).replace("-", "").replace("/", "")
    if len(date_str) != 8:
        date_str = "20260101"

    inv_no = document.get("invoice_number", "INV-001")
    total_amount = document.get("total", "0.00").replace(",", "")
    subtotal = document.get("subtotal", "0.00").replace(",", "")
    cgst = document.get("cgst", "0.00").replace(",", "")
    sgst = document.get("sgst", "0.00").replace(",", "")
    igst = document.get("igst", "0.00").replace(",", "")

    items = document.get("items") or []

    envelope = ET.Element("ENVELOPE")
    header = ET.SubElement(envelope, "HEADER")
    ET.SubElement(header, "TALLYREQUEST").text = "Import Data"

    body = ET.SubElement(envelope, "BODY")
    import_data = ET.SubElement(body, "IMPORTDATA")
    request_desc = ET.SubElement(import_data, "REQUESTDESC")
    ET.SubElement(request_desc, "REPORTNAME").text = "Vouchers"
    
    req_data = ET.SubElement(import_data, "REQUESTDATA")
    tally_msg = ET.SubElement(req_data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})

    voucher = ET.SubElement(tally_msg, "VOUCHER", {
        "VCHTYPE": voucher_type,
        "ACTION": "Create",
        "OBJVIEW": "Accounting Voucher View"
    })

    ET.SubElement(voucher, "DATE").text = date_str
    ET.SubElement(voucher, "VOUCHERTYPENAME").text = voucher_type
    ET.SubElement(voucher, "VOUCHERNUMBER").text = inv_no
    ET.SubElement(voucher, "PARTYLEDGERNAME").text = vendor
    ET.SubElement(voucher, "PERSISTEDVIEW").text = "Accounting Voucher View"
    ET.SubElement(voucher, "NARRATION").text = f"Auto-imported from Document to Excel Platform. Invoice #{inv_no}"

    # Party Ledger (Credit entry for Vendor)
    party_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
    ET.SubElement(party_entry, "LEDGERNAME").text = vendor
    ET.SubElement(party_entry, "ISDEEMEDPOSITIVE").text = "No"
    ET.SubElement(party_entry, "AMOUNT").text = f"{float(total_amount or 0):.2f}"

    # Expense / Purchase Ledger (Debit entry)
    purchase_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
    ET.SubElement(purchase_entry, "LEDGERNAME").text = "Purchase Account"
    ET.SubElement(purchase_entry, "ISDEEMEDPOSITIVE").text = "Yes"
    ET.SubElement(purchase_entry, "AMOUNT").text = f"-{float(subtotal or total_amount or 0):.2f}"

    # Tax Ledgers if applicable
    if float(cgst or 0) > 0:
        cgst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(cgst_entry, "LEDGERNAME").text = "Input CGST"
        ET.SubElement(cgst_entry, "ISDEEMEDPOSITIVE").text = "Yes"
        ET.SubElement(cgst_entry, "AMOUNT").text = f"-{float(cgst):.2f}"

    if float(sgst or 0) > 0:
        sgst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(sgst_entry, "LEDGERNAME").text = "Input SGST"
        ET.SubElement(sgst_entry, "ISDEEMEDPOSITIVE").text = "Yes"
        ET.SubElement(sgst_entry, "AMOUNT").text = f"-{float(sgst):.2f}"

    if float(igst or 0) > 0:
        igst_entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(igst_entry, "LEDGERNAME").text = "Input IGST"
        ET.SubElement(igst_entry, "ISDEEMEDPOSITIVE").text = "Yes"
        ET.SubElement(igst_entry, "AMOUNT").text = f"-{float(igst):.2f}"

    # Inventory entries if line items present
    for item in items:
        if isinstance(item, dict) and item.get("description"):
            inv_item = ET.SubElement(voucher, "ALLINVENTORYENTRIES.LIST")
            ET.SubElement(inv_item, "STOCKITEMNAME").text = item.get("description")
            ET.SubElement(inv_item, "ISDEEMEDPOSITIVE").text = "Yes"
            ET.SubElement(inv_item, "RATE").text = f"{float(item.get('unit_price', 0) or 0):.2f}"
            ET.SubElement(inv_item, "ACTUALQTY").text = f"{item.get('qty', '1')} Pcs"
            ET.SubElement(inv_item, "BILLEDQTY").text = f"{item.get('qty', '1')} Pcs"
            ET.SubElement(inv_item, "AMOUNT").text = f"-{float(item.get('amount', 0) or 0):.2f}"

    rough_string = ET.tostring(envelope, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")
