import logging
import tempfile
import os
import requests
from flask import Blueprint, jsonify, request
from backend.app.services.document_service import DocumentService
from backend.app.utils.url_validator import validate_url, safe_request

logger = logging.getLogger(__name__)

whatsapp_bp = Blueprint("whatsapp", __name__)

WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "DOCUMENT_EXCEL_WHATSAPP_TOKEN")

@whatsapp_bp.get("/webhook")
def verify_webhook():
    """
    WhatsApp Business API Webhook Verification Challenge.
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe":
        if token == WHATSAPP_VERIFY_TOKEN:
            logger.info("WhatsApp webhook verified successfully.")
            return challenge, 200
        else:
            logger.warning("WhatsApp webhook verification failed: invalid token.")
            return jsonify({"error": "Forbidden - Invalid verify token."}), 403

    return jsonify({"status": "verified", "message": "WhatsApp webhook endpoint active."}), 200

@whatsapp_bp.post("/webhook")
def handle_incoming_whatsapp():
    """
    Handles incoming WhatsApp messages containing invoice photos.
    """
    data = request.get_json(silent=True) or {}
    logger.info("Incoming WhatsApp message: %s", data)

    # Simulation or live WhatsApp Business Cloud API payload
    image_url = data.get("media_url") or data.get("image_url")
    sender = data.get("from") or data.get("sender", "+919876543210")

    if not image_url:
        return jsonify({
            "status": "error",
            "message": "No media image URL provided in WhatsApp message."
        }), 400

    # Defensive URL validation against SSRF
    is_valid, err_msg = validate_url(image_url, allow_local_tally=False)
    if not is_valid:
        logger.warning("Rejected invalid WhatsApp media URL: %s", err_msg)
        return jsonify({"error": f"Disallowed media URL: {err_msg}"}), 400

    # Download image to temp file with safe requests helper
    temp_path = None
    try:
        res = safe_request(
            "GET",
            image_url,
            allow_local_tally=False,
            stream=True,
            max_response_bytes=16 * 1024 * 1024,
            connect_timeout=5.0,
            read_timeout=10.0
        )
        res.raise_for_status()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tf:
            tf.write(res.content)
            temp_path = tf.name

        doc_payload = DocumentService.process_document(temp_path, filename="whatsapp_invoice.png")
        doc_payload["source"] = f"WhatsApp ({sender})"

        reply_message = (
            f"✅ *Invoice Received & Processed via WhatsApp*\n\n"
            f"📍 Vendor: {doc_payload.get('vendor', 'N/A')}\n"
            f"📄 Inv #: {doc_payload.get('invoice_number', 'N/A')}\n"
            f"📅 Date: {doc_payload.get('date', 'N/A')}\n"
            f"💰 Total: ₹ {doc_payload.get('total', '0.00')}\n\n"
            f"Verification Status: {doc_payload.get('status')}\n"
            f"Synced with Dashboard."
        )

        return jsonify({
            "status": "success",
            "whatsapp_reply": reply_message,
            "document": doc_payload
        })

    except Exception as exc:
        logger.exception("Failed to process WhatsApp media")
        return jsonify({"error": str(exc)}), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

@whatsapp_bp.post("/simulate")
def simulate_whatsapp_upload():
    """
    Simulate uploading an invoice as if sent via WhatsApp Business.
    """
    if "image" not in request.files:
        return jsonify({"error": "No image file uploaded in 'image' field."}), 400
    
    file = request.files["image"]
    sender_phone = request.form.get("sender", "+91 98765 43210")

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tf:
            file.save(tf)
            temp_path = tf.name

        doc_payload = DocumentService.process_document(temp_path, filename=file.filename or "whatsapp.png")
        doc_payload["source"] = f"WhatsApp ({sender_phone})"

        reply_text = (
            f"✅ *Invoice Processed via WhatsApp*\n"
            f"Vendor: {doc_payload.get('vendor', 'N/A')}\n"
            f"GSTIN: {doc_payload.get('gstin', 'N/A')}\n"
            f"Invoice #: {doc_payload.get('invoice_number', 'N/A')}\n"
            f"Total: ₹ {doc_payload.get('total', '0.00')}\n"
            f"Status: {doc_payload.get('status')}"
        )

        return jsonify({
            "status": "success",
            "sender": sender_phone,
            "whatsapp_reply": reply_text,
            "document": doc_payload
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
