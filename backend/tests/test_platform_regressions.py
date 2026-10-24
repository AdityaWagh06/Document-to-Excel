"""
Regression tests for the client-handover hardening work: amount parsing, GST
rules, honest ERP status reporting, WhatsApp Cloud API handling, PDF text
layers, OCR/AI fallbacks and concurrent database access.
"""
import hashlib
import hmac
import io
import json
import os
import tempfile
import threading
import unittest
import uuid
from unittest.mock import MagicMock, patch

import fitz
import requests

from backend.app import create_app
from backend.app.config.settings import settings
from backend.app.db.connection import init_db
from backend.app.exports.tally_exporter import export_document_to_tally_xml
from backend.app.models.document import OCRResult
from backend.app.repository.document_repository import DocumentRepository, document_repo
from backend.app.services.erp_service import ERPConnectorService, _parse_tally_response
from backend.app.services.validation_service import ValidationEngine, gstin_checksum_valid
from backend.app.utils.text_utils import normalize_amount

API_HEADERS = {"X-API-Key": settings.api_secret_key}


def _doc(**overrides):
    base = {
        "id": f"doc-{uuid.uuid4().hex[:8]}",
        "vendor": "ACME Industrial Supplies",
        "gstin": "27AAPFU0939F1ZV",
        "invoice_number": f"INV-{uuid.uuid4().hex[:6]}",
        "date": "2026-03-12",
        "subtotal": "1000.00",
        "cgst": "90.00",
        "sgst": "90.00",
        "igst": "0.00",
        "tax_total": "180.00",
        "total": "1180.00",
        "items": [],
        "raw_text": "invoice",
    }
    base.update(overrides)
    return base


class TestAmountNormalization(unittest.TestCase):
    def test_common_formats(self):
        cases = {
            "1,180.00": "1180.00",
            "1,18,000.50": "118000.50",
            "₹ 2,500.00": "2500.00",
            "118.000,00": "118000.00",
            "1180,50": "1180.50",
            "12.50": "12.50",
            "": "",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_amount(raw), expected)


class TestRuleBasedParser(unittest.TestCase):
    TEXT = """Sharma Office Supplies Pvt Ltd
GSTIN: 27AAPFU0939F1ZV
Invoice No: INV-2026-0107
Invoice Date: 15/09/2026
Description            HSN    Qty   Rate     Amount
A4 Paper Ream 4802 10 250.00 2,500.00
Printer Toner 8443 2 1,250.00 2,500.00
Subtotal 5,000.00
CGST 9% 450.00
SGST @ 9% : 450.00
Grand Total 5,900.00"""

    def test_tax_rates_without_parentheses_and_grouped_amounts(self):
        from backend.app.parsers.document_parser import regex_parse
        doc = regex_parse(self.TEXT)
        self.assertEqual((doc.cgst, doc.sgst, doc.tax_total), ("450.00", "450.00", "900.00"))
        self.assertEqual((doc.subtotal, doc.total), ("5000.00", "5900.00"))

    def test_line_items_hsn_qty_rate(self):
        from backend.app.parsers.document_parser import regex_parse
        items = regex_parse(self.TEXT).items
        self.assertEqual(len(items), 2)
        self.assertEqual(
            (items[0].description, items[0].hsn_sac, items[0].qty, items[0].unit_price, items[0].amount),
            ("A4 Paper Ream", "4802", "10", "250.00", "2500.00"),
        )
        self.assertEqual((items[1].qty, items[1].unit_price), ("2", "1250.00"))


class TestGstValidation(unittest.TestCase):
    def test_gstin_checksum(self):
        self.assertTrue(gstin_checksum_valid("27AAPFU0939F1ZV"))
        self.assertFalse(gstin_checksum_valid("27AAPFU0939F1ZX"))

    def _codes(self, doc):
        return {w["code"] for w in ValidationEngine.validate_document(doc, [])}

    def test_bad_checksum_warns(self):
        self.assertIn("INVALID_GST_CHECKSUM", self._codes(_doc(gstin="27AAPFU0939F1ZX")))

    def test_valid_invoice_has_no_gst_warnings(self):
        codes = self._codes(_doc())
        self.assertFalse({"INVALID_GST_CHECKSUM", "INVALID_GST_FORMAT", "GST_TYPE_CONFLICT", "TAX_MISMATCH"} & codes)

    def test_igst_with_cgst_conflict(self):
        self.assertIn("GST_TYPE_CONFLICT", self._codes(_doc(igst="50.00", tax_total="230.00", total="1230.00")))

    def test_unequal_cgst_sgst(self):
        self.assertIn("CGST_SGST_MISMATCH", self._codes(_doc(sgst="40.00", tax_total="130.00", total="1130.00")))

    def test_low_confidence_flagged(self):
        self.assertIn("LOW_CONFIDENCE", self._codes(_doc(confidence=0.4)))


class TestTallyIntegration(unittest.TestCase):
    def test_voucher_balances(self):
        xml = export_document_to_tally_xml(_doc(total="1180.40"))
        import re
        amounts = [float(a) for a in re.findall(r"<AMOUNT>(-?[\d.]+)</AMOUNT>", xml)]
        self.assertAlmostEqual(sum(amounts), 0.0, places=2)
        self.assertIn("Round Off", xml)

    @patch("backend.app.services.erp_service.document_repo")
    @patch("backend.app.services.erp_service.safe_request", side_effect=requests.ConnectionError("refused"))
    def test_offline_tally_is_not_reported_as_synced(self, _req, repo):
        res = ERPConnectorService.sync_to_tally(_doc(), "http://localhost:9000")
        self.assertEqual(res["status"], "XML Generated")
        self.assertIn("not reachable", res["message"])
        repo.save.assert_called_with({"id": unittest.mock.ANY, "erp_sync_status": "XML Generated"})

    @patch("backend.app.services.erp_service.document_repo")
    @patch("backend.app.services.erp_service.safe_request")
    def test_tally_confirmation_marks_synced(self, req, _repo):
        req.return_value = MagicMock(text="<RESPONSE><CREATED>1</CREATED><ERRORS>0</ERRORS></RESPONSE>")
        self.assertEqual(ERPConnectorService.sync_to_tally(_doc(), "http://localhost:9000")["status"], "Synced")

    @patch("backend.app.services.erp_service.document_repo")
    @patch("backend.app.services.erp_service.safe_request")
    def test_tally_line_error_marks_failed(self, req, _repo):
        req.return_value = MagicMock(
            text="<RESPONSE><CREATED>0</CREATED><ERRORS>1</ERRORS><LINEERROR>Ledger 'X' does not exist!</LINEERROR></RESPONSE>"
        )
        res = ERPConnectorService.sync_to_tally(_doc(), "http://localhost:9000")
        self.assertEqual(res["status"], "Failed")
        self.assertIn("does not exist", res["message"])

    def test_missing_fields_block_sync(self):
        res = ERPConnectorService.sync_to_tally(_doc(vendor="", total="0"), "http://localhost:9000")
        self.assertEqual(res["status"], "Failed")
        self.assertIn("vendor", res["message"])

    def test_tally_response_parser(self):
        parsed = _parse_tally_response("<CREATED>2</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS>")
        self.assertEqual(parsed["created"], 2)

    @patch("backend.app.services.erp_service.validate_url", return_value=(True, ""))
    @patch("backend.app.services.erp_service.document_repo")
    @patch("backend.app.services.erp_service.safe_request")
    def test_custom_erp_key_only_sent_to_configured_endpoint(self, req, _repo, _validate):
        req.return_value = MagicMock(status_code=200)
        with patch.object(settings, "custom_erp_endpoint", "https://erp.example.com/invoices"), \
                patch.object(settings, "custom_erp_api_key", "erp-secret"):
            ERPConnectorService.sync_to_custom_erp(_doc(), "https://attacker.example.net/collect")
            self.assertNotIn("Authorization", req.call_args.kwargs["headers"])
            ERPConnectorService.sync_to_custom_erp(_doc(), "https://erp.example.com/invoices")
            self.assertEqual(req.call_args.kwargs["headers"]["Authorization"], "Bearer erp-secret")
            self.assertNotIn("raw_text", req.call_args.kwargs["json"])


class TestApiRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.client = self.app.test_client()
        document_repo._clear_db()

    def test_sync_latest_resolves_most_recent_document(self):
        saved = document_repo.save(_doc())
        with patch("backend.app.services.erp_service.safe_request", side_effect=requests.ConnectionError()):
            resp = self.client.post("/api/v1/documents/latest/sync-erp", json={"erp_type": "tally"}, headers=API_HEADERS)
        self.assertEqual(resp.status_code, 200, resp.get_json())
        self.assertEqual(document_repo.get_by_id(saved["id"])["erp_sync_status"], "XML Generated")

    def test_client_cannot_redirect_tally_to_other_host(self):
        document_repo.save(_doc())
        resp = self.client.post(
            "/api/v1/documents/latest/sync-erp",
            json={"erp_type": "tally", "tally_url": "http://169.254.169.254:9000"},
            headers=API_HEADERS,
        )
        self.assertEqual(resp.status_code, 400)

    def test_invalid_status_rejected_and_verify_works(self):
        saved = document_repo.save(_doc())
        bad = self.client.put(f"/api/v1/documents/{saved['id']}", json={"status": "Hacked"}, headers=API_HEADERS)
        self.assertEqual(bad.status_code, 400)
        ok = self.client.put(f"/api/v1/documents/{saved['id']}", json={"status": "Verified"}, headers=API_HEADERS)
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.get_json()["status"], "Verified")

    def test_system_status_requires_auth_and_hides_secrets(self):
        self.assertEqual(self.client.get("/api/v1/system/status").status_code, 401)
        with patch.object(settings, "openai_api_key", "sk-super-secret"), patch.object(settings, "ai_provider", "openai"):
            resp = self.client.get("/api/v1/system/status", headers=API_HEADERS)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("sk-super-secret", resp.get_data(as_text=True))
        self.assertEqual(resp.get_json()["ai"]["provider"], "openai")

    def test_health_is_public(self):
        resp = self.client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["database"])

    def test_security_headers_present(self):
        resp = self.client.get("/api/v1/health")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")

    def test_upload_without_ocr_or_ai_returns_actionable_503(self):
        png = io.BytesIO()
        from PIL import Image
        Image.new("RGB", (40, 40), "white").save(png, format="PNG")
        png.seek(0)
        with patch("backend.app.ocr.ocr_engine.ocr_manager") as manager, \
                patch.object(settings, "ai_provider", "none"), \
                patch.object(settings, "openai_api_key", None), \
                patch.object(settings, "openrouter_api_key", None):
            manager.paddle_provider = None
            manager.easy_provider = None
            resp = self.client.post(
                "/api/v1/upload", data={"file": (png, "invoice.png")},
                headers=API_HEADERS, content_type="multipart/form-data",
            )
        self.assertEqual(resp.status_code, 503)
        self.assertIn("OPENAI_API_KEY", resp.get_json()["error"])

    def test_upload_vision_fallback_when_ocr_missing(self):
        png = io.BytesIO()
        from PIL import Image
        Image.new("RGB", (40, 40), "white").save(png, format="PNG")
        png.seek(0)
        ai_payload = {
            "vendor": "Vision Vendor", "gstin": "", "invoice_number": f"V-{uuid.uuid4().hex[:6]}", "date": "2026-01-05",
            "due_date": "", "subtotal": "100", "cgst": "9", "sgst": "9", "igst": "", "tax_total": "18",
            "total": "118", "currency": "INR", "items": [],
        }
        completion = MagicMock(status_code=200, headers={})
        completion.json.return_value = {"choices": [{"message": {"content": json.dumps(ai_payload)}, "finish_reason": "stop"}]}
        with patch("backend.app.ocr.ocr_engine.ocr_manager") as manager, \
                patch.object(settings, "ai_provider", "openai"), \
                patch.object(settings, "openai_api_key", "sk-test"), \
                patch("backend.app.ai.providers.requests.post", return_value=completion) as post:
            manager.paddle_provider = None
            manager.easy_provider = None
            resp = self.client.post(
                "/api/v1/upload", data={"file": (png, "invoice.png")},
                headers=API_HEADERS, content_type="multipart/form-data",
            )
        self.assertEqual(resp.status_code, 200, resp.get_json())
        body = resp.get_json()
        self.assertEqual(body["extraction_method"], "ai-vision:openai")
        self.assertEqual(body["total"], "118.00")
        self.assertEqual(body["source"], "Manual Upload")
        sent = post.call_args.kwargs["json"]["messages"][1]["content"]
        self.assertTrue(any(part.get("type") == "image_url" for part in sent))


class TestPdfTextLayer(unittest.TestCase):
    def test_digital_pdf_text_used_without_ocr(self):
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 72), "ACME Supplies Pvt Ltd  Invoice No: INV-778  Grand Total 1,180.00")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()
        doc.save(tmp.name)
        doc.close()
        try:
            from backend.app.ocr.ocr_engine import extract_text
            with patch("backend.app.ocr.ocr_engine.extract_text_from_image", side_effect=AssertionError("OCR should not run")):
                result = extract_text(tmp.name)
            self.assertIn("INV-778", result.text)
            self.assertGreater(result.confidence, 0.9)
        finally:
            os.remove(tmp.name)


class TestWhatsAppCloudApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.client = self.app.test_client()

    def _post(self, payload):
        body = json.dumps(payload).encode()
        sig = hmac.new(settings.whatsapp_app_secret.encode(), body, hashlib.sha256).hexdigest()
        return self.client.post(
            "/api/v1/whatsapp/webhook", data=body,
            headers={"X-Hub-Signature-256": f"sha256={sig}", "Content-Type": "application/json"},
        )

    @staticmethod
    def _meta_payload(message):
        return {"object": "whatsapp_business_account",
                "entry": [{"changes": [{"value": {"messages": [message]} if message else {"statuses": [{"id": "x"}]}}]}]}

    def test_status_callbacks_acknowledged(self):
        resp = self._post(self._meta_payload(None))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "ignored")

    @patch("backend.app.services.document_service.DocumentService.process_document")
    @patch("backend.app.api.v1.whatsapp_routes.safe_request")
    def test_image_message_downloaded_via_graph_api(self, req, process):
        meta_resp = MagicMock()
        meta_resp.json.return_value = {"url": "https://lookaside.fbsbx.com/media/abc"}
        media_resp = MagicMock(content=b"\xff\xd8\xff\xe0" + b"jpegdata")
        req.side_effect = [meta_resp, media_resp]
        process.return_value = {"id": "d1", "vendor": "V", "status": "Pending Verification"}
        msg = {"id": f"wamid.{uuid.uuid4().hex}", "from": "919876543210", "type": "image", "image": {"id": "MEDIA123"}}
        with patch.object(settings, "whatsapp_access_token", "EAAG-test"), patch.object(settings, "whatsapp_send_replies", False):
            resp = self._post(self._meta_payload(msg))
        self.assertEqual(resp.status_code, 200, resp.get_json())
        self.assertEqual(resp.get_json()["status"], "success")
        self.assertIn("MEDIA123", req.call_args_list[0].args[1])
        self.assertEqual(process.call_args.kwargs["source"], "WhatsApp (919876543210)")

    def test_media_without_access_token_reports_configuration(self):
        msg = {"id": f"wamid.{uuid.uuid4().hex}", "from": "91999", "type": "image", "image": {"id": "M1"}}
        with patch.object(settings, "whatsapp_access_token", None):
            resp = self._post(self._meta_payload(msg))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("WHATSAPP_ACCESS_TOKEN", resp.get_json()["message"])

    @patch("backend.app.services.document_service.DocumentService.process_document")
    @patch("backend.app.api.v1.whatsapp_routes.safe_request")
    def test_transient_failure_allows_retry(self, req, process):
        msg = {"id": f"wamid.{uuid.uuid4().hex}", "from": "91999", "type": "image", "image": {"id": "M2"}}
        req.side_effect = requests.ConnectionError("graph down")
        with patch.object(settings, "whatsapp_access_token", "EAAG-test"):
            first = self._post(self._meta_payload(msg))
        self.assertEqual(first.status_code, 500)

        meta_resp = MagicMock()
        meta_resp.json.return_value = {"url": "https://lookaside.fbsbx.com/media/abc"}
        req.side_effect = [meta_resp, MagicMock(content=b"%PDF-1.7 test")]
        process.return_value = {"id": "d2", "status": "Pending Verification"}
        with patch.object(settings, "whatsapp_access_token", "EAAG-test"), patch.object(settings, "whatsapp_send_replies", False):
            retry = self._post(self._meta_payload(msg))
        self.assertEqual(retry.get_json()["status"], "success")


class TestConcurrentPersistence(unittest.TestCase):
    def test_parallel_saves_are_all_persisted(self):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        tmp.close()
        try:
            init_db(tmp.name)
            errors = []

            def worker(n):
                # A repository per thread simulates separate Gunicorn worker processes
                repo = DocumentRepository(db_path=tmp.name)
                try:
                    for i in range(10):
                        repo.save(_doc(id=f"t{n}-{i}"))
                except Exception as exc:  # pragma: no cover - surfaced below
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(n,)) for n in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            self.assertEqual(len(DocumentRepository(db_path=tmp.name).get_all()), 50)
        finally:
            for suffix in ("", "-wal", "-shm"):
                if os.path.exists(tmp.name + suffix):
                    os.remove(tmp.name + suffix)


if __name__ == "__main__":
    unittest.main()
