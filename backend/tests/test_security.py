import hashlib
import hmac
import io
import json
import os
import re
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure backend root is in sys.path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app import create_app
from backend.app.config.settings import settings
from backend.app.utils.url_validator import validate_url, safe_request, is_disallowed_ip


class TestUrlValidation(unittest.TestCase):
    """
    Tests for defensive outbound URL validation and SSRF mitigations.
    """

    def test_loopback_ipv4_rejected(self):
        valid, msg = validate_url("http://127.0.0.1/")
        self.assertFalse(valid)
        self.assertIn("Insecure scheme", msg)

        # Even with https, 127.0.0.1 must be rejected
        valid, msg = validate_url("https://127.0.0.1/")
        self.assertFalse(valid)
        self.assertIn("disallowed range", msg)

    def test_localhost_rejected(self):
        valid, msg = validate_url("http://localhost/")
        self.assertFalse(valid)
        self.assertIn("Insecure scheme", msg)

        valid, msg = validate_url("https://localhost/")
        self.assertFalse(valid)
        self.assertIn("Host 'localhost' resolves to disallowed IP", msg)

    def test_private_ip_10_rejected(self):
        valid, msg = validate_url("http://10.0.0.1/")
        self.assertFalse(valid)

        valid, msg = validate_url("https://10.0.0.1/")
        self.assertFalse(valid)
        self.assertIn("disallowed range", msg)

    def test_private_ip_192_168_rejected(self):
        valid, msg = validate_url("http://192.168.1.1/")
        self.assertFalse(valid)

        valid, msg = validate_url("https://192.168.1.1/")
        self.assertFalse(valid)
        self.assertIn("disallowed range", msg)

    def test_cloud_metadata_ip_rejected(self):
        valid, msg = validate_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(valid)
        self.assertTrue("metadata" in msg.lower() or "insecure" in msg.lower())

        valid, msg = validate_url("https://169.254.169.254/latest/meta-data/")
        self.assertFalse(valid)
        self.assertIn("metadata", msg.lower())

    def test_ipv6_loopback_rejected(self):
        valid, msg = validate_url("http://[::1]/")
        self.assertFalse(valid)

        valid, msg = validate_url("https://[::1]/")
        self.assertFalse(valid)
        self.assertIn("disallowed range", msg)

    def test_public_ip_https_accepted(self):
        # 93.184.216.34 is example.com public IP
        valid, msg = validate_url("https://93.184.216.34/")
        self.assertTrue(valid, msg)

    @patch("socket.getaddrinfo")
    def test_public_domain_https_accepted(self, mock_getaddrinfo):
        # Mock DNS resolution to public IP 93.184.216.34
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ]
        valid, msg = validate_url("https://api.custom-erp.com/v1/invoices")
        self.assertTrue(valid, msg)

    @patch("socket.getaddrinfo")
    def test_dns_resolving_to_private_ip_rejected(self, mock_getaddrinfo):
        # Mock DNS rebinding / internal domain resolving to 10.0.0.1
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))
        ]
        valid, msg = validate_url("https://attacker-domain.internal/webhook")
        self.assertFalse(valid)
        self.assertIn("resolves to disallowed IP", msg)

    def test_malformed_url_rejected(self):
        for bad_url in ["http://", "not_a_url", "://foo", "https://"]:
            valid, msg = validate_url(bad_url)
            self.assertFalse(valid, f"Expected failure for '{bad_url}'")

    def test_embedded_credentials_rejected(self):
        valid, msg = validate_url("https://admin:password123@example.com/api")
        self.assertFalse(valid)
        self.assertIn("embedded credentials", msg)

    def test_unsupported_schemes_rejected(self):
        for scheme_url in ["ftp://example.com/file", "file:///etc/passwd", "gopher://example.com"]:
            valid, msg = validate_url(scheme_url)
            self.assertFalse(valid, f"Expected failure for '{scheme_url}'")

    def test_permitted_local_tally_accepted(self):
        permitted = "http://localhost:9000"
        valid, msg = validate_url(
            "http://localhost:9000",
            allow_local_tally=True,
            permitted_tally_url=permitted
        )
        self.assertTrue(valid, msg)

    def test_disallowed_tally_rejected(self):
        permitted = "http://localhost:9000"
        # Disallowed port
        valid, msg = validate_url(
            "http://localhost:22",
            allow_local_tally=True,
            permitted_tally_url=permitted
        )
        self.assertFalse(valid)

        # Disallowed remote host attempting Tally scheme
        valid, msg = validate_url(
            "http://192.168.1.100:9000",
            allow_local_tally=True,
            permitted_tally_url=permitted
        )
        self.assertFalse(valid)

    @patch("backend.app.utils.url_validator.requests.request")
    @patch("socket.getaddrinfo")
    def test_safe_request_blocks_redirect_to_private_ip(self, mock_getaddrinfo, mock_req):
        # Mock initial URL resolution as public
        mock_getaddrinfo.side_effect = [
            [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
            [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
        ]

        # Initial request redirects to loopback
        redirect_resp = MagicMock()
        redirect_resp.is_redirect = True
        redirect_resp.status_code = 302
        redirect_resp.headers = {"Location": "http://127.0.0.1/admin"}
        mock_req.return_value = redirect_resp

        with self.assertRaises(ValueError) as ctx:
            safe_request("GET", "https://example.com/redirect")
        self.assertIn("Disallowed or invalid URL", str(ctx.exception))


class TestUploadSecurity(unittest.TestCase):
    """
    Tests for upload file size, extension whitelist, and magic byte validation.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        cls.client.environ_base["HTTP_X_API_KEY"] = settings.api_secret_key

    def test_empty_upload_rejected(self):
        resp = self.client.post("/api/v1/upload", data={})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("No file provided", resp.get_json().get("error", ""))

    def test_missing_filename_rejected(self):
        data = {"image": (io.BytesIO(b""), "")}
        resp = self.client.post("/api/v1/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Empty upload or missing filename", resp.get_json().get("error", ""))

    def test_disallowed_extension_exe_rejected(self):
        data = {"image": (io.BytesIO(b"MZ\x90\x00"), "malware.exe")}
        resp = self.client.post("/api/v1/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("File type '.exe' is not permitted", resp.get_json().get("error", ""))

    def test_disallowed_extension_sh_rejected(self):
        data = {"image": (io.BytesIO(b"#!/bin/bash\nrm -rf /"), "script.sh")}
        resp = self.client.post("/api/v1/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("File type '.sh' is not permitted", resp.get_json().get("error", ""))

    def test_spoofed_mime_type_with_text_content_rejected(self):
        # File named .png but containing plain script text
        fake_png = b"echo 'hack' > /dev/null\n"
        data = {"image": (io.BytesIO(fake_png), "invoice.png")}
        resp = self.client.post("/api/v1/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Malformed file content or extension mismatch", resp.get_json().get("error", ""))

    def test_malformed_image_content_rejected(self):
        # File named .jpg but containing random invalid bytes
        bad_jpg = b"RandomTextBytesNotAJPEG"
        data = {"image": (io.BytesIO(bad_jpg), "invoice.jpg")}
        resp = self.client.post("/api/v1/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Malformed file content or extension mismatch", resp.get_json().get("error", ""))

    @patch("backend.app.services.document_service.DocumentService.process_document")
    def test_valid_png_magic_accepted(self, mock_process):
        mock_process.return_value = {
            "id": "test-uuid",
            "vendor": "Test Corp",
            "total": "100.00",
            "status": "Pending Verification"
        }
        # Valid PNG header (8 bytes) + IHDR chunk
        valid_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        data = {"image": (io.BytesIO(valid_png), "valid_invoice.png")}
        resp = self.client.post("/api/v1/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json().get("vendor"), "Test Corp")

    def test_upload_exceeding_16mib_returns_413(self):
        # Generate 17 MiB stream
        oversized_data = b"0" * (17 * 1024 * 1024)
        data = {"image": (io.BytesIO(oversized_data), "huge_invoice.png")}
        resp = self.client.post("/api/v1/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 413)
        self.assertIn("16 MiB maximum upload limit", resp.get_json().get("error", ""))


class TestCorsSecurity(unittest.TestCase):
    """
    Tests for configurable CORS origin restrictions.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_trusted_origin_permitted(self):
        resp = self.client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "http://localhost:5173")

    def test_untrusted_origin_denied(self):
        resp = self.client.get("/api/v1/health", headers={"Origin": "https://malicious-website.com"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotEqual(resp.headers.get("Access-Control-Allow-Origin"), "https://malicious-website.com")


class TestEndpointSsrfProtection(unittest.TestCase):
    """
    Tests ensuring REST endpoints block SSRF payloads.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        cls.client.environ_base["HTTP_X_API_KEY"] = settings.api_secret_key

    @patch("backend.app.services.document_service.DocumentService.get_document_by_id")
    def test_sync_erp_blocks_cloud_metadata_ssrf(self, mock_get_doc):
        mock_get_doc.return_value = {"id": "doc-123", "vendor": "ACME", "total": "500.00"}
        payload = {
            "erp_type": "custom",
            "custom_endpoint": "http://169.254.169.254/latest/meta-data/"
        }
        resp = self.client.post("/api/v1/documents/doc-123/sync-erp", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Disallowed or invalid ERP endpoint", resp.get_json().get("message", ""))

    def test_whatsapp_webhook_blocks_private_ip_ssrf(self):
        payload = {
            "image_url": "http://127.0.0.1:8080/secret.png",
            "from": "+919999999999"
        }
        raw_body = json.dumps(payload).encode("utf-8")
        sig = hmac.new(
            settings.whatsapp_app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        headers = {
            "X-Hub-Signature-256": f"sha256={sig}",
            "Content-Type": "application/json"
        }
        resp = self.client.post("/api/v1/whatsapp/webhook", data=raw_body, headers=headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Disallowed media URL", resp.get_json().get("error", ""))

    def test_whatsapp_verify_token_valid(self):
        resp = self.client.get(
            f"/api/v1/whatsapp/webhook?hub.mode=subscribe&hub.verify_token={settings.whatsapp_verify_token}&hub.challenge=test_chall_123"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_data(as_text=True), "test_chall_123")

    def test_whatsapp_verify_token_invalid_returns_403(self):
        resp = self.client.get(
            "/api/v1/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=WRONG_TOKEN&hub.challenge=test_chall_123"
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Forbidden", resp.get_json().get("error", ""))


class TestSecretScrubbing(unittest.TestCase):
    """
    Tests ensuring no hardcoded API keys exist in test scripts.
    """

    def test_no_hardcoded_keys_in_test_free_models(self):
        script_path = ROOT_DIR / "backend" / "app" / "test_free_models.py"
        self.assertTrue(script_path.exists())
        content = script_path.read_text(encoding="utf-8")
        matches = re.findall(r"sk-[a-zA-Z0-9_\-]{20,}", content)
        self.assertEqual(len(matches), 0, "Found hardcoded API key in test_free_models.py!")


if __name__ == "__main__":
    unittest.main()
