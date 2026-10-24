"""
Tally Prime / Tally ERP 9 purchase voucher XML.

The voucher is an accounting-view voucher (party, purchase, GST and round-off
ledgers). The ledgers must already exist in the target Tally company with the
names configured below, otherwise Tally reports an import error. Inventory
(stock item) lines are only included when TALLY_INCLUDE_INVENTORY=true, because
they require matching stock items and an item-invoice voucher setup.
"""
import os
import xml.etree.ElementTree as ET
from datetime import date as date_cls
from typing import Any, Dict
from xml.dom import minidom

from backend.app.utils.text_utils import amount_to_float


def _ledger_names() -> Dict[str, str]:
    return {
        "purchase": os.getenv("TALLY_PURCHASE_LEDGER", "Purchase Account"),
        "cgst": os.getenv("TALLY_CGST_LEDGER", "Input CGST"),
        "sgst": os.getenv("TALLY_SGST_LEDGER", "Input SGST"),
        "igst": os.getenv("TALLY_IGST_LEDGER", "Input IGST"),
        "round_off": os.getenv("TALLY_ROUND_OFF_LEDGER", "Round Off"),
    }


def _tally_date(value: str) -> str:
    digits = str(value or "").replace("-", "").replace("/", "")
    if len(digits) == 8 and digits.isdigit() and digits[:2] in ("19", "20"):
        return digits
    # Tally requires a date; fall back to today and flag it in the narration
    return date_cls.today().strftime("%Y%m%d")


def _ledger_entry(voucher: ET.Element, name: str, amount: float, debit: bool) -> None:
    entry = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
    ET.SubElement(entry, "LEDGERNAME").text = name
    ET.SubElement(entry, "ISDEEMEDPOSITIVE").text = "Yes" if debit else "No"
    # Tally convention: debit amounts are negative, credit amounts positive
    ET.SubElement(entry, "AMOUNT").text = f"{-amount if debit else amount:.2f}"


def export_document_to_tally_xml(document: Dict[str, Any], voucher_type: str = "Purchase") -> str:
    ledgers = _ledger_names()
    vendor = str(document.get("vendor") or "").strip() or "Cash Vendor"
    raw_date = str(document.get("date") or "")
    date_str = _tally_date(raw_date)
    inv_no = str(document.get("invoice_number") or "").strip()

    total = amount_to_float(document.get("total"))
    subtotal = amount_to_float(document.get("subtotal"))
    cgst = amount_to_float(document.get("cgst"))
    sgst = amount_to_float(document.get("sgst"))
    igst = amount_to_float(document.get("igst"))
    tax = round(cgst + sgst + igst, 2)

    purchase_amount = subtotal if subtotal > 0 else round(total - tax, 2)
    if total <= 0:
        total = round(purchase_amount + tax, 2)
    round_off = round(total - (purchase_amount + tax), 2)

    envelope = ET.Element("ENVELOPE")
    header = ET.SubElement(envelope, "HEADER")
    ET.SubElement(header, "TALLYREQUEST").text = "Import Data"

    body = ET.SubElement(envelope, "BODY")
    import_data = ET.SubElement(body, "IMPORTDATA")
    request_desc = ET.SubElement(import_data, "REQUESTDESC")
    ET.SubElement(request_desc, "REPORTNAME").text = "Vouchers"
    company = os.getenv("TALLY_COMPANY_NAME", "").strip()
    if company:
        static_vars = ET.SubElement(request_desc, "STATICVARIABLES")
        ET.SubElement(static_vars, "SVCURRENTCOMPANY").text = company

    req_data = ET.SubElement(import_data, "REQUESTDATA")
    tally_msg = ET.SubElement(req_data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})

    voucher = ET.SubElement(tally_msg, "VOUCHER", {
        "VCHTYPE": voucher_type,
        "ACTION": "Create",
        "OBJVIEW": "Accounting Voucher View",
    })

    ET.SubElement(voucher, "DATE").text = date_str
    ET.SubElement(voucher, "VOUCHERTYPENAME").text = voucher_type
    if inv_no:
        ET.SubElement(voucher, "VOUCHERNUMBER").text = inv_no
        ET.SubElement(voucher, "REFERENCE").text = inv_no
    gstin = str(document.get("gstin") or "").strip()
    if gstin:
        ET.SubElement(voucher, "PARTYGSTIN").text = gstin
    ET.SubElement(voucher, "PARTYLEDGERNAME").text = vendor
    ET.SubElement(voucher, "PERSISTEDVIEW").text = "Accounting Voucher View"
    narration = f"Imported from Invoice Automation Platform. Invoice #{inv_no or 'N/A'}"
    if date_str != raw_date.replace("-", "").replace("/", ""):
        narration += " (invoice date missing or unreadable - voucher dated on import day, please verify)"
    ET.SubElement(voucher, "NARRATION").text = narration

    _ledger_entry(voucher, vendor, total, debit=False)
    _ledger_entry(voucher, ledgers["purchase"], purchase_amount, debit=True)
    if cgst > 0:
        _ledger_entry(voucher, ledgers["cgst"], cgst, debit=True)
    if sgst > 0:
        _ledger_entry(voucher, ledgers["sgst"], sgst, debit=True)
    if igst > 0:
        _ledger_entry(voucher, ledgers["igst"], igst, debit=True)
    if abs(round_off) >= 0.01:
        _ledger_entry(voucher, ledgers["round_off"], round_off, debit=True)

    if os.getenv("TALLY_INCLUDE_INVENTORY", "false").strip().lower() == "true":
        for item in document.get("items") or []:
            if isinstance(item, dict) and item.get("description"):
                inv_item = ET.SubElement(voucher, "ALLINVENTORYENTRIES.LIST")
                ET.SubElement(inv_item, "STOCKITEMNAME").text = str(item.get("description"))
                ET.SubElement(inv_item, "ISDEEMEDPOSITIVE").text = "Yes"
                ET.SubElement(inv_item, "RATE").text = f"{amount_to_float(item.get('unit_price')):.2f}"
                qty = str(item.get("qty") or "1")
                ET.SubElement(inv_item, "ACTUALQTY").text = f"{qty} Nos"
                ET.SubElement(inv_item, "BILLEDQTY").text = f"{qty} Nos"
                ET.SubElement(inv_item, "AMOUNT").text = f"-{amount_to_float(item.get('amount')):.2f}"

    rough_string = ET.tostring(envelope, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")
