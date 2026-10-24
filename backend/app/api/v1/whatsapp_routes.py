import hashlib
import hmac
import logging
import os
import re
import tempfile
from typing import Optional, Tuple, Any, Dict
from flask import Blueprint, jsonify, request
from backend.app.config.settings import settings
from backend.app.db.webhook_repository import webhook_event_repo
from backend.app.ocr.ocr_engine import PDFProcessingError
from backend.app.services.document_service import DocumentService, DocumentProcessingError
from backend.app.utils.file_validation import detect_file_type
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


def extract_meta_message(data: Any) -> Optional[Dict[str, Any]]:
    """Returns the first message object of a Meta Cloud API webhook payload, if any."""
    try:
        value = data["entry"][0]["changes"][0]["value"]
        messages = value.get("messages")
        if isinstance(messages, list) and messages and isinstance(messages[0], dict):
            return messages[0]
    except (KeyError, IndexError, TypeError, AttributeError):
        pass
    return None


def _download_meta_media(media_id: str) -> bytes:
    """
    Downloads WhatsApp media via the Graph API: first resolve the media ID to a
    short-lived URL, then fetch it with the same bearer token.
    """
    if not settings.whatsapp_access_token:
        raise WhatsAppConfigError(
            "WHATSAPP_ACCESS_TOKEN is not configured, so media sent to the WhatsApp number cannot be downloaded."
        )
    auth = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    meta_url = f"https://graph.facebook.com/{settings.whatsapp_graph_api_version}/{media_id}"
    meta = safe_request("GET", meta_url, headers=auth, connect_timeout=5.0, read_timeout=10.0)
    meta.raise_for_status()
    media_url = (meta.json() or {}).get("url")
    if not media_url:
        raise ValueError("Graph API did not return a media URL.")
    media = safe_request(
        "GET", media_url, headers=auth, stream=True,
        max_response_bytes=settings.max_upload_size_bytes, connect_timeout=5.0, read_timeout=20.0,
    )
    media.raise_for_status()
    return media.content


def _send_whatsapp_reply(recipient: str, text: str) -> bool:
    """Sends a text reply through the Cloud API when credentials are configured."""
    if not (settings.whatsapp_send_replies and settings.whatsapp_access_token and settings.whatsapp_phone_number_id):
        return False
    try:
        url = (
            f"https://graph.facebook.com/{settings.whatsapp_graph_api_version}/"
            f"{settings.whatsapp_phone_number_id}/messages"
        )
        res = safe_request(
            "POST", url,
            headers={"Authorization": f"Bearer {settings.whatsapp_access_token}", "Content-Type": "application/json"},
            json={"messaging_product": "whatsapp", "to": recipient, "type": "text", "text": {"body": text[:4000]}},
            connect_timeout=5.0, read_timeout=10.0,
        )
        res.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("Could not send WhatsApp reply: %s", type(exc).__name__)
        return False


class WhatsAppConfigError(Exception):
    pass


def _build_reply(doc_payload: Dict[str, Any]) -> str:
    return (
        f"✅ *Invoice received and processed*\n\n"
        f"Vendor: {doc_payload.get('vendor') or 'N/A'}\n"
        f"GSTIN: {doc_payload.get('gstin') or 'N/A'}\n"
        f"Invoice #: {doc_payload.get('invoice_number') or 'N/A'}\n"
        f"Date: {doc_payload.get('date') or 'N/A'}\n"
        f"Total: ₹ {doc_payload.get('total') or '0.00'}\n\n"
        f"Status: {doc_payload.get('status')}"
    )


def _process_media_bytes(content: bytes, sender: str) -> Dict[str, Any]:
    suffix = detect_file_type(content[:32])
    if suffix is None:
        raise UnsupportedMediaError("Only invoice photos (JPG, PNG, WEBP) and PDF documents are supported.")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
            tf.write(content)
            temp_path = tf.name
        return DocumentService.process_document(
            temp_path, filename=f"whatsapp_invoice{suffix}", source=f"WhatsApp ({sender})"
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


class UnsupportedMediaError(Exception):
    pass


@whatsapp_bp.post("/webhook")
def handle_incoming_whatsapp():
    """
    Handles incoming WhatsApp messages containing invoice photos or PDFs.
    Verifies Meta HMAC-SHA256 signature before parsing or processing any content.
    Enforces atomic SQLite deduplication on Meta message ID (wamid).

    Accepts the real Meta Cloud API payload (image/document message with a media
    ID, downloaded through the Graph API) and, for testing, a simplified payload
    with a direct HTTPS "media_url".
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

    meta_message = extract_meta_message(data)
    image_url = data.get("media_url") or data.get("image_url")
    media_id = None
    if meta_message and not image_url:
        msg_type = meta_message.get("type")
        if msg_type in ("image", "document") and isinstance(meta_message.get(msg_type), dict):
            media_id = meta_message[msg_type].get("id")

    if not image_url and not media_id:
        if "entry" in data:
            # Status callbacks, text messages etc.: acknowledge so Meta does not retry
            return jsonify({"status": "ignored", "message": "No invoice image or document in this event."}), 200
        return jsonify({
            "status": "error",
            "message": "No media image URL provided in WhatsApp message."
        }), 400

    sender = str(
        data.get("from") or data.get("sender") or (meta_message or {}).get("from") or "unknown"
    )[:32]

    # Enforce atomic message deduplication across multiple workers and restarts
    message_id = extract_whatsapp_message_id(data)
    if message_id:
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

    try:
        if image_url:
            # Defensive URL validation against SSRF
            url_ok, err_msg = validate_url(image_url, allow_local_tally=False)
            if not url_ok:
                logger.warning("Rejected invalid WhatsApp media URL: %s", err_msg)
                webhook_event_repo.update_status(message_id, "rejected")
                return jsonify({"error": f"Disallowed media URL: {err_msg}"}), 400
            res = safe_request(
                "GET",
                image_url,
                allow_local_tally=False,
                stream=True,
                max_response_bytes=settings.max_upload_size_bytes,
                connect_timeout=5.0,
                read_timeout=10.0
            )
            res.raise_for_status()
            content = res.content
        else:
            content = _download_meta_media(media_id)

        doc_payload = _process_media_bytes(content, sender)
        reply_message = _build_reply(doc_payload)
        reply_sent = _send_whatsapp_reply(sender, reply_message) if media_id else False
        webhook_event_repo.update_status(message_id, "processed")

        return jsonify({
            "status": "success",
            "whatsapp_reply": reply_message,
            "reply_sent": reply_sent,
            "document": doc_payload
        })

    except WhatsAppConfigError as exc:
        logger.error("WhatsApp media download not configured: %s", exc)
        webhook_event_repo.update_status(message_id, "not_configured")
        # 200 so Meta does not retry endlessly; the error is visible in logs
        return jsonify({"status": "error", "message": str(exc)}), 200
    except (UnsupportedMediaError, DocumentProcessingError, PDFProcessingError) as exc:
        webhook_event_repo.update_status(message_id, "rejected")
        if media_id:
            _send_whatsapp_reply(sender, f"❌ We could not process this file: {exc}")
        return jsonify({"status": "error", "message": str(exc)}), 200 if media_id else 400
    except Exception:
        logger.exception("Failed to process WhatsApp media")
        # Transient failure: release the event so Meta's retry is processed again
        webhook_event_repo.release_event(message_id)
        return jsonify({"error": "Failed to process WhatsApp media. The delivery can be retried."}), 500


@whatsapp_bp.post("/simulate")
def simulate_whatsapp_upload():
    """
    SIMULATION ONLY: processes an uploaded invoice as if it had arrived via
    WhatsApp. Nothing is sent to or received from WhatsApp.
    """
    if not settings.whatsapp_simulator_enabled:
        return jsonify({"error": "The WhatsApp simulator is disabled (WHATSAPP_SIMULATOR_ENABLED=false)."}), 404

    file = request.files.get("image") or request.files.get("file")
    if not file:
        return jsonify({"error": "No image file uploaded in 'image' field."}), 400

    sender_phone = re.sub(r"[^0-9+ ]", "", request.form.get("sender", "+91 98765 43210"))[:20] or "unknown"
    content = file.read(settings.max_upload_size_bytes + 1)
    if not content:
        return jsonify({"error": "Uploaded file is empty (0 bytes)."}), 400

    try:
        doc_payload = _process_media_bytes(content, sender_phone)
    except UnsupportedMediaError as exc:
        return jsonify({"error": str(exc)}), 400
    except DocumentProcessingError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except PDFProcessingError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        logger.exception("WhatsApp simulation failed")
        return jsonify({"error": "Failed to process the simulated WhatsApp invoice."}), 500

    return jsonify({
        "status": "success",
        "simulated": True,
        "sender": sender_phone,
        "whatsapp_reply": _build_reply(doc_payload),
        "document": doc_payload
    })
