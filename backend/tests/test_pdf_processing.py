import io
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from dataclasses import asdict

import fitz
from PIL import Image

from backend.app import create_app
from backend.app.config.settings import settings
from backend.app.ocr.ocr_engine import (
    PDFProcessingError,
    PDFEncryptedError,
    PDFEmptyError,
    PDFCorruptError,
    PDFPageLimitExceededError,
    PDFRenderError,
    render_pdf_pages,
    iter_pdf_pages,
    load_image_or_pdf,
    extract_text,
    extract_text_from_image,
)
from backend.app.models.document import OCRResult
from backend.app.parsers.document_parser import parse_document, regex_parse
from backend.app.services.document_service import DocumentService
from backend.app.services.validation_service import ValidationEngine


def create_synthetic_pdf(pages_text: list[str]) -> str:
    """Helper to generate a temporary multi-page PDF on disk."""
    doc = fitz.open()
    for txt in pages_text:
        page = doc.new_page()
        if txt:
            page.insert_text((50, 72), txt)
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    filename = temp.name
    temp.close()  # Close handle so PyMuPDF can write to file on Windows
    doc.save(filename)
    doc.close()
    return filename


def create_encrypted_pdf(password: str = "secret") -> str:
    """Helper to generate a password-protected PDF on disk."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Encrypted Invoice Data")
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    filename = temp.name
    temp.close()  # Close handle so PyMuPDF can write to file on Windows
    doc.save(filename, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw=password, owner_pw=password)
    doc.close()
    return filename


def create_zero_page_pdf() -> str:
    """Helper to generate a structurally valid PDF file containing 0 pages."""
    data = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
        b"xref\n0 3\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n"
        b"trailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n115\n%%EOF"
    )
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp.write(data)
    temp.close()
    return temp.name


def create_corrupt_pdf() -> str:
    """Helper to generate a corrupt PDF file with valid header but malformed body."""
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp.write(b"%PDF-1.4\nCORRUPTED_BYTE_STREAM_INVALID_PDF_OBJECTS")
    temp.close()
    return temp.name


# ===========================================================================
# A. PDF Rendering Tests
# ===========================================================================

class TestPDFRendering(unittest.TestCase):
    def setUp(self):
        self.temp_files: list[str] = []

    def tearDown(self):
        for path in self.temp_files:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    def test_valid_one_page_pdf(self):
        pdf_path = create_synthetic_pdf(["Tax Invoice - Single Page"])
        self.temp_files.append(pdf_path)

        images = render_pdf_pages(pdf_path)
        self.assertEqual(len(images), 1)
        self.assertIsInstance(images[0], Image.Image)
        self.assertEqual(images[0].mode, "RGB")
        self.assertGreater(images[0].width, 100)
        self.assertGreater(images[0].height, 100)

    def test_valid_three_page_pdf(self):
        pdf_path = create_synthetic_pdf(["Page 1 Content", "Page 2 Content", "Page 3 Content"])
        self.temp_files.append(pdf_path)

        images = render_pdf_pages(pdf_path)
        self.assertEqual(len(images), 3)
        for img in images:
            self.assertIsInstance(img, Image.Image)
            self.assertEqual(img.mode, "RGB")

    def test_correct_page_ordering(self):
        # Create pages with distinct dimensions to verify ordering
        doc = fitz.open()
        p1 = doc.new_page(width=300, height=400)
        p1.insert_text((20, 40), "P1")
        p2 = doc.new_page(width=500, height=600)
        p2.insert_text((20, 40), "P2")
        p3 = doc.new_page(width=700, height=800)
        p3.insert_text((20, 40), "P3")
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        filename = temp.name
        temp.close()
        doc.save(filename)
        doc.close()
        self.temp_files.append(filename)

        images = render_pdf_pages(filename)
        self.assertEqual(len(images), 3)
        # Widths must strictly increase matching the page generation order
        self.assertLess(images[0].width, images[1].width)
        self.assertLess(images[1].width, images[2].width)

    def test_blank_page_between_pages_containing_text(self):
        pdf_path = create_synthetic_pdf(["Page 1 Header", "", "Page 3 Footer"])
        self.temp_files.append(pdf_path)

        images = render_pdf_pages(pdf_path)
        self.assertEqual(len(images), 3)
        for img in images:
            self.assertIsInstance(img, Image.Image)
            self.assertEqual(img.mode, "RGB")

    def test_empty_pdf_raises_pdf_empty_error(self):
        empty_pdf = create_zero_page_pdf()
        self.temp_files.append(empty_pdf)

        with self.assertRaises(PDFEmptyError) as ctx:
            render_pdf_pages(empty_pdf)
        self.assertIn("contains no pages", str(ctx.exception).lower())

    def test_corrupt_pdf_raises_pdf_corrupt_error(self):
        corrupt_pdf = create_corrupt_pdf()
        self.temp_files.append(corrupt_pdf)

        with self.assertRaises(PDFCorruptError) as ctx:
            render_pdf_pages(corrupt_pdf)
        self.assertIn("corrupted", str(ctx.exception).lower())

    def test_encrypted_pdf_raises_pdf_encrypted_error(self):
        enc_pdf = create_encrypted_pdf("secret123")
        self.temp_files.append(enc_pdf)

        with self.assertRaises(PDFEncryptedError) as ctx:
            render_pdf_pages(enc_pdf)
        self.assertIn("encrypted", str(ctx.exception).lower())

    def test_page_count_limit_exceeded(self):
        pdf_path = create_synthetic_pdf(["Page 1", "Page 2", "Page 3", "Page 4"])
        self.temp_files.append(pdf_path)

        with self.assertRaises(PDFPageLimitExceededError) as ctx:
            render_pdf_pages(pdf_path, max_pages=3)
        self.assertIn("exceeds maximum permitted limit", str(ctx.exception))

    def test_rendering_resource_limit_exceeded(self):
        pdf_path = create_synthetic_pdf(["Normal Page"])
        self.temp_files.append(pdf_path)

        # Patch MAX_RENDER_PIXELS_PER_PAGE to a very low value (e.g. 100 pixels) to trigger resource guard
        with patch("backend.app.ocr.ocr_engine.MAX_RENDER_PIXELS_PER_PAGE", 100):
            with self.assertRaises(PDFRenderError) as ctx:
                render_pdf_pages(pdf_path)
            self.assertIn("exceed", str(ctx.exception).lower())

    def test_load_image_or_pdf_backward_compatibility(self):
        pdf_path = create_synthetic_pdf(["Single Page Doc"])
        self.temp_files.append(pdf_path)

        img = load_image_or_pdf(pdf_path)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.mode, "RGB")


# ===========================================================================
# B. OCR Integration Tests
# ===========================================================================

class TestMultiPageOCRIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_files: list[str] = []

    def tearDown(self):
        for path in self.temp_files:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    @patch("backend.app.ocr.ocr_engine.extract_text_from_image")
    def test_mock_ocr_providers_return_distinct_text_retained_in_order(self, mock_ocr):
        mock_ocr.side_effect = [
            OCRResult(text="Line from Page 1", confidence=0.92, raw_lines=["Line from Page 1"]),
            OCRResult(text="Line from Page 2", confidence=0.88, raw_lines=["Line from Page 2"]),
            OCRResult(text="Line from Page 3", confidence=0.84, raw_lines=["Line from Page 3"]),
        ]

        pdf_path = create_synthetic_pdf(["P1", "P2", "P3"])
        self.temp_files.append(pdf_path)

        result = extract_text(pdf_path)

        # Assert all page results retained in order
        self.assertIn("Line from Page 1", result.text)
        self.assertIn("Line from Page 2", result.text)
        self.assertIn("Line from Page 3", result.text)

        # Assert page boundaries are preserved
        self.assertIn("--- Page 1 ---", result.text)
        self.assertIn("--- Page 2 ---", result.text)
        self.assertIn("--- Page 3 ---", result.text)

        pos1 = result.text.index("--- Page 1 ---")
        pos2 = result.text.index("--- Page 2 ---")
        pos3 = result.text.index("--- Page 3 ---")
        self.assertLess(pos1, pos2)
        self.assertLess(pos2, pos3)

    @patch("backend.app.ocr.ocr_engine.extract_text_from_image")
    def test_confidence_aggregation_across_pages(self, mock_ocr):
        mock_ocr.side_effect = [
            OCRResult(text="Page 1", confidence=0.90, raw_lines=["Page 1"]),
            OCRResult(text="Page 2", confidence=0.80, raw_lines=["Page 2"]),
        ]

        pdf_path = create_synthetic_pdf(["P1", "P2"])
        self.temp_files.append(pdf_path)

        result = extract_text(pdf_path)
        # Average of 0.90 and 0.80 is 0.85
        self.assertAlmostEqual(result.confidence, 0.85, places=2)

    @patch("backend.app.ocr.ocr_engine.extract_text_from_image")
    def test_blank_page_between_text_pages_confidence_aggregation(self, mock_ocr):
        mock_ocr.side_effect = [
            OCRResult(text="Page 1 Content", confidence=0.90, raw_lines=["Page 1 Content"]),
            OCRResult(text="", confidence=0.0, raw_lines=[]),  # Blank page
            OCRResult(text="Page 3 Content", confidence=0.80, raw_lines=["Page 3 Content"]),
        ]

        pdf_path = create_synthetic_pdf(["P1", "", "P3"])
        self.temp_files.append(pdf_path)

        result = extract_text(pdf_path)
        # Aggregated only across non-empty pages (0.90 + 0.80) / 2 = 0.85
        self.assertAlmostEqual(result.confidence, 0.85, places=2)
        self.assertIn("--- Page 1 ---", result.text)
        self.assertIn("--- Page 2 ---", result.text)
        self.assertIn("--- Page 3 ---", result.text)

    @patch("backend.app.ocr.ocr_engine.extract_text_from_image")
    def test_behavior_when_one_page_fails(self, mock_ocr):
        # Page 2 raises an unexpected error; Pages 1 & 3 succeed
        mock_ocr.side_effect = [
            OCRResult(text="Page 1 Valid Text", confidence=0.95, raw_lines=["Page 1 Valid Text"]),
            RuntimeError("Unexpected OCR engine crash on corrupt page 2"),
            OCRResult(text="Page 3 Valid Text", confidence=0.85, raw_lines=["Page 3 Valid Text"]),
        ]

        pdf_path = create_synthetic_pdf(["P1", "P2", "P3"])
        self.temp_files.append(pdf_path)

        result = extract_text(pdf_path)

        # Results from page 1 and 3 are preserved
        self.assertIn("Page 1 Valid Text", result.text)
        self.assertIn("Page 3 Valid Text", result.text)
        self.assertAlmostEqual(result.confidence, 0.90, places=2)

    @patch("backend.app.ocr.ocr_engine.extract_text_from_image")
    def test_behavior_when_all_pages_fail_raises_clear_failure(self, mock_ocr):
        mock_ocr.side_effect = [
            RuntimeError("Crash 1"),
            RuntimeError("Crash 2"),
        ]

        pdf_path = create_synthetic_pdf(["P1", "P2"])
        self.temp_files.append(pdf_path)

        with self.assertRaises(PDFProcessingError) as ctx:
            extract_text(pdf_path)
        self.assertIn("OCR processing failed or produced no readable text", str(ctx.exception))


# ===========================================================================
# C. Multi-Page Invoice Extraction Tests
# ===========================================================================

class TestMultiPageInvoiceExtraction(unittest.TestCase):
    def test_extract_items_across_three_pages_and_ignore_repeated_headers(self):
        raw_multi_page_ocr_text = """
--- Page 1 ---
Acme Industrial Supplies
GSTIN: 27AABCU9603R1ZM
Invoice No: INV-2026-9042
Date: 15/04/2026
Item Description Qty Rate Amount
Industrial Steel Valve 2 2500.00 5000.00

--- Page 2 ---
Acme Industrial Supplies
Page 2 of 3
Item Description Qty Rate Amount
High Pressure Gauge 4 750.00 3000.00
Hydraulic Hose Pipe 10 200.00 2000.00

--- Page 3 ---
Acme Industrial Supplies
Page 3 of 3
Item Description Qty Rate Amount
Gasket Seal Pack 5 400.00 2000.00
Subtotal: 12000.00
CGST (9%): 1080.00
SGST (9%): 1080.00
Total: 14160.00
"""
        parsed_doc = regex_parse(raw_multi_page_ocr_text)

        # 1. Header extraction
        self.assertEqual(parsed_doc.vendor, "Acme Industrial Supplies")
        self.assertEqual(parsed_doc.gstin, "27AABCU9603R1ZM")
        self.assertEqual(parsed_doc.invoice_number, "INV-2026-9042")
        self.assertEqual(parsed_doc.date, "2026-04-15")

        # 2. Line items from all 3 pages are extracted in order
        descriptions = [it.description for it in parsed_doc.items]
        self.assertEqual(len(parsed_doc.items), 4)
        self.assertIn("Industrial Steel Valve", descriptions[0])
        self.assertIn("High Pressure Gauge", descriptions[1])
        self.assertIn("Hydraulic Hose Pipe", descriptions[2])
        self.assertIn("Gasket Seal Pack", descriptions[3])

        # 3. Repeated headers and page numbers must NOT be extracted as items
        for desc in descriptions:
            self.assertNotIn("Page 2", desc)
            self.assertNotIn("Page 3", desc)
            self.assertNotIn("--- Page", desc)
            self.assertNotIn("Item Description", desc)

        # 4. Math and validation totals
        self.assertEqual(parsed_doc.subtotal, "12000.00")
        self.assertEqual(parsed_doc.cgst, "1080.00")
        self.assertEqual(parsed_doc.sgst, "1080.00")
        self.assertEqual(parsed_doc.total, "14160.00")

        # 5. Validation engine checks
        warnings = ValidationEngine.validate_document(asdict(parsed_doc), [])
        error_warnings = [w for w in warnings if w.get("type") == "error"]
        # No calculation errors because line item sum matches subtotal and tax matches total
        self.assertEqual(len(error_warnings), 0)

    def test_missing_totals_handled_safely_without_inventing_values(self):
        text_without_totals = """
--- Page 1 ---
Acme Industrial Supplies
Invoice No: INV-001
Date: 10/01/2026
Item Description Qty Rate Amount
Hardware Item A 1 500.00 500.00

--- Page 2 ---
Hardware Item B 1 600.00 600.00
"""
        parsed_doc = regex_parse(text_without_totals)
        self.assertEqual(len(parsed_doc.items), 2)
        # Subtotal should not invent arbitrary values when not present
        self.assertEqual(parsed_doc.cgst, "0.00")
        self.assertEqual(parsed_doc.sgst, "0.00")


# ===========================================================================
# D. API Integration Tests
# ===========================================================================

class TestUploadAPIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def setUp(self):
        self.temp_files: list[str] = []

    def tearDown(self):
        for path in self.temp_files:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    @patch("backend.app.services.document_service.DocumentService.process_document")
    def test_upload_valid_one_page_pdf(self, mock_process):
        mock_process.return_value = {
            "id": "pdf-uuid-1",
            "vendor": "Acme Corp",
            "total": "500.00",
            "status": "Pending Verification"
        }
        pdf_path = create_synthetic_pdf(["Invoice Page 1"])
        self.temp_files.append(pdf_path)

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        resp = self.client.post(
            "/api/v1/upload",
            data={"file": (io.BytesIO(pdf_bytes), "invoice.pdf")},
            content_type="multipart/form-data"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json().get("vendor"), "Acme Corp")

    @patch("backend.app.services.document_service.DocumentService.process_document")
    def test_upload_valid_multi_page_pdf(self, mock_process):
        mock_process.return_value = {
            "id": "pdf-uuid-multi",
            "vendor": "MultiPage Supplies",
            "items": [{"description": "Item 1"}, {"description": "Item 2"}],
            "total": "1500.00",
            "status": "Pending Verification"
        }
        pdf_path = create_synthetic_pdf(["P1", "P2", "P3"])
        self.temp_files.append(pdf_path)

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        resp = self.client.post(
            "/api/v1/upload",
            data={"file": (io.BytesIO(pdf_bytes), "multi_invoice.pdf")},
            content_type="multipart/form-data"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.get_json().get("items")), 2)

    def test_upload_corrupt_pdf_returns_400(self):
        corrupt_bytes = b"%PDF-1.4\nNOT_A_VALID_PDF_STREAM_MALFORMED_TRAILER"
        resp = self.client.post(
            "/api/v1/upload",
            data={"file": (io.BytesIO(corrupt_bytes), "corrupt.pdf")},
            content_type="multipart/form-data"
        )
        self.assertEqual(resp.status_code, 400)
        error_msg = resp.get_json().get("error", "")
        self.assertTrue("corrupt" in error_msg.lower() or "invalid" in error_msg.lower())

    def test_upload_encrypted_pdf_returns_400(self):
        enc_pdf = create_encrypted_pdf("secret_password")
        self.temp_files.append(enc_pdf)

        with open(enc_pdf, "rb") as f:
            enc_bytes = f.read()

        resp = self.client.post(
            "/api/v1/upload",
            data={"file": (io.BytesIO(enc_bytes), "protected.pdf")},
            content_type="multipart/form-data"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("encrypted", resp.get_json().get("error", "").lower())

    def test_upload_disguised_file_rejected_400(self):
        fake_pdf = b"#!/bin/bash\necho 'Not a PDF'\n"
        resp = self.client.post(
            "/api/v1/upload",
            data={"file": (io.BytesIO(fake_pdf), "fake.pdf")},
            content_type="multipart/form-data"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Malformed file content or extension mismatch", resp.get_json().get("error", ""))

    def test_upload_pdf_exceeding_page_limit_returns_400(self):
        # Create a 4-page PDF and set max_pdf_pages to 2
        pdf_path = create_synthetic_pdf(["P1", "P2", "P3", "P4"])
        self.temp_files.append(pdf_path)

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        with patch.object(settings, "max_pdf_pages", 2):
            resp = self.client.post(
                "/api/v1/upload",
                data={"file": (io.BytesIO(pdf_bytes), "large.pdf")},
                content_type="multipart/form-data"
            )
            self.assertEqual(resp.status_code, 400)
            self.assertIn("exceeds maximum permitted limit", resp.get_json().get("error", ""))

    def test_corrupt_pdf_does_not_leak_filesystem_paths(self):
        corrupt_bytes = b"%PDF-1.4\nCORRUPTED_STREAM_CONTENT"
        resp = self.client.post(
            "/api/v1/upload",
            data={"file": (io.BytesIO(corrupt_bytes), "corrupt_invoice.pdf")},
            content_type="multipart/form-data"
        )
        self.assertEqual(resp.status_code, 400)
        error_msg = resp.get_json().get("error", "")
        # Must not contain windows or unix temp paths
        self.assertNotIn("AppData", error_msg)
        self.assertNotIn("Temp", error_msg)
        self.assertNotIn("\\", error_msg)
        self.assertNotIn("/tmp", error_msg)

    def test_temp_file_cleaned_up_on_upload_failure(self):
        saved_paths = []
        original_named_temp_file = tempfile.NamedTemporaryFile

        def tracking_temp_file(*args, **kwargs):
            tf = original_named_temp_file(*args, **kwargs)
            saved_paths.append(tf.name)
            return tf

        corrupt_bytes = b"%PDF-1.4\nMALFORMED_DATA"
        with patch("backend.app.api.v1.routes.tempfile.NamedTemporaryFile", side_effect=tracking_temp_file):
            resp = self.client.post(
                "/api/v1/upload",
                data={"file": (io.BytesIO(corrupt_bytes), "corrupt.pdf")},
                content_type="multipart/form-data"
            )
            self.assertEqual(resp.status_code, 400)

        self.assertTrue(len(saved_paths) > 0)
        for p in saved_paths:
            self.assertFalse(os.path.exists(p), f"Temp file was not cleaned up: {p}")


if __name__ == "__main__":
    unittest.main()

