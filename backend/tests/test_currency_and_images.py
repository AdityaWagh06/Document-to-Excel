"""
Currency handling (never relabel or convert amounts) and image-assisted AI extraction.
All AI calls are mocked.
"""
import unittest
from unittest.mock import patch

from backend.app.ai.providers import AIProviderError, AIResult
from backend.app.ai.schema import InvoiceExtraction
from backend.app.exports.csv_exporter import export_document_to_csv_string
from backend.app.exports.doc_exporter import export_document_to_doc_summary
from backend.app.parsers.document_parser import parse_document, regex_parse
from backend.app.services.validation_service import ValidationEngine
from backend.app.utils.currency import detect_currency, normalize_currency

# OCR text of a real US grocery receipt where the "$" of "$25.97" was misread as "5"
US_RECEIPT_OCR = """The - Shop
Store #100
Chicago , IL
Large Eggs 0.99
Kilk 1.15
cottage Cheese 0 59
Natural yogurt 0 70
Cherry TomnaLoes l16 1.29
Bananas IIb 0.77
Aubergine 1.50
Cheese Crackers 2.19
Chocolate Cookies 1.82
Canned Tuna 12pk 5.95
Chicken Breast 2.46
Toilet Paper 4.98
Baby wipes 1.59
TOTAL 525.97"""

US_RECEIPT_AI = {
    "vendor": "The Shop", "gstin": "", "invoice_number": "", "date": "", "due_date": "",
    "subtotal": "", "cgst": "", "sgst": "", "igst": "", "tax_total": "", "discount": "",
    "other_charges": "", "total": "25.97", "currency": "USD",
    "items": [{"description": "Large Eggs", "hsn_sac": "", "qty": "1", "unit_price": "",
               "tax_rate": "", "tax_amount": "", "amount": "0.99"}],
}


class FakeProvider:
    name = "gemini"

    def __init__(self, payload, reject_images=False):
        self.payload = payload
        self.reject_images = reject_images
        self.calls = []

    def extract_invoice(self, text, images=None):
        self.calls.append(bool(images))
        if images and self.reject_images:
            raise AIProviderError("model does not support image input", "bad_request", status=400)
        return AIResult(extraction=InvoiceExtraction.model_validate(self.payload), provider="gemini", model="test-model")


class TestCurrencyDetection(unittest.TestCase):
    def test_detects_currency_from_symbols_and_codes(self):
        cases = {
            "Total: $25.97": "USD",
            "Grand Total ₹ 5,900.00": "INR",
            "Amount Rs. 450": "INR",
            "Total EUR 120,00": "EUR",
            "Total € 120": "EUR",
            "TOTAL £14.50": "GBP",
            "Total AED 75.00": "AED",
            "Total CA$ 40.00": "CAD",
            "GSTIN 27AAPFU0939F1ZV Total 500": "INR",
            "Total 500.00": "",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(detect_currency(text), expected)

    def test_normalize_currency(self):
        self.assertEqual(normalize_currency("usd"), "USD")
        self.assertEqual(normalize_currency("$"), "USD")
        self.assertEqual(normalize_currency("Rs."), "INR")
        self.assertEqual(normalize_currency("dollars?"), "")

    def test_rule_parser_keeps_dollar_currency(self):
        doc = regex_parse("Joe's Diner\nBurger 1 $12.50\nTOTAL $12.50")
        self.assertEqual(doc.currency, "USD")

    def test_rule_parser_does_not_read_numbers_across_lines_as_a_date(self):
        doc = regex_parse(US_RECEIPT_OCR)
        self.assertNotIn("\n", doc.date)
        self.assertNotIn("TOTAL", doc.date)


class TestImageAssistedExtraction(unittest.TestCase):
    def test_images_are_sent_and_image_values_win_over_ocr_misreads(self):
        provider = FakeProvider(US_RECEIPT_AI)
        with patch("backend.app.parsers.document_parser.get_provider", return_value=provider):
            doc = parse_document(US_RECEIPT_OCR, 0.85, images_b64_png=["aW1n"])
        self.assertEqual(provider.calls, [True])
        self.assertEqual(doc.total, "25.97")
        self.assertEqual(doc.currency, "USD")
        self.assertEqual(doc.extraction_method, "ai-image:gemini")
        # Rule-parser amounts read from the bad OCR text must not overwrite image values
        amounts = [doc.subtotal, doc.tax_total, doc.other_charges, doc.total]
        self.assertNotIn("525.97", amounts)
        self.assertGreater(doc.confidence, 0.6)

    def test_text_only_model_retries_without_images(self):
        provider = FakeProvider(US_RECEIPT_AI, reject_images=True)
        with patch("backend.app.parsers.document_parser.get_provider", return_value=provider):
            doc = parse_document(US_RECEIPT_OCR, 0.85, images_b64_png=["aW1n"])
        self.assertEqual(provider.calls, [True, False])
        self.assertEqual(doc.extraction_method, "ai:gemini")

    def test_ai_currency_falls_back_to_detection(self):
        payload = dict(US_RECEIPT_AI, currency="")
        provider = FakeProvider(payload)
        with patch("backend.app.parsers.document_parser.get_provider", return_value=provider):
            doc = parse_document("Total: $25.97", 0.9)
        self.assertEqual(doc.currency, "USD")


class TestCurrencyAwareValidationAndExport(unittest.TestCase):
    def _doc(self, **overrides):
        doc = {
            "id": "x", "vendor": "The Shop", "invoice_number": "", "date": "2026-07-28", "gstin": "",
            "subtotal": "24.00", "tax_total": "1.97", "discount": "0.00", "other_charges": "0.00",
            "total": "25.97", "currency": "USD",
            "items": [{"description": "Eggs", "qty": "1", "unit_price": "24.00", "amount": "24.00"}],
        }
        doc.update(overrides)
        return doc

    def test_foreign_bill_does_not_ask_for_gstin(self):
        codes = {w["code"] for w in ValidationEngine.validate_document(self._doc(), [])}
        self.assertNotIn("MISSING_GSTIN", codes)
        self.assertNotIn("TAX_MISMATCH", codes)

    def test_tip_and_discount_are_part_of_the_total_check(self):
        doc = self._doc(other_charges="5.00", discount="1.00", total="29.97")
        codes = {w["code"] for w in ValidationEngine.validate_document(doc, [])}
        self.assertNotIn("TAX_MISMATCH", codes)

    def test_large_item_sum_gap_is_a_warning(self):
        doc = self._doc(subtotal="0.00", tax_total="0.00", total="525.97")
        warnings = ValidationEngine.validate_document(doc, [])
        gap = [w for w in warnings if w["code"] == "ITEM_SUM_MISMATCH"]
        self.assertEqual(gap[0]["type"], "warning")

    def test_exports_use_document_currency_not_rupees(self):
        doc = self._doc()
        summary = export_document_to_doc_summary(doc)
        self.assertIn("USD 25.97", summary)
        self.assertNotIn("₹", summary)
        self.assertIn("Currency,USD", export_document_to_csv_string(doc).replace("\r", ""))


class TestCurrencyApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.app import create_app
        from backend.app.config.settings import settings
        cls.app = create_app()
        cls.api_headers = {"X-API-Key": settings.api_secret_key}

    def test_currency_is_editable_and_analytics_never_mix_currencies(self):
        from backend.app.repository.document_repository import document_repo
        client = self.app.test_client()
        inr = document_repo.save({"vendor": "Sharma", "invoice_number": "A1", "total": "1000.00", "currency": "INR"})
        usd = document_repo.save({"vendor": "The Shop", "invoice_number": "B1", "total": "25.97", "currency": ""})
        try:
            resp = client.put(f"/api/v1/documents/{usd['id']}", json={"currency": "usd"}, headers=self.api_headers)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get_json()["currency"], "USD")

            bad = client.put(f"/api/v1/documents/{usd['id']}", json={"currency": "dollars"}, headers=self.api_headers)
            self.assertEqual(bad.status_code, 400)

            analytics = client.get("/api/v1/analytics", headers=self.api_headers).get_json()
            totals = {c["currency"]: c["total_spend"] for c in analytics["currency_totals"]}
            self.assertEqual(totals.get("USD"), 25.97)
            self.assertGreaterEqual(totals.get("INR", 0), 1000.0)
            self.assertNotEqual(analytics["total_spend"], 1025.97)
        finally:
            document_repo.delete(inr["id"])
            document_repo.delete(usd["id"])


if __name__ == "__main__":
    unittest.main()
