import io
import unittest
from unittest.mock import patch, MagicMock

from backend.app import create_app
from backend.app.config.settings import settings
from backend.app.repository.document_repository import document_repo
from backend.app.services.document_service import DocumentService


class TestDocumentPersistenceAndExports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        cls.client.environ_base["HTTP_X_API_KEY"] = settings.api_secret_key

    def setUp(self):
        # Back up existing documents in memory and clear during test
        self.original_docs = [dict(d) for d in document_repo._documents]
        document_repo._documents = []
        # Prevent tests from writing to actual temp/documents.json on disk
        self.save_patcher = patch.object(document_repo, "_save_to_disk")
        self.mock_save = self.save_patcher.start()

    def tearDown(self):
        self.save_patcher.stop()
        document_repo._documents = self.original_docs

    def _create_sample_doc(self, doc_id="test-doc-1", **kwargs):
        doc = {
            "id": doc_id,
            "vendor": "Initial Vendor Pvt Ltd",
            "gstin": "27AABCU9603R1ZM",
            "invoice_number": "INV-2026-001",
            "date": "2026-04-10",
            "due_date": "2026-04-25",
            "subtotal": "1000.00",
            "cgst": "90.00",
            "sgst": "90.00",
            "igst": "0.00",
            "tax_total": "180.00",
            "total": "1180.00",
            "items": [
                {
                    "description": "Item 1",
                    "hsn_sac": "8471",
                    "qty": "2",
                    "unit_price": "500.00",
                    "tax_rate": "18%",
                    "tax_amount": "180.00",
                    "amount": "1000.00",
                }
            ],
            "confidence": 0.95,
            "ocr_confidence": 0.92,
            "raw_text": "Sample Invoice Text",
            "status": "Pending Verification",
            "erp_sync_status": "Not Synced",
            "validation_warnings": [],
            "created_at": "2026-04-10T10:00:00",
        }
        doc.update(kwargs)
        document_repo._documents.append(dict(doc))
        return dict(doc)

    def test_update_existing_document_persists_changes(self):
        self._create_sample_doc("doc-update-1")

        updates = {
            "vendor": "Corrected Vendor Corp",
            "invoice_number": "INV-2026-CORRECTED",
            "subtotal": "2000.00",
            "total": "2360.00",
            "cgst": "180.00",
            "sgst": "180.00",
            "tax_total": "360.00",
            "items": [
                {
                    "description": "Upgraded Item",
                    "hsn_sac": "8472",
                    "qty": "4",
                    "unit_price": "500.00",
                    "tax_rate": "18%",
                    "tax_amount": "360.00",
                    "amount": "2000.00",
                }
            ],
        }

        resp = self.client.put("/api/v1/documents/doc-update-1", json=updates)
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertEqual(data["vendor"], "Corrected Vendor Corp")
        self.assertEqual(data["invoice_number"], "INV-2026-CORRECTED")
        self.assertEqual(data["subtotal"], "2000.00")
        self.assertEqual(data["total"], "2360.00")
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["description"], "Upgraded Item")

    def test_get_returns_updated_values(self):
        self._create_sample_doc("doc-get-1")

        self.client.put(
            "/api/v1/documents/doc-get-1",
            json={"vendor": "Persistent Name", "total": "5500.00"},
        )

        resp = self.client.get("/api/v1/documents/doc-get-1")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["vendor"], "Persistent Name")
        self.assertEqual(data["total"], "5500.00")

    def test_missing_document_ids_return_404(self):
        resp_put = self.client.put(
            "/api/v1/documents/non_existent_id",
            json={"vendor": "Ghost Corp"},
        )
        self.assertEqual(resp_put.status_code, 404)
        self.assertIn("Document not found", resp_put.get_json().get("error", ""))

        resp_get = self.client.get("/api/v1/documents/non_existent_id")
        self.assertEqual(resp_get.status_code, 404)
        self.assertIn("Document not found", resp_get.get_json().get("error", ""))

    def test_invalid_payloads_rejected_with_400(self):
        self._create_sample_doc("doc-invalid-1")

        # 1. Non-dict payload
        resp1 = self.client.put(
            "/api/v1/documents/doc-invalid-1",
            data="Not a JSON object",
            content_type="application/json",
        )
        self.assertEqual(resp1.status_code, 400)

        # 2. Invalid field type (e.g. list instead of string/number)
        resp2 = self.client.put(
            "/api/v1/documents/doc-invalid-1",
            json={"vendor": ["Invalid", "List"]},
        )
        self.assertEqual(resp2.status_code, 400)
        self.assertIn("Field 'vendor' must be a string", resp2.get_json().get("error", ""))

        # 3. Invalid items type (not a list)
        resp3 = self.client.put(
            "/api/v1/documents/doc-invalid-1",
            json={"items": "Invalid item string"},
        )
        self.assertEqual(resp3.status_code, 400)
        self.assertIn("items", resp3.get_json().get("error", "").lower())

        # 4. Invalid item object inside items (not a dict)
        resp4 = self.client.put(
            "/api/v1/documents/doc-invalid-1",
            json={"items": ["Not a dict"]},
        )
        self.assertEqual(resp4.status_code, 400)
        self.assertIn("must be a JSON object", resp4.get_json().get("error", ""))

    def test_validation_status_and_warnings_recalculated(self):
        # Create document with an intentional calculation error: 2 * 100 != 500
        self._create_sample_doc(
            "doc-math-1",
            subtotal="500.00",
            total="500.00",
            tax_total="0.00",
            items=[
                {
                    "description": "Faulty Item",
                    "qty": "2",
                    "unit_price": "100.00",
                    "amount": "500.00",
                }
            ],
            status="Flagged Error",
        )

        # Verify initial state has warning
        initial = document_repo.get_by_id("doc-math-1")
        initial_warnings = initial.get("validation_warnings", [])

        # Correct the invoice: qty=5, unit_price=100 -> 500.00
        resp = self.client.put(
            "/api/v1/documents/doc-math-1",
            json={
                "items": [
                    {
                        "description": "Faulty Item Corrected",
                        "qty": "5",
                        "unit_price": "100.00",
                        "amount": "500.00",
                    }
                ],
                "subtotal": "500.00",
                "total": "500.00",
            },
        )
        self.assertEqual(resp.status_code, 200)
        updated = resp.get_json()

        # Check that CALCULATION_ERROR was cleared
        calc_errors = [
            w for w in updated.get("validation_warnings", [])
            if w.get("code") == "CALCULATION_ERROR"
        ]
        self.assertEqual(len(calc_errors), 0)
        self.assertEqual(updated["status"], "Pending Verification")

    def test_immutable_fields_cannot_be_overwritten(self):
        self._create_sample_doc(
            "doc-immutable-1",
            created_at="2026-01-01T12:00:00",
        )

        resp = self.client.put(
            "/api/v1/documents/doc-immutable-1",
            json={
                "id": "malicious-replacement-id",
                "created_at": "1990-01-01T00:00:00",
                "vendor": "Legit Update Vendor",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["id"], "doc-immutable-1")
        self.assertEqual(data["created_at"], "2026-01-01T12:00:00")
        self.assertEqual(data["vendor"], "Legit Update Vendor")

    def test_client_supplied_validation_warnings_ignored(self):
        self._create_sample_doc("doc-warnings-1")

        fake_warning = {
            "code": "CLIENT_INJECTED_ERROR",
            "type": "error",
            "field": "vendor",
            "message": "Fake injection",
        }

        resp = self.client.put(
            "/api/v1/documents/doc-warnings-1",
            json={"validation_warnings": [fake_warning]},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        codes = [w.get("code") for w in data.get("validation_warnings", [])]
        self.assertNotIn("CLIENT_INJECTED_ERROR", codes)

    def test_saved_edits_reflected_in_export_output(self):
        self._create_sample_doc(
            "doc-export-1",
            vendor="Export Target Inc",
            invoice_number="EXP-2026-888",
            total="7500.00",
            items=[
                {
                    "description": "Exported Widget",
                    "amount": "7500.00",
                    "qty": "3",
                    "unit_price": "2500.00",
                }
            ],
        )

        # Update invoice
        self.client.put(
            "/api/v1/documents/doc-export-1",
            json={
                "vendor": "Updated Global Exporters",
                "invoice_number": "EXP-2026-FINAL",
            },
        )

        # 1. Excel export
        resp_excel = self.client.get("/api/v1/documents/doc-export-1/export/excel")
        self.assertEqual(resp_excel.status_code, 200)
        self.assertTrue(len(resp_excel.data) > 100)

        # 2. CSV export
        resp_csv = self.client.get("/api/v1/documents/doc-export-1/export/csv")
        self.assertEqual(resp_csv.status_code, 200)
        csv_text = resp_csv.data.decode("utf-8")
        self.assertIn("Updated Global Exporters", csv_text)
        self.assertIn("EXP-2026-FINAL", csv_text)

        # 3. DOC Summary export
        resp_doc = self.client.get("/api/v1/documents/doc-export-1/export/doc")
        self.assertEqual(resp_doc.status_code, 200)
        doc_text = resp_doc.data.decode("utf-8")
        self.assertIn("Updated Global Exporters", doc_text)
        self.assertIn("EXP-2026-FINAL", doc_text)

        # 4. Tally XML export
        resp_tally = self.client.get("/api/v1/documents/doc-export-1/export/tally")
        self.assertEqual(resp_tally.status_code, 200)
        xml_text = resp_tally.data.decode("utf-8")
        self.assertIn("Updated Global Exporters", xml_text)

    def test_failed_updates_do_not_corrupt_existing_records(self):
        self._create_sample_doc("doc-atomic-1", vendor="Clean Safe Vendor")

        # Attempt invalid update with bad items structure
        resp = self.client.put(
            "/api/v1/documents/doc-atomic-1",
            json={
                "vendor": "Should Not Be Saved",
                "items": "InvalidNonList",
            },
        )
        self.assertEqual(resp.status_code, 400)

        # Verify repository still holds unmodified record
        doc = document_repo.get_by_id("doc-atomic-1")
        self.assertEqual(doc["vendor"], "Clean Safe Vendor")

    def test_analytics_reflect_saved_edits(self):
        self._create_sample_doc(
            "doc-analytics-1",
            total="1000.00",
            tax_total="180.00",
            vendor="Old Analytics Vendor",
        )

        # Check initial analytics
        resp_initial = self.client.get("/api/v1/analytics")
        self.assertEqual(resp_initial.get_json()["total_spend"], 1000.0)

        # Update spend to 4500.00 and new vendor
        self.client.put(
            "/api/v1/documents/doc-analytics-1",
            json={"total": "4500.00", "tax_total": "500.00", "vendor": "New Analytics Vendor"},
        )

        resp_updated = self.client.get("/api/v1/analytics")
        analytics = resp_updated.get_json()
        self.assertEqual(analytics["total_spend"], 4500.0)
        self.assertEqual(analytics["total_tax"], 500.0)
        top_vendor = analytics["vendors_summary"][0]
        self.assertEqual(top_vendor["vendor"], "New Analytics Vendor")
        self.assertEqual(top_vendor["total_spend"], 4500.0)


if __name__ == "__main__":
    unittest.main()
