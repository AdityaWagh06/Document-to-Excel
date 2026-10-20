import hmac
import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app import create_app
from backend.app.config.settings import settings
from backend.app.db.connection import init_db, get_db
from backend.app.db.session_repository import SessionRepository
from backend.app.db.webhook_repository import WebhookEventRepository
from backend.app.db.migrate_json_to_sqlite import migrate_json_to_sqlite
from backend.app.repository.document_repository import DocumentRepository
from backend.app.exports.excel_exporter import export_document_to_excel_bytes
from backend.app.exports.csv_exporter import export_document_to_csv_string
from backend.app.exports.doc_exporter import export_document_to_doc_summary
from backend.app.exports.tally_exporter import export_document_to_tally_xml


class TestSQLiteCRUDAndRestart(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        init_db(self.temp_db_path)
        self.repo = DocumentRepository(db_path=self.temp_db_path)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_crud_lifecycle_and_persistence_across_restarts(self):
        # 1. Create / Insert
        doc_payload = {
            "id": "inv-sqlite-001",
            "vendor": "Alpha Tech Solutions",
            "gstin": "27AABCU9603R1ZM",
            "invoice_number": "INV-2026-SQLITE",
            "date": "2026-05-01",
            "due_date": "2026-05-15",
            "subtotal": "5000.00",
            "cgst": "450.00",
            "sgst": "450.00",
            "igst": "0.00",
            "tax_total": "900.00",
            "total": "5900.00",
            "items": [
                {
                    "description": "Cloud Hosting Service",
                    "hsn_sac": "998315",
                    "qty": "1",
                    "unit_price": "5000.00",
                    "tax_rate": "18%",
                    "tax_amount": "900.00",
                    "amount": "5000.00",
                }
            ],
            "confidence": 0.98,
            "status": "Pending Verification",
        }
        saved = self.repo.save(doc_payload)
        self.assertEqual(saved["id"], "inv-sqlite-001")
        self.assertEqual(saved["vendor"], "Alpha Tech Solutions")

        # 2. Read
        fetched = self.repo.get_by_id("inv-sqlite-001")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["invoice_number"], "INV-2026-SQLITE")
        self.assertEqual(len(fetched["items"]), 1)
        self.assertEqual(fetched["items"][0]["description"], "Cloud Hosting Service")

        # 3. Update
        self.repo.update("inv-sqlite-001", {
            "vendor": "Alpha Tech Enterprises",
            "total": "6000.00",
            "status": "Verified",
        })
        updated = self.repo.get_by_id("inv-sqlite-001")
        self.assertEqual(updated["vendor"], "Alpha Tech Enterprises")
        self.assertEqual(updated["total"], "6000.00")
        self.assertEqual(updated["status"], "Verified")

        # 4. Simulate Application Restart (Instantiate brand new repository instance pointing to same file)
        restarted_repo = DocumentRepository(db_path=self.temp_db_path)
        all_docs = restarted_repo.get_all()
        self.assertEqual(len(all_docs), 1)
        restarted_doc = restarted_repo.get_by_id("inv-sqlite-001")
        self.assertIsNotNone(restarted_doc)
        self.assertEqual(restarted_doc["vendor"], "Alpha Tech Enterprises")
        self.assertEqual(restarted_doc["total"], "6000.00")
        self.assertEqual(restarted_doc["status"], "Verified")
        self.assertEqual(len(restarted_doc["items"]), 1)
        self.assertEqual(restarted_doc["items"][0]["tax_amount"], "900.00")

        # 5. Delete
        deleted = restarted_repo.delete("inv-sqlite-001")
        self.assertTrue(deleted)
        self.assertIsNone(restarted_repo.get_by_id("inv-sqlite-001"))
        self.assertEqual(len(restarted_repo.get_all()), 0)


class TestInvoiceEditsInAnalyticsAndExports(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        init_db(self.temp_db_path)
        self.repo = DocumentRepository(db_path=self.temp_db_path)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_edits_reflected_in_analytics_and_exports(self):
        # Create initial invoice
        doc = {
            "id": "doc-edit-analytics-1",
            "vendor": "Initial Supplies Ltd",
            "invoice_number": "INV-ORIG-001",
            "date": "2026-06-01",
            "subtotal": "1000.00",
            "tax_total": "180.00",
            "total": "1180.00",
            "items": [
                {
                    "description": "Original Widget",
                    "qty": "2",
                    "unit_price": "500.00",
                    "tax_rate": "18%",
                    "tax_amount": "180.00",
                    "amount": "1000.00",
                }
            ],
            "status": "Pending Verification",
        }
        self.repo.save(doc)

        # Baseline analytics
        analytics_before = self.repo.get_analytics()
        self.assertEqual(analytics_before["total_spend"], 1180.0)
        self.assertEqual(analytics_before["total_tax"], 180.0)
        self.assertEqual(analytics_before["vendors_summary"][0]["vendor"], "Initial Supplies Ltd")

        # Perform invoice edit: update vendor, total, and tax
        self.repo.update("doc-edit-analytics-1", {
            "vendor": "Updated Global Suppliers",
            "invoice_number": "INV-EDITED-999",
            "subtotal": "3000.00",
            "tax_total": "540.00",
            "total": "3540.00",
            "items": [
                {
                    "description": "Premium Widget",
                    "qty": "6",
                    "unit_price": "500.00",
                    "tax_rate": "18%",
                    "tax_amount": "540.00",
                    "amount": "3000.00",
                }
            ],
        })

        # Updated analytics
        analytics_after = self.repo.get_analytics()
        self.assertEqual(analytics_after["total_spend"], 3540.0)
        self.assertEqual(analytics_after["total_tax"], 540.0)
        self.assertEqual(analytics_after["vendors_summary"][0]["vendor"], "Updated Global Suppliers")

        # Test exports with edited invoice data
        edited_doc = self.repo.get_by_id("doc-edit-analytics-1")

        # Excel export
        excel_bytes = export_document_to_excel_bytes(edited_doc)
        self.assertIsInstance(excel_bytes, bytes)
        self.assertGreater(len(excel_bytes), 100)

        # CSV export
        csv_str = export_document_to_csv_string(edited_doc)
        self.assertIn("Updated Global Suppliers", csv_str)
        self.assertIn("INV-EDITED-999", csv_str)
        self.assertIn("3540.00", csv_str)

        # Document Summary export
        doc_summary = export_document_to_doc_summary(edited_doc)
        self.assertIn("Updated Global Suppliers", doc_summary)
        self.assertIn("INV-EDITED-999", doc_summary)

        # Tally XML export
        tally_xml = export_document_to_tally_xml(edited_doc)
        self.assertIn("Updated Global Suppliers", tally_xml)
        self.assertIn("INV-EDITED-999", tally_xml)


class TestMigrationSafetyAndIdempotency(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        init_db(self.temp_db_path)

        self.temp_json = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")
        self.temp_json_path = self.temp_json.name

    def tearDown(self):
        for path in [self.temp_db_path, self.temp_json_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        # Clean up any generated .bak files
        bak_file = f"{self.temp_json_path}.bak"
        if os.path.exists(bak_file):
            try:
                os.remove(bak_file)
            except OSError:
                pass

    def test_migration_from_legacy_fixtures_and_idempotency(self):
        # Construct fixture containing:
        # - 2 valid records with distinct IDs
        # - 1 duplicate record with existing ID
        # - 1 malformed record (string instead of dict)
        # - 1 record with missing ID
        legacy_data = [
            {
                "id": "mig-001",
                "vendor": "Acme Tools Corp",
                "invoice_number": "INV-001",
                "total": "1000.00",
                "items": [{"description": "Drill Bit", "amount": "1000.00"}],
            },
            {
                "id": "mig-002",
                "vendor": "Beta Electronics",
                "invoice_number": "INV-002",
                "total": "2500.00",
                "items": [{"description": "Circuit Board", "amount": "2500.00"}],
            },
            {
                "id": "mig-001",  # Duplicate ID
                "vendor": "Acme Tools Corp Duplicate",
                "invoice_number": "INV-001",
                "total": "1000.00",
            },
            "MALFORMED_NON_DICT_STRING_RECORD",
            {
                # Missing ID
                "vendor": "Nameless Vendor",
                "total": "500.00",
            }
        ]
        json.dump(legacy_data, self.temp_json)
        self.temp_json.close()

        # Run first migration pass
        report1 = migrate_json_to_sqlite(
            json_path=self.temp_json_path,
            db_path=self.temp_db_path,
            backup=True,
            idempotent=True
        )

        # 5 items total: 2 imported, 1 duplicate skipped, 2 malformed failed
        self.assertEqual(report1["total_found"], 5)
        self.assertEqual(report1["imported"], 2)
        self.assertEqual(report1["skipped"], 1)
        self.assertEqual(report1["failed"], 2)

        # Verify source JSON was preserved and backup was created
        self.assertTrue(os.path.exists(self.temp_json_path), "Source JSON must never be deleted")
        self.assertTrue(os.path.exists(f"{self.temp_json_path}.bak"), "Backup .bak must be created")

        # Verify DB content
        repo = DocumentRepository(db_path=self.temp_db_path)
        docs = repo.get_all()
        self.assertEqual(len(docs), 2)
        doc_ids = {d["id"] for d in docs}
        self.assertEqual(doc_ids, {"mig-001", "mig-002"})

        # Re-run migration to test idempotency (no duplicates should be added)
        report2 = migrate_json_to_sqlite(
            json_path=self.temp_json_path,
            db_path=self.temp_db_path,
            backup=False,
            idempotent=True
        )

        # On second run: 0 imported, 3 skipped (mig-001, mig-002, duplicate mig-001), 2 failed (malformed)
        self.assertEqual(report2["imported"], 0)
        self.assertEqual(report2["skipped"], 3)
        self.assertEqual(report2["failed"], 2)

        # Database document count remains strictly 2
        docs_after = repo.get_all()
        self.assertEqual(len(docs_after), 2)


class TestTransactionsAndRollback(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        init_db(self.temp_db_path)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_transaction_rollback_on_unhandled_exception(self):
        # Insert a valid row inside an aborted transaction
        try:
            with get_db(self.temp_db_path) as conn:
                conn.execute(
                    "INSERT INTO documents (id, vendor, total) VALUES (?, ?, ?)",
                    ("aborted-doc-1", "Rollback Vendor", "500.00")
                )
                # Force an exception before commit
                raise RuntimeError("Simulated transaction abort")
        except RuntimeError:
            pass

        # Verify row was rolled back and is not in database
        with get_db(self.temp_db_path) as conn:
            cur = conn.execute("SELECT * FROM documents WHERE id = ?", ("aborted-doc-1",))
            self.assertIsNone(cur.fetchone())

    def test_repository_save_rejects_invalid_types(self):
        repo = DocumentRepository(db_path=self.temp_db_path)
        with self.assertRaises(ValueError):
            repo.save("NOT_A_DICT")


class TestWhatsAppWebhookDeduplication(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        init_db(self.temp_db_path)

        self.repo = WebhookEventRepository(db_path=self.temp_db_path)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_atomic_message_deduplication(self):
        msg_id = "wamid.HBgLMzQ5OTk5OTk5OQ=="
        payload = {"entry": [{"changes": [{"value": {"messages": [{"id": msg_id}]}}]}]}

        # First recording: success
        first_attempt = self.repo.record_event(
            message_id=msg_id,
            source="whatsapp",
            event_type="messages",
            payload=payload
        )
        self.assertTrue(first_attempt, "First delivery must succeed")
        self.assertTrue(self.repo.is_event_processed(msg_id))

        # Second recording with identical message_id: must return False (deduplicated)
        second_attempt = self.repo.record_event(
            message_id=msg_id,
            source="whatsapp",
            event_type="messages",
            payload=payload
        )
        self.assertFalse(second_attempt, "Replay of existing message_id must be deduplicated")

    @patch("backend.app.api.v1.whatsapp_routes.safe_request")
    @patch("backend.app.services.document_service.DocumentService.process_document")
    def test_whatsapp_webhook_endpoint_returns_duplicate_status(self, mock_process, mock_safe_request):
        mock_http_resp = unittest.mock.MagicMock()
        mock_http_resp.content = b"fake_png_data"
        mock_http_resp.raise_for_status = unittest.mock.MagicMock()
        mock_safe_request.return_value = mock_http_resp
        mock_process.return_value = {
            "id": "doc-wh-001",
            "vendor": "Test Vendor",
            "total": "1000.00",
            "status": "Pending Verification"
        }

        app = create_app()
        client = app.test_client()

        secret = settings.whatsapp_app_secret
        import uuid
        msg_id = f"wamid.HBgL_{uuid.uuid4().hex}"
        raw_payload = json.dumps({
            "media_url": "https://example.com/invoice.png",
            "from": "+919876543210",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "id": msg_id,
                            "type": "text",
                            "text": {"body": "Invoice message"}
                        }]
                    }
                }]
            }]
        }).encode("utf-8")

        digest = hmac.new(secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()
        headers = {
            "X-Hub-Signature-256": f"sha256={digest}",
            "Content-Type": "application/json",
        }

        # First delivery: creates document and returns success
        resp1 = client.post("/api/v1/whatsapp/webhook", data=raw_payload, headers=headers)
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.get_json().get("status"), "success")
        self.assertEqual(mock_process.call_count, 1)

        # Second delivery (replay): deduplicated at database layer, process_document not called
        resp2 = client.post("/api/v1/whatsapp/webhook", data=raw_payload, headers=headers)
        self.assertEqual(resp2.status_code, 200)
        json_resp = resp2.get_json()
        self.assertEqual(json_resp.get("status"), "duplicate")
        self.assertIn("already processed", json_resp.get("message", "").lower())
        self.assertEqual(mock_process.call_count, 1, "Duplicate delivery must not re-process document")


class TestSessionRevocation(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        init_db(self.temp_db_path)
        self.session_repo = SessionRepository(db_path=self.temp_db_path)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_session_lifecycle_and_revocation_store(self):
        session_id = "test-session-uuid-12345"

        # Initially not revoked
        self.assertFalse(self.session_repo.is_session_revoked(session_id))

        # Revoke session
        self.session_repo.revoke_session(session_id, user_id="admin", reason="logout")
        self.assertTrue(self.session_repo.is_session_revoked(session_id))

        # Re-revoking same session is idempotent
        self.session_repo.revoke_session(session_id, user_id="admin", reason="logout")
        self.assertTrue(self.session_repo.is_session_revoked(session_id))

    def test_session_invalidated_after_logout_blocks_subsequent_requests(self):
        app = create_app()
        client = app.test_client()

        # 1. Login with valid credentials
        login_resp = client.post("/api/v1/auth/login", json={
            "username": settings.app_admin_username,
            "password": settings.app_admin_password
        })
        self.assertEqual(login_resp.status_code, 200)
        csrf_token = login_resp.get_json().get("csrf_token")
        self.assertIsNotNone(csrf_token)

        # Capture session cookie before logout to simulate replay attack
        session_cookie = client.get_cookie("session")
        self.assertIsNotNone(session_cookie, "Expected session cookie in client")

        # 2. Access protected endpoint while logged in
        doc_resp = client.get("/api/v1/documents")
        self.assertEqual(doc_resp.status_code, 200)

        # 3. Logout with required CSRF token
        logout_resp = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf_token})
        self.assertEqual(logout_resp.status_code, 200)

        # 4. Attempt to access protected endpoint using standard client (cleared session)
        post_logout_resp = client.get("/api/v1/documents")
        self.assertEqual(post_logout_resp.status_code, 401)
        self.assertIn("authentication required", post_logout_resp.get_json().get("error", "").lower())

        # 5. Cookie replay attack using stolen pre-logout cookie is rejected by SQLite revocation store
        replay_client = app.test_client()
        replay_client.set_cookie("session", session_cookie.value)
        replay_resp = replay_client.get("/api/v1/documents")
        self.assertEqual(replay_resp.status_code, 401)
        self.assertIn("revoked", replay_resp.get_json().get("error", "").lower())


if __name__ == "__main__":
    unittest.main()
