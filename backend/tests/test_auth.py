import json
import unittest
from unittest.mock import patch

from backend.app import create_app
from backend.app.auth import limiter
from backend.app.config.settings import Settings, settings


class TestAuthenticationAndCsrf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        # Create fresh, clean test client without default headers or cookies
        self.client = self.app.test_client()
        limiter.reset()

    def tearDown(self):
        limiter.reset()

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


class TestLoginRateLimiting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.client = self.app.test_client()
        limiter.reset()

    def tearDown(self):
        limiter.reset()

    def test_login_succeeds_below_limit(self):
        """
        Valid login attempts succeed without triggering rate limiting.
        """
        for _ in range(4):
            resp = self.client.post("/api/v1/auth/login", json={
                "username": settings.app_admin_username,
                "password": settings.app_admin_password
            })
            self.assertEqual(resp.status_code, 200)

    def test_repeated_failed_logins_trigger_429(self):
        """
        Five failed attempts are permitted; the sixth consecutive failure triggers HTTP 429 Too Many Requests.
        """
        for i in range(5):
            resp = self.client.post("/api/v1/auth/login", json={
                "username": settings.app_admin_username,
                "password": "wrong_password"
            })
            self.assertEqual(resp.status_code, 401, f"Attempt {i+1} should return 401")

        # 6th attempt exceeds limit
        resp_blocked = self.client.post("/api/v1/auth/login", json={
            "username": settings.app_admin_username,
            "password": "wrong_password"
        })
        self.assertEqual(resp_blocked.status_code, 429)
        data = resp_blocked.get_json()
        self.assertIn("Too many failed login attempts", data.get("error", ""))
        self.assertIn("Retry-After", resp_blocked.headers)
        self.assertIn("X-RateLimit-Limit", resp_blocked.headers)

    def test_rate_limit_shared_across_both_login_aliases(self):
        """
        Both /api/v1/auth/login and /auth/login share the same counter bucket so attackers
        cannot bypass rate limiting by switching endpoint aliases.
        """
        # Alternate 5 failed attempts across both endpoints
        self.assertEqual(self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "bad"}).status_code, 401)
        self.assertEqual(self.client.post("/auth/login", json={"username": "admin", "password": "bad"}).status_code, 401)
        self.assertEqual(self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "bad"}).status_code, 401)
        self.assertEqual(self.client.post("/auth/login", json={"username": "admin", "password": "bad"}).status_code, 401)
        self.assertEqual(self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "bad"}).status_code, 401)

        # 6th attempt on /auth/login must be blocked
        blocked_root = self.client.post("/auth/login", json={"username": "admin", "password": "bad"})
        self.assertEqual(blocked_root.status_code, 429)

        # 7th attempt on /api/v1/auth/login must also be blocked
        blocked_v1 = self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "bad"})
        self.assertEqual(blocked_v1.status_code, 429)

    def test_separate_client_ips_have_independent_limits(self):
        """
        Different client IP identities have separate independent rate limiting buckets.
        """
        # Fail 5 times from IP 192.168.1.50
        for _ in range(5):
            r = self.client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "bad"},
                environ_base={"REMOTE_ADDR": "192.168.1.50"}
            )
            self.assertEqual(r.status_code, 401)

        # 192.168.1.50 is now blocked
        blocked = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "bad"},
            environ_base={"REMOTE_ADDR": "192.168.1.50"}
        )
        self.assertEqual(blocked.status_code, 429)

        # Separate client IP 192.168.1.51 is NOT blocked and can authenticate successfully
        allowed = self.client.post(
            "/api/v1/auth/login",
            json={"username": settings.app_admin_username, "password": settings.app_admin_password},
            environ_base={"REMOTE_ADDR": "192.168.1.51"}
        )
        self.assertEqual(allowed.status_code, 200)

    def test_rate_limit_expires_with_clock(self):
        """
        Rate limit bucket expires and resets after configured time window using controllable clock.
        """
        base_time = 1700000000.0

        with patch("time.time", side_effect=lambda: base_time):
            for _ in range(5):
                self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "bad"})
            self.assertEqual(self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "bad"}).status_code, 429)

        # Advance controllable clock by 301 seconds (5 minutes + 1 second)
        with patch("time.time", side_effect=lambda: base_time + 301.0):
            resp_after = self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "bad"})
            self.assertEqual(resp_after.status_code, 401)

    def test_malformed_login_payloads_handled_safely(self):
        """
        Malformed JSON or non-dict payloads return 400 and are safely handled by rate limiting.
        """
        resp_text = self.client.post("/api/v1/auth/login", data="not json", content_type="text/plain")
        self.assertEqual(resp_text.status_code, 400)

        resp_list = self.client.post("/api/v1/auth/login", json=["invalid", "array"])
        self.assertEqual(resp_list.status_code, 400)

        resp_empty = self.client.post("/api/v1/auth/login", json={})
        self.assertEqual(resp_empty.status_code, 400)

    def test_production_storage_warning_for_in_memory_backend(self):
        """
        validate_production_config logs a high-visibility warning when in-memory rate limiting is used in production.
        """
        test_settings = Settings()
        test_settings.flask_env = "production"
        test_settings.secret_key = "a" * 32
        test_settings.app_admin_username = "prodadmin"
        test_settings.app_admin_password = "strongpassword123!"
        test_settings.whatsapp_app_secret = "b" * 32
        test_settings.whatsapp_verify_token = "c" * 32
        test_settings.rate_limit_storage_uri = "memory://"

        with self.assertLogs("backend.app.config.settings", level="WARNING") as cm:
            test_settings.validate_production_config()
            self.assertTrue(any("RATE_LIMIT_STORAGE_URI" in line and "in-memory" in line.lower() for line in cm.output))


class TestAuthenticationLogSanitization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.client = self.app.test_client()
        limiter.reset()

    def tearDown(self):
        limiter.reset()

    def test_crlf_injection_in_username_escaped_and_sanitized(self):
        """
        Usernames containing CRLF characters (\\r\\n) are escaped and cannot forge multiple log lines.
        """
        malicious_username = "admin\r\n2026-10-19 03:00:00 - Fake Log Injection"
        with self.assertLogs("backend.app.auth.auth_routes", level="WARNING") as cm:
            resp = self.client.post("/api/v1/auth/login", json={
                "username": malicious_username,
                "password": "wrongpassword"
            })
            self.assertEqual(resp.status_code, 401)
            for line in cm.output:
                self.assertNotIn("\r", line)
                self.assertNotIn("\n", line)
                self.assertIn("admin\\r\\n2026-10-19", line)

    def test_embedded_newlines_and_tabs_escaped(self):
        """
        Tabs and embedded newlines are safely escaped.
        """
        tab_user = "user\twith\nembedded\rnewlines"
        with self.assertLogs("backend.app.auth.auth_routes", level="WARNING") as cm:
            resp = self.client.post("/api/v1/auth/login", json={
                "username": tab_user,
                "password": "wrongpassword"
            })
            self.assertEqual(resp.status_code, 401)
            for line in cm.output:
                self.assertNotIn("\t", line)
                self.assertNotIn("\n", line)
                self.assertNotIn("\r", line)
                self.assertIn("user\\twith\\nembedded\\rnewlines", line)

    def test_control_characters_escaped(self):
        """
        Null bytes and unprintable control characters are hex-escaped.
        """
        ctrl_user = "user\x00\x08\x1btest"
        with self.assertLogs("backend.app.auth.auth_routes", level="WARNING") as cm:
            resp = self.client.post("/api/v1/auth/login", json={
                "username": ctrl_user,
                "password": "wrongpassword"
            })
            self.assertEqual(resp.status_code, 401)
            for line in cm.output:
                self.assertIn("user\\x00\\x08\\x1btest", line)

    def test_extremely_long_username_truncated(self):
        """
        Extremely long username strings are truncated to prevent log flooding / resource exhaustion.
        """
        huge_user = "A" * 5000
        with self.assertLogs("backend.app.auth.auth_routes", level="WARNING") as cm:
            resp = self.client.post("/api/v1/auth/login", json={
                "username": huge_user,
                "password": "wrongpassword"
            })
            self.assertEqual(resp.status_code, 401)
            for line in cm.output:
                self.assertIn("...[truncated]", line)
                self.assertNotIn("A" * 100, line)

    def test_credentials_and_secrets_never_logged(self):
        """
        Passwords, CSRF tokens, and secret keys are never written to auth logs.
        """
        secret_password = "super_secret_password_do_not_log_123"
        with self.assertLogs("backend.app.auth.auth_routes", level="INFO") as cm:
            # Failed attempt
            self.client.post("/api/v1/auth/login", json={
                "username": "testuser",
                "password": secret_password
            })
            # Successful attempt
            self.client.post("/api/v1/auth/login", json={
                "username": settings.app_admin_username,
                "password": settings.app_admin_password
            })
            for line in cm.output:
                self.assertNotIn(secret_password, line)
                self.assertNotIn(settings.app_admin_password, line)
                self.assertNotIn(settings.api_secret_key, line)
