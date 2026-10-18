import logging
import requests
from typing import Dict, Any

from backend.app.exports.tally_exporter import export_document_to_tally_xml
from backend.app.repository.document_repository import document_repo
from backend.app.config.settings import settings
from backend.app.utils.url_validator import validate_url, safe_request

logger = logging.getLogger(__name__)

class ERPConnectorService:
    @staticmethod
    def sync_to_tally(document: Dict[str, Any], tally_url: str = "http://localhost:9000") -> Dict[str, Any]:
        """
        Sends Tally XML voucher payload to local Tally Prime / Tally ERP 9 instance.
        """
        xml_payload = export_document_to_tally_xml(document, voucher_type="Purchase")
        doc_id = document.get("id")

        # Validate target Tally endpoint against permitted loopback configuration
        is_valid, err_msg = validate_url(
            tally_url,
            allow_local_tally=True,
            permitted_tally_url=settings.permitted_tally_url
        )
        if not is_valid:
            logger.warning("Rejected invalid Tally URL: %s", err_msg)
            return {
                "status": "Failed",
                "message": f"Disallowed or invalid Tally endpoint: {err_msg}",
                "tally_xml": xml_payload
            }

        try:
            response = safe_request(
                "POST",
                tally_url,
                allow_local_tally=True,
                permitted_tally_url=settings.permitted_tally_url,
                data=xml_payload,
                headers={"Content-Type": "text/xml; charset=utf-8"},
                connect_timeout=3.0,
                read_timeout=5.0
            )
            response.raise_for_status()
            status = "Synced"
            msg = "Successfully pushed XML voucher to Tally."
        except Exception as exc:
            logger.warning("Could not push to live Tally endpoint: %s. Marking XML generated.", exc)
            status = "Synced (XML Generated)"
            msg = "Tally XML generated and ready for import. (Live post attempt skipped or offline)"

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
        Pushes invoice payload to external Custom ERP REST API.
        """
        doc_id = document.get("id")

        # Defensive SSRF check on custom endpoint (Must be public HTTPS)
        is_valid, err_msg = validate_url(erp_endpoint, allow_local_tally=False)
        if not is_valid:
            logger.warning("Rejected invalid custom ERP URL: %s", err_msg)
            return {
                "status": "Failed",
                "message": f"Disallowed or invalid ERP endpoint: {err_msg}"
            }

        try:
            response = safe_request(
                "POST",
                erp_endpoint,
                allow_local_tally=False,
                json=document,
                headers={"Content-Type": "application/json"},
                connect_timeout=5.0,
                read_timeout=10.0
            )
            response.raise_for_status()
            status = "Synced"
            msg = f"Successfully synced voucher to Custom ERP endpoint."
        except Exception as exc:
            logger.error("Custom ERP post failed: %s", exc)
            status = "Failed"
            msg = f"Custom ERP Sync failed: {str(exc)}"

        if doc_id:
            document_repo.save({"id": doc_id, "erp_sync_status": status})

        return {
            "status": status,
            "message": msg
        }
