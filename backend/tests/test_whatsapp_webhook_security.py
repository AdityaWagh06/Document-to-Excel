import hashlib
import hmac
import json
import unittest
from unittest.mock import patch, MagicMock

from backend.app import create_app
from backend.app.config.settings import settings


class TestWhatsAppWebhookSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.client = self.app.test_client()
        self.secret = settings.whatsapp_app_secret

    def _sign_payload(self, body_bytes: bytes, secret: str = None) -> str:
        s = secret if secret is not None else self.secret
        sig = hmac.new(s.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
        return f"sha256={sig}"

    @patch("backend.app.services.document_service.DocumentService.process_document")
    def test_valid_signature_accepted(self, mock_process):
        """
        Valid HMAC-SHA256 signature passes signature check.
        """
        payload = {"from": "+919876543210"}  # No media URL -> returns 400 for missing media, but NOT 401 signature error
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Hub-Signature-256": self._sign_payload(body),
            "Content-Type": "application/json"
        }

        resp = self.client.post("/api/v1/whatsapp/webhook", data=body, headers=headers)
        # Signature passed -> reaches payload validation -> 400 missing media
        self.assertEqual(resp.status_code, 400)
        self.assertIn("No media image URL provided", resp.get_json().get("message", ""))
        mock_process.assert_not_called()

    @patch("backend.app.services.document_service.DocumentService.process_document")
    def test_missing_signature_header_rejected(self, mock_process):
        """
        Missing X-Hub-Signature-256 header must return 401 without processing.
        """
        payload = {"media_url": "https://example.com/invoice.png", "from": "+919876543210"}
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        resp = self.client.post("/api/v1/whatsapp/webhook", data=body, headers=headers)
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Missing X-Hub-Signature-256", resp.get_json().get("error", ""))
        mock_process.assert_not_called()

    @patch("backend.app.services.document_service.DocumentService.process_document")
    def test_incorrect_signature_rejected(self, mock_process):
        """
        Incorrect signature hash must return 401.
        """
        payload = {"media_url": "https://example.com/invoice.png", "from": "+919876543210"}
        body = json.dumps(payload).encode("utf-8")
        fake_sig = "sha256=" + "a" * 64
        headers = {
            "X-Hub-Signature-256": fake_sig,
            "Content-Type": "application/json"
        }

        resp = self.client.post("/api/v1/whatsapp/webhook", data=body, headers=headers)
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Invalid signature", resp.get_json().get("error", ""))
        mock_process.assert_not_called()

    @patch("backend.app.services.document_service.DocumentService.process_document")
    def test_malformed_signature_prefix_rejected(self, mock_process):
        """
        Signature missing 'sha256=' prefix must return 401.
        """
        payload = {"media_url": "https://example.com/invoice.png"}
        body = json.dumps(payload).encode("utf-8")
        raw_hash = hmac.new(self.secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        headers = {
            "X-Hub-Signature-256": raw_hash,  # Missing sha256= prefix
            "Content-Type": "application/json"
        }

        resp = self.client.post("/api/v1/whatsapp/webhook", data=body, headers=headers)
        self.assertEqual(resp.status_code, 401)
        self.assertIn("missing 'sha256=' prefix", resp.get_json().get("error", ""))
        mock_process.assert_not_called()

    @patch("backend.app.services.document_service.DocumentService.process_document")
    def test_malformed_signature_non_hex_rejected(self, mock_process):
        """
        Signature containing non-hex characters must return 401.
        """
        body = b'{"test": 1}'
        headers = {
            "X-Hub-Signature-256": "sha256=" + "z" * 64,  # 'z' is not hex
            "Content-Type": "application/json"
        }
        resp = self.client.post("/api/v1/whatsapp/webhook", data=body, headers=headers)
        self.assertEqual(resp.status_code, 401)
        self.assertIn("non-hexadecimal", resp.get_json().get("error", ""))
        mock_process.assert_not_called()

    @patch("backend.app.services.document_service.DocumentService.process_document")
    def test_malformed_signature_short_length_rejected(self, mock_process):
        """
        Signature shorter than 64 hex characters must return 401.
        """
        body = b'{"test": 1}'
        headers = {
            "X-Hub-Signature-256": "sha256=abcdef123456",
            "Content-Type": "application/json"
        }
        resp = self.client.post("/api/v1/whatsapp/webhook", data=body, headers=headers)
        self.assertEqual(resp.status_code, 401)
        self.assertIn("invalid SHA-256 hash length", resp.get_json().get("error", ""))
        mock_process.assert_not_called()

    @patch("backend.app.services.document_service.DocumentService.process_document")
    def test_tampered_payload_rejected(self, mock_process):
        """
        Modifying even 1 byte of the payload after signature computation must return 401.
        """
        original_body = b'{"media_url": "https://example.com/invoice.png"}'
        sig = self._sign_payload(original_body)

        tampered_body = b'{"media_url": "https://example.com/malicious.png"}'
        headers = {
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json"
        }

        resp = self.client.post("/api/v1/whatsapp/webhook", data=tampered_body, headers=headers)
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Invalid signature", resp.get_json().get("error", ""))
        mock_process.assert_not_called()

    @patch("backend.app.services.document_service.DocumentService.process_document")
    def test_missing_app_secret_fails_safely(self, mock_process):
        """
        When server has no WHATSAPP_APP_SECRET configured, requests fail safely with 401.
        """
        body = b'{"test": 1}'
        headers = {
            "X-Hub-Signature-256": "sha256=" + "a" * 64,
            "Content-Type": "application/json"
        }

        with patch.object(settings, "whatsapp_app_secret", ""):
            resp = self.client.post("/api/v1/whatsapp/webhook", data=body, headers=headers)
            self.assertEqual(resp.status_code, 401)
            self.assertIn("not configured", resp.get_json().get("error", ""))
            mock_process.assert_not_called()

    def test_get_webhook_challenge_valid(self):
        """
        GET challenge returns the hub.challenge when token matches.
        """
        resp = self.client.get(
            f"/api/v1/whatsapp/webhook?hub.mode=subscribe&hub.verify_token={settings.whatsapp_verify_token}&hub.challenge=test_chall_456"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_data(as_text=True), "test_chall_456")

    def test_get_webhook_challenge_invalid_token_returns_403(self):
        """
        GET challenge returns 403 Forbidden when token does not match.
        """
        resp = self.client.get(
            "/api/v1/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=totally_wrong_token&hub.challenge=test_chall_456"
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Forbidden", resp.get_json().get("error", ""))

    def test_get_webhook_missing_server_token_fails_safely(self):
        """
        When WHATSAPP_VERIFY_TOKEN is missing on server, GET returns 500 fail-safe.
        """
        with patch.object(settings, "whatsapp_verify_token", ""):
            resp = self.client.get(
                "/api/v1/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=any&hub.challenge=test"
            )
            self.assertEqual(resp.status_code, 500)
            self.assertIn("not configured", resp.get_json().get("error", ""))
