import json
import unittest
from unittest.mock import patch

from backend.app import create_app
from backend.app.config.settings import Settings, settings


class TestAuthenticationAndCsrf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        # Create fresh, clean test client without default headers or cookies
        self.client = self.app.test_client()

    def test_unauthenticated_access_rejected_on_protected_endpoints(self):
        """
        All sensitive endpoints must reject unauthenticated requests with HTTP 401.
        """
        protected_endpoints = [
            ("GET", "/api/v1/documents"),
            ("GET", "/documents"),
            ("GET", "/api/v1/documents/doc-123"),
            ("GET", "/documents/doc-123"),
            ("PUT", "/api/v1/documents/doc-123"),
            ("PUT", "/documents/doc-123"),
            ("DELETE", "/api/v1/documents/doc-123"),
            ("DELETE", "/documents/doc-123"),
            ("GET", "/api/v1/analytics"),
            ("GET", "/analytics"),
            ("POST", "/api/v1/upload"),
            ("POST", "/upload"),
            ("GET", "/api/v1/download"),
            ("GET", "/download"),
            ("POST", "/api/v1/documents/doc-123/sync-erp"),
            ("POST", "/api/v1/whatsapp/simulate"),
        ]

        for method, endpoint in protected_endpoints:
            with self.subTest(method=method, endpoint=endpoint):
                if method == "GET":
                    resp = self.client.get(endpoint)
                elif method == "POST":
                    resp = self.client.post(endpoint, json={})
                elif method == "PUT":
                    resp = self.client.put(endpoint, json={})
                elif method == "DELETE":
                    resp = self.client.delete(endpoint)
                else:
                    self.fail(f"Unhandled method {method}")

                self.assertEqual(resp.status_code, 401, f"{method} {endpoint} should return 401")
                data = resp.get_json()
                self.assertIsNotNone(data)
                self.assertIn("Authentication required", data.get("error", ""))

    def test_public_endpoints_accessible_without_auth(self):
        """
        Public endpoints must remain accessible without authentication.
        """
        public_endpoints = [
            ("/health", 200),
            ("/api/v1/health", 200),
            ("/", 200),
            ("/api/v1/", 200),
            ("/favicon.ico", 204),
            ("/api/v1/auth/session", 200),
        ]

        for endpoint, expected_code in public_endpoints:
            with self.subTest(endpoint=endpoint):
                resp = self.client.get(endpoint, follow_redirects=True)
                self.assertEqual(resp.status_code, expected_code, f"{endpoint} should return {expected_code}")

    def test_login_success_and_cookie_attributes(self):
        """
        Login with correct credentials returns 200, user, csrf_token, and sets secure cookie attributes.
        """
        payload = {
            "username": settings.app_admin_username,
            "password": settings.app_admin_password
        }
        resp = self.client.post("/api/v1/auth/login", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("status"), "authenticated")
        self.assertEqual(data.get("user"), settings.app_admin_username)
        self.assertTrue(len(data.get("csrf_token", "")) >= 32)

        # Inspect Set-Cookie header for security attributes
        cookie_header = resp.headers.get("Set-Cookie", "")
        self.assertIn("session=", cookie_header)
        self.assertIn("HttpOnly", cookie_header)
        self.assertIn("SameSite=Lax", cookie_header)

    def test_login_invalid_credentials_rejected(self):
        """
        Login with incorrect password or username returns 401 without leaking details.
        """
        # Wrong password
        resp = self.client.post("/api/v1/auth/login", json={
            "username": settings.app_admin_username,
            "password": "wrong-password-123"
        })
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Invalid username or password", resp.get_json().get("error", ""))

        # Wrong username
        resp2 = self.client.post("/api/v1/auth/login", json={
            "username": "unknown_user",
            "password": settings.app_admin_password
        })
        self.assertEqual(resp2.status_code, 401)
        self.assertIn("Invalid username or password", resp2.get_json().get("error", ""))

        # Empty fields
        resp3 = self.client.post("/api/v1/auth/login", json={"username": "", "password": ""})
        self.assertEqual(resp3.status_code, 400)

        # Invalid body
        resp4 = self.client.post("/api/v1/auth/login", data="plain text")
        self.assertEqual(resp4.status_code, 400)

    def test_session_lifecycle_and_csrf_protection(self):
        """
        Full session lifecycle: login -> authenticated GET -> CSRF rejection on state-change ->
        successful state-change with CSRF token -> logout -> session invalidated.
        """
        # 1. Check session before login
        sess_resp = self.client.get("/api/v1/auth/session")
        self.assertEqual(sess_resp.status_code, 200)
        self.assertFalse(sess_resp.get_json().get("authenticated"))

        # 2. Login
        login_resp = self.client.post("/api/v1/auth/login", json={
            "username": settings.app_admin_username,
            "password": settings.app_admin_password
        })
        self.assertEqual(login_resp.status_code, 200)
        csrf_token = login_resp.get_json().get("csrf_token")

        # 3. Authenticated GET (does not require CSRF token)
        docs_resp = self.client.get("/api/v1/documents")
        self.assertEqual(docs_resp.status_code, 200)

        # 4. State-changing request WITHOUT CSRF token must fail with 403 Forbidden
        put_no_csrf = self.client.put("/api/v1/documents/test-doc", json={"vendor": "New"})
        self.assertEqual(put_no_csrf.status_code, 403)
        self.assertIn("CSRF validation failed", put_no_csrf.get_json().get("error", ""))

        # 5. State-changing request with INVALID CSRF token must fail with 403 Forbidden
        put_bad_csrf = self.client.put(
            "/api/v1/documents/test-doc",
            json={"vendor": "New"},
            headers={"X-CSRF-Token": "invalid_csrf_token_12345"}
        )
        self.assertEqual(put_bad_csrf.status_code, 403)
        self.assertIn("CSRF validation failed", put_bad_csrf.get_json().get("error", ""))

        # 6. State-changing request with VALID CSRF token passes CSRF validation
        # (Returns 404 because document test-doc does not exist in DB, confirming CSRF check passed)
        put_valid_csrf = self.client.put(
            "/api/v1/documents/test-doc",
            json={"vendor": "New"},
            headers={"X-CSRF-Token": csrf_token}
        )
        self.assertEqual(put_valid_csrf.status_code, 404)
        self.assertIn("Document not found", put_valid_csrf.get_json().get("error", ""))

        # 7. Logout
        logout_resp = self.client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf_token}
        )
        self.assertEqual(logout_resp.status_code, 200)
        self.assertEqual(logout_resp.get_json().get("status"), "logged_out")

        # 8. Subsequent requests after logout must return 401
        after_logout_resp = self.client.get("/api/v1/documents")
        self.assertEqual(after_logout_resp.status_code, 401)

        # 9. Session check confirms unauthenticated
        check_resp = self.client.get("/api/v1/auth/session")
        self.assertFalse(check_resp.get_json().get("authenticated"))

    def test_api_key_authentication(self):
        """
        Machine-to-machine requests with X-API-Key or Authorization Bearer header succeed without cookie session.
        """
        # Valid X-API-Key
        resp_key = self.client.get("/api/v1/documents", headers={"X-API-Key": settings.api_secret_key})
        self.assertEqual(resp_key.status_code, 200)

        # Valid Bearer Authorization
        resp_bearer = self.client.get(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {settings.api_secret_key}"}
        )
        self.assertEqual(resp_bearer.status_code, 200)

        # Invalid API Key
        resp_bad = self.client.get("/api/v1/documents", headers={"X-API-Key": "wrong_key_12345"})
        self.assertEqual(resp_bad.status_code, 401)

    def test_production_fails_safely_when_mandatory_secrets_missing(self):
        """
        Production mode must raise RuntimeError upon startup if critical security secrets are missing or weak.
        """
        test_settings = Settings()
        test_settings.flask_env = "production"
        test_settings.secret_key = ""
        test_settings.app_admin_password = ""
        test_settings.whatsapp_app_secret = ""

        with self.assertRaises(RuntimeError) as ctx:
            test_settings.validate_production_config()

        err_msg = str(ctx.exception)
        self.assertIn("SECRET_KEY must be set", err_msg)
        self.assertIn("APP_ADMIN_PASSWORD", err_msg)
        self.assertIn("WHATSAPP_APP_SECRET", err_msg)
