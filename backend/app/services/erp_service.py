import logging
import re
from typing import Dict, Any, List

from backend.app.exports.tally_exporter import export_document_to_tally_xml
from backend.app.repository.document_repository import document_repo
from backend.app.config.settings import settings
from backend.app.utils.url_validator import validate_url, safe_request

logger = logging.getLogger(__name__)

# Fields sent to a custom ERP (raw OCR text and internal metadata are excluded)
CUSTOM_ERP_FIELDS = (
    "id", "vendor", "gstin", "invoice_number", "date", "due_date", "subtotal",
    "cgst", "sgst", "igst", "tax_total", "total", "items", "status", "source", "created_at",
)


def _missing_required_fields(document: Dict[str, Any]) -> List[str]:
    missing = []
    if not str(document.get("vendor") or "").strip():
        missing.append("vendor")
    if not str(document.get("invoice_number") or "").strip():
        missing.append("invoice number")
    total = re.sub(r"[^\d.]", "", str(document.get("total") or ""))
    try:
        if float(total or 0) <= 0:
            missing.append("total")
    except ValueError:
        missing.append("total")
    return missing


def _parse_tally_response(text: str) -> Dict[str, Any]:
    """Tally answers HTTP 200 even on failure; the counters in the body tell the truth."""
    def count(tag: str) -> int:
        match = re.search(rf"<{tag}>\s*(\d+)\s*</{tag}>", text or "", re.IGNORECASE)
        return int(match.group(1)) if match else 0

    line_error = re.search(r"<LINEERROR>(.*?)</LINEERROR>", text or "", re.IGNORECASE | re.DOTALL)
    return {
        "created": count("CREATED"),
        "altered": count("ALTERED"),
        "errors": count("ERRORS"),
        "line_error": line_error.group(1).strip() if line_error else "",
    }


class ERPConnectorService:
    @staticmethod
    def describe_config() -> Dict[str, Any]:
        return {
            "tally_url": settings.permitted_tally_url,
            "tally_company": settings.tally_company_name,
            "custom_erp_configured": bool(settings.custom_erp_endpoint),
            "custom_erp_auth": bool(settings.custom_erp_api_key),
        }

    @staticmethod
    def sync_to_tally(document: Dict[str, Any], tally_url: str = "") -> Dict[str, Any]:
        """
        Generates a Tally purchase voucher and posts it to the configured Tally
        XML server. Status is "Synced" only when Tally confirms the voucher was
        created; when Tally cannot be reached the status is "XML Generated" so the
        user can import the file manually.
        """
        tally_url = tally_url or settings.permitted_tally_url
        xml_payload = export_document_to_tally_xml(document, voucher_type="Purchase")
        doc_id = document.get("id")

        missing = _missing_required_fields(document)
        if missing:
            return {
                "status": "Failed",
                "message": f"Cannot sync to Tally: missing {', '.join(missing)}. Correct the invoice and save first.",
                "tally_xml": xml_payload,
            }

        currency = str(document.get("currency") or "").strip().upper()
        if currency not in ("", "INR"):
            return {
                "status": "Failed",
                "message": (
                    f"This invoice is in {currency}. Tally vouchers here are posted in INR, and amounts are "
                    "never converted automatically. Enter it in Tally with the exchange rate, or export it to Excel."
                ),
                "tally_xml": xml_payload,
            }

        # The endpoint must exactly match the operator-configured PERMITTED_TALLY_URL
        is_valid, err_msg = validate_url(
            tally_url,
            allow_local_tally=True,
            permitted_tally_url=settings.permitted_tally_url
        )
        if not is_valid:
            logger.warning("Rejected invalid Tally URL: %s", err_msg)
            return {
                "status": "Failed",
                "message": f"Disallowed Tally endpoint. Only the configured PERMITTED_TALLY_URL "
                           f"({settings.permitted_tally_url}) may be used. ({err_msg})",
                "tally_xml": xml_payload
            }

        try:
            response = safe_request(
                "POST",
                tally_url,
                allow_local_tally=True,
                permitted_tally_url=settings.permitted_tally_url,
                data=xml_payload.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8"},
                connect_timeout=3.0,
                read_timeout=15.0
            )
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Tally at %s not reachable: %s", tally_url, type(exc).__name__)
            status = "XML Generated"
            msg = (
                f"Tally was not reachable at {tally_url}. The voucher XML was generated instead; "
                "download it and import it in Tally (Import > Vouchers), or start Tally with the XML server "
                "enabled and try again."
            )
        else:
            result = _parse_tally_response(response.text)
            if result["created"] + result["altered"] > 0 and result["errors"] == 0:
                status = "Synced"
                msg = "Tally confirmed the purchase voucher was created."
            else:
                status = "Failed"
                detail = result["line_error"] or "Tally did not report the voucher as created."
                msg = (
                    f"Tally rejected the voucher: {detail} Check that the ledgers "
                    f"('{settings.tally_purchase_ledger}', GST ledgers, and the vendor ledger) exist in the company."
                )

        if doc_id:
            document_repo.save({"id": doc_id, "erp_sync_status": status})

        return {
            "status": status,
            "message": msg,
            "tally_xml": xml_payload
        }

    @staticmethod
    def sync_to_custom_erp(document: Dict[str, Any], erp_endpoint: str) -> Dict[str, Any]:
        """
        POSTs the invoice JSON to a custom ERP REST endpoint (public HTTPS only).
        If CUSTOM_ERP_API_KEY is set it is sent as a Bearer token.
        """
        doc_id = document.get("id")

        is_valid, err_msg = validate_url(erp_endpoint, allow_local_tally=False)
        if not is_valid:
            logger.warning("Rejected invalid custom ERP URL: %s", err_msg)
            return {
                "status": "Failed",
                "message": f"Disallowed or invalid ERP endpoint: {err_msg}"
            }

        headers = {"Content-Type": "application/json"}
        # Never forward the ERP credential to an endpoint other than the configured one
        if settings.custom_erp_api_key and erp_endpoint.strip() == settings.custom_erp_endpoint:
            headers["Authorization"] = f"Bearer {settings.custom_erp_api_key}"
        payload = {k: document.get(k) for k in CUSTOM_ERP_FIELDS if k in document}

        try:
            response = safe_request(
                "POST",
                erp_endpoint,
                allow_local_tally=False,
                json=payload,
                headers=headers,
                connect_timeout=5.0,
                read_timeout=15.0
            )
            response.raise_for_status()
            status = "Synced"
            msg = f"ERP endpoint accepted the invoice (HTTP {response.status_code})."
        except Exception as exc:
            code = getattr(getattr(exc, "response", None), "status_code", None)
            logger.error("Custom ERP post failed: %s", type(exc).__name__)
            status = "Failed"
            msg = f"Custom ERP sync failed{f' (HTTP {code})' if code else ''}: {type(exc).__name__}."

        if doc_id:
            document_repo.save({"id": doc_id, "erp_sync_status": status})

        return {
            "status": status,
            "message": msg
        }
