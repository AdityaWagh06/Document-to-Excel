from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from io import BytesIO
from threading import Lock

# Disable OneDNN for PaddleOCR compatibility
os.environ['PADDLE_DISABLE_FAST_MATH'] = '1'
os.environ.setdefault('FLAGS_use_mkldnn', '0')

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from dotenv import load_dotenv

from backend.export import export_document_to_excel_bytes
from backend.ocr import extract_text_with_paddleocr
from backend.parser import parse_document

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

STATE_LOCK = Lock()
LATEST_DOCUMENT: dict = {
    "vendor": "",
    "date": "",
    "total": "",
    "items": [],
    "confidence": 0.0,
    "raw_text": "",
}


@app.get("/health")
def health_check():
    return jsonify({"status": "ok"})


@app.post("/upload")
def upload_document():
    if "image" not in request.files:
        return jsonify({"error": "No file provided. Expected multipart field 'image'."}), 400

    uploaded_file = request.files["image"]
    if not uploaded_file or uploaded_file.filename == "":
        return jsonify({"error": "Empty upload."}), 400

    suffix = Path(uploaded_file.filename).suffix or ".png"
    temp_path: str | None = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            uploaded_file.save(temp_file)
            temp_path = temp_file.name

        ocr_result = extract_text_with_paddleocr(temp_path)
        parsed_document = parse_document(ocr_result.text, ocr_result.confidence)
        document_payload = parsed_document.model_dump()
        document_payload["raw_text"] = ocr_result.text
        document_payload["ocr_confidence"] = ocr_result.confidence

        with STATE_LOCK:
            LATEST_DOCUMENT.update(document_payload)

        logger.info("Upload processed successfully: %s", json.dumps({
            "vendor": document_payload.get("vendor", ""),
            "date": document_payload.get("date", ""),
            "total": document_payload.get("total", ""),
            "confidence": document_payload.get("confidence", 0.0),
        }))
        logger.info("Raw OCR text: %s", ocr_result.text)

        return jsonify(document_payload)
    except Exception as exc:
        logger.exception("Failed to process upload")
        return jsonify({"error": str(exc)}), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                logger.warning("Could not remove temp file %s", temp_path)


@app.get("/download")
def download_latest_excel():
    with STATE_LOCK:
        document_snapshot = dict(LATEST_DOCUMENT)

    if not document_snapshot.get("vendor") and not document_snapshot.get("raw_text"):
        return jsonify({"error": "No processed document available yet."}), 400

    excel_bytes = export_document_to_excel_bytes(document_snapshot)
    buffer = BytesIO(excel_bytes)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="document_extraction.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True, use_reloader=False)
