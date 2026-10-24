import json
import logging
import os
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Optional
from werkzeug.utils import secure_filename

from flask import Blueprint, jsonify, request, send_file, make_response, Response

import re

from backend.app.ai import describe_ai_config
from backend.app.config.settings import settings
from backend.app.services.document_service import DocumentService, DocumentProcessingError
from backend.app.services.erp_service import ERPConnectorService
from backend.app.utils.file_validation import ALLOWED_EXTENSIONS, magic_matches_extension
from backend.app.ocr.ocr_engine import PDFProcessingError, OCREngineUnavailableError, ocr_manager
from backend.app.exports.excel_exporter import export_document_to_excel_bytes
from backend.app.exports.csv_exporter import export_document_to_csv_string
from backend.app.exports.doc_exporter import export_document_to_doc_summary
from backend.app.exports.tally_exporter import export_document_to_tally_xml

logger = logging.getLogger(__name__)

api_bp = Blueprint("api_v1", __name__)


@api_bp.get("/health")
def health_check():
    """Public liveness/readiness probe used by Docker health checks (no configuration details)."""
    try:
        from backend.app.db.connection import get_db
        with get_db() as conn:
            conn.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        logger.exception("Health check database probe failed")
        db_ok = False
    body = {"status": "ok" if db_ok else "degraded", "service": "Invoice & ERP Automation Platform", "database": db_ok}
    return jsonify(body), 200 if db_ok else 503

@api_bp.get("/system/status")
def system_status():
    """Authenticated, non-secret overview of how the server is configured."""
    return jsonify({
        "ai": describe_ai_config(),
        "ocr": ocr_manager.status(),
        "erp": ERPConnectorService.describe_config(),
        "whatsapp": {
            "webhook_secret_configured": bool(settings.whatsapp_app_secret),
            "verify_token_configured": bool(settings.whatsapp_verify_token),
            "media_download_configured": bool(settings.whatsapp_access_token),
            "simulator_enabled": settings.whatsapp_simulator_enabled,
        },
        "limits": {
            "max_upload_mb": round(settings.max_upload_size_bytes / (1024 * 1024), 1),
            "max_pdf_pages": settings.max_pdf_pages,
        },
        "environment": settings.flask_env,
    })

@api_bp.get("/")
def index():
    return jsonify({
        "name": "AI-Powered Invoice & ERP Automation Platform Backend",
        "status": "running",
        "health": "/api/v1/health",
        "documents": "/api/v1/documents",
        "analytics": "/api/v1/analytics",
        "upload": "/api/v1/upload",
    })

@api_bp.get("/favicon.ico")
def favicon():
    return make_response(("", 204))

@api_bp.post("/upload")
def upload_document():
    if "image" not in request.files and "file" not in request.files:
        return jsonify({"error": "No file provided. Expected multipart field 'image' or 'file'."}), 400

    uploaded_file = request.files.get("image") or request.files.get("file")
    if not uploaded_file or not uploaded_file.filename or uploaded_file.filename.strip() == "":
        return jsonify({"error": "Empty upload or missing filename."}), 400

    raw_filename = uploaded_file.filename
    safe_name = secure_filename(raw_filename)
    if not safe_name:
        return jsonify({"error": "Invalid or unsafe filename."}), 400

    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return jsonify({
            "error": f"File type '{suffix}' is not permitted. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        }), 400

    # Validate file magic header to prevent file extension spoofing
    header = uploaded_file.read(32)
    uploaded_file.seek(0)
    if not header or len(header) == 0:
        return jsonify({"error": "Uploaded file is empty (0 bytes)."}), 400

    is_valid_magic = magic_matches_extension(header, suffix)

    if not is_valid_magic:
        return jsonify({"error": f"Malformed file content or extension mismatch for '{safe_name}'."}), 400

    temp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            uploaded_file.save(temp_file)
            temp_path = temp_file.name

        document_payload = DocumentService.process_document(temp_path, filename=safe_name)
        return jsonify(document_payload)

    except DocumentProcessingError as d_err:
        logger.warning("Document processing failed for '%s': %s", safe_name, d_err)
        return jsonify({"error": str(d_err)}), d_err.status_code
    except OCREngineUnavailableError as o_err:
        logger.error("OCR unavailable while processing '%s': %s", safe_name, o_err)
        return jsonify({"error": str(o_err)}), 503
    except PDFProcessingError as p_err:
        logger.warning("PDF processing rejected file '%s': %s", safe_name, p_err)
        return jsonify({"error": str(p_err)}), 400
    except ValueError as v_err:
        logger.warning("Value error during document processing for '%s': %s", safe_name, v_err)
        return jsonify({"error": str(v_err)}), 400
    except Exception as exc:
        logger.exception("Failed to process upload")
        return jsonify({"error": "Failed to process document. Ensure the file contains a valid readable invoice."}), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                logger.warning("Could not remove temp file %s", temp_path)

@api_bp.get("/documents")
def get_documents():
    documents = DocumentService.get_all_documents()
    return jsonify(documents)

@api_bp.get("/documents/<doc_id>")
def get_document_by_id(doc_id: str):
    doc = DocumentService.get_document_by_id(doc_id)
    if not doc:
        return jsonify({"error": "Document not found."}), 404
    return jsonify(doc)

@api_bp.put("/documents/<doc_id>")
def update_document(doc_id: str):
    if not doc_id or doc_id.strip() == "":
        return jsonify({"error": "Document ID is required."}), 400

    updates = request.get_json(silent=True)
    if updates is None or not isinstance(updates, dict):
        return jsonify({"error": "Invalid JSON payload. Expected a JSON object."}), 400

    try:
        updated_doc = DocumentService.update_document(doc_id, updates)
    except ValueError as err:
        return jsonify({"error": str(err)}), 400
    except Exception as exc:
        logger.exception("Failed to update document %s", doc_id)
        return jsonify({"error": "Failed to update document."}), 500

    if not updated_doc:
        return jsonify({"error": "Document not found."}), 404
    return jsonify(updated_doc)

@api_bp.delete("/documents/<doc_id>")
def delete_document(doc_id: str):
    success = DocumentService.delete_document(doc_id)
    if not success:
        return jsonify({"error": "Document not found."}), 404
    return jsonify({"status": "deleted", "id": doc_id})

@api_bp.get("/analytics")
def get_analytics():
    return jsonify(DocumentService.get_analytics())

@api_bp.post("/documents/<doc_id>/sync-erp")
def sync_to_erp(doc_id: str):
    data = request.get_json(silent=True) or {}
    erp_type = str(data.get("erp_type", "tally")).lower()

    if doc_id == "latest":
        doc = DocumentService.get_latest_document()
        if not doc or not doc.get("id"):
            return jsonify({"error": "No invoices have been processed yet. Upload an invoice first."}), 404
    else:
        doc = DocumentService.get_document_by_id(doc_id)
    if not doc:
        return jsonify({"error": "Document not found."}), 404

    if erp_type == "tally":
        # The Tally endpoint is operator-configured; a client-supplied URL must match it exactly
        tally_url = data.get("tally_url") or settings.permitted_tally_url
        res = ERPConnectorService.sync_to_tally(doc, tally_url=tally_url)
    elif erp_type == "custom":
        custom_endpoint = data.get("custom_endpoint") or settings.custom_erp_endpoint
        if not custom_endpoint:
            return jsonify({"error": "Custom ERP endpoint URL is required (set CUSTOM_ERP_ENDPOINT or provide one)."}), 400
        res = ERPConnectorService.sync_to_custom_erp(doc, custom_endpoint)
    else:
        return jsonify({"error": f"Unsupported ERP type: {erp_type}"}), 400

    if res.get("status") == "Failed":
        return jsonify(res), 400

    return jsonify(res)

@api_bp.get("/download")
@api_bp.get("/documents/<doc_id>/export/<format_type>")
def download_export(doc_id: str = "latest", format_type: str = "excel"):
    if doc_id == "latest":
        doc = DocumentService.get_latest_document()
        if not doc or (not doc.get("vendor") and not doc.get("raw_text")):
            return jsonify({"error": "No document available for export."}), 400
    else:
        doc = DocumentService.get_document_by_id(doc_id)  # type: ignore[assignment]
        if not doc:
            return jsonify({"error": "Document not found."}), 404
        if not doc.get("vendor") and not doc.get("raw_text"):
            return jsonify({"error": "No document available for export."}), 400

    format_type = format_type.lower()
    inv_name = re.sub(r"[^A-Za-z0-9._-]+", "_", str(doc.get("invoice_number") or "document")).strip("._")[:60] or "document"

    if format_type in ("excel", "xlsx"):
        excel_bytes = export_document_to_excel_bytes(doc)
        buffer = BytesIO(excel_bytes)
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"{inv_name}_extraction.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    elif format_type == "csv":
        csv_str = export_document_to_csv_string(doc)
        return Response(
            csv_str,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename={inv_name}_extraction.csv"}
        )
    elif format_type in ("doc", "summary", "docx"):
        doc_str = export_document_to_doc_summary(doc)
        return Response(
            doc_str,
            mimetype="text/plain",
            headers={"Content-disposition": f"attachment; filename={inv_name}_summary.txt"}
        )
    elif format_type in ("tally", "xml"):
        xml_str = export_document_to_tally_xml(doc)
        return Response(
            xml_str,
            mimetype="application/xml",
            headers={"Content-disposition": f"attachment; filename={inv_name}_tally_voucher.xml"}
        )
    else:
        return jsonify({"error": f"Unsupported format '{format_type}'. Supported: excel, csv, doc, tally"}), 400
