import hashlib
import hmac
import json
import logging
import os
import tempfile
from typing import Optional, Tuple, Any
import requests
from flask import Blueprint, jsonify, request
from backend.app.config.settings import settings
from backend.app.services.document_service import DocumentService
from backend.app.utils.url_validator import validate_url, safe_request

logger = logging.getLogger(__name__)

whatsapp_bp = Blueprint("whatsapp", __name__)


def verify_meta_signature(raw_body: bytes, sig_header: Optional[str], app_secret: Optional[str]) -> Tuple[bool, str]:
    """
    Validates Meta's X-Hub-Signature-256 header against the raw request body bytes.
    Uses constant-time comparison to prevent timing attacks.
    """
    if not app_secret:
        return False, "WhatsApp app secret is not configured on the server."

    if not sig_header:
        return False, "Missing X-Hub-Signature-256 header."

    clean_header = sig_header.strip()
    if not clean_header.startswith("sha256="):
        return False, "Malformed signature header: missing 'sha256=' prefix."

    received_hex = clean_header[7:].strip()
    if len(received_hex) != 64:
        return False, "Malformed signature header: invalid SHA-256 hash length."

    try:
        bytes.fromhex(received_hex)
    except ValueError:
        return False, "Malformed signature header: contains non-hexadecimal characters."

    expected_hex = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_hex.lower(), received_hex.lower()):
        return False, "Invalid signature: HMAC-SHA256 digest mismatch."

    return True, "Valid signature."


@whatsapp_bp.get("/webhook")
def verify_webhook():
    """
    WhatsApp Business API Webhook Verification Challenge.
    Verified with constant-time token comparison without hardcoded fallbacks.
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if not settings.whatsapp_verify_token:
        logger.error("WHATSAPP_VERIFY_TOKEN is not configured.")
        return jsonify({"error": "Webhook verify token is not configured on the server."}), 500

    if mode == "subscribe":
        if token and hmac.compare_digest(token, settings.whatsapp_verify_token):
            logger.info("WhatsApp webhook challenge verified successfully.")
            return challenge or "", 200
        else:
            logger.warning("WhatsApp webhook verification failed: invalid token.")
            return jsonify({"error": "Forbidden - Invalid verify token."}), 403

    return jsonify({"status": "verified", "message": "WhatsApp webhook endpoint active."}), 200


def extract_whatsapp_message_id(data: Any) -> Optional[str]:
    """
    Extracts a unique WhatsApp message ID (wamid) from Meta Cloud API or simulation payloads.
    """
    if not isinstance(data, dict):
        return None
    if "id" in data and isinstance(data["id"], str) and data["id"].strip():
        return data["id"].strip()
    if "message_id" in data and isinstance(data["message_id"], str) and data["message_id"].strip():
        return data["message_id"].strip()
    entries = data.get("entry")
    if isinstance(entries, list) and len(entries) > 0 and isinstance(entries[0], dict):
        changes = entries[0].get("changes")
        if isinstance(changes, list) and len(changes) > 0 and isinstance(changes[0], dict):
            val = changes[0].get("value")
            if isinstance(val, dict):
                messages = val.get("messages")
                if isinstance(messages, list) and len(messages) > 0 and isinstance(messages[0], dict):
                    m_id = messages[0].get("id")
                    if m_id and isinstance(m_id, str) and m_id.strip():
                        return m_id.strip()
    return None


@whatsapp_bp.post("/webhook")
def handle_incoming_whatsapp():
    """
    Handles incoming WhatsApp messages containing invoice photos.
    Verifies Meta HMAC-SHA256 signature before parsing or processing any content.
    Enforces atomic SQLite deduplication on Meta message ID (wamid).
    """
    raw_body = request.get_data()
    sig_header = request.headers.get("X-Hub-Signature-256")

    is_valid, reason = verify_meta_signature(raw_body, sig_header, settings.whatsapp_app_secret)
    if not is_valid:
        logger.warning("Rejected WhatsApp webhook POST from %s: %s", request.remote_addr, reason)
        return jsonify({"error": f"Unauthorized: {reason}"}), 401

    # Only parse JSON and validate media URLs after signature is strictly verified
    data = request.get_json(silent=True) or {}
    logger.info("Verified incoming WhatsApp webhook payload received.")

    sender = data.get("from") or data.get("sender", "+919876543210")

    # Enforce atomic message deduplication across multiple workers and restarts
    message_id = extract_whatsapp_message_id(data)
    if message_id:
        from backend.app.db.webhook_repository import webhook_event_repo
        is_new = webhook_event_repo.record_event(
            message_id=message_id,
            sender=sender,
            event_type="whatsapp_message",
            payload=data
        )
        if not is_new:
            logger.warning(
                "Duplicate WhatsApp webhook message '%s' rejected to ensure idempotent processing.",
                message_id
            )
            return jsonify({
                "status": "duplicate",
                "message": "Event already processed.",
                "message_id": message_id
            }), 200

    # Simulation or live WhatsApp Business Cloud API payload
    image_url = data.get("media_url") or data.get("image_url")

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
