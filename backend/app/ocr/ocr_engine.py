from __future__ import annotations
import logging
import os
import re
import sys
import threading
from abc import ABC, abstractmethod
from typing import Optional, Union, Generator, Tuple, List

import cv2
import numpy as np
from PIL import Image
import fitz  # PyMuPDF

if hasattr(sys.stdout, "reconfigure"):
    getattr(sys.stdout, "reconfigure")(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    getattr(sys.stderr, "reconfigure")(encoding="utf-8")

from backend.app.models.document import OCRResult
from backend.app.config.settings import settings
from backend.app.config.ocr_constants import (
    TARGET_WIDTH,
    EASYOCR_LANGUAGES,
    PADDLEOCR_LANG,
    OCR_CONFIDENCE_THRESHOLD,
    DEFAULT_PDF_RENDER_DPI,
    DEFAULT_MAX_PDF_PAGES,
    MAX_RENDER_PIXELS_PER_PAGE,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PDF Exceptions
# ---------------------------------------------------------------------------

class PDFProcessingError(Exception):
    """Base exception for all PDF processing errors."""
    pass


class PDFEncryptedError(PDFProcessingError):
    """Raised when PDF is password protected or encrypted."""
    pass


class PDFEmptyError(PDFProcessingError):
    """Raised when PDF contains zero pages or no readable content."""
    pass


class PDFCorruptError(PDFProcessingError):
    """Raised when PDF file is invalid, corrupt, or truncated."""
    pass


class PDFPageLimitExceededError(PDFProcessingError):
    """Raised when PDF exceeds the maximum allowed page count."""
    pass


class PDFRenderError(PDFProcessingError):
    """Raised when PDF page dimensions exceed safety limits."""
    pass


class OCREngineUnavailableError(Exception):
    """Raised when no OCR engine is installed/loaded and the page has no text layer."""
    pass


# ---------------------------------------------------------------------------
# PDF Rendering and Page Management
# ---------------------------------------------------------------------------

def iter_pdf_pages(
    file_path: str,
    max_pages: Optional[int] = None,
    dpi: Optional[int] = None,
) -> Generator[Tuple[int, Image.Image], None, None]:
    """
    Renders pages of a PDF one by one as PIL RGB images.
    Enforces page limits, dimensions limits, encryption verification, and corruption safety.
    Closes the underlying PDF document reliably on completion or exception.
    """
    if max_pages is None:
        max_pages = getattr(settings, "max_pdf_pages", DEFAULT_MAX_PDF_PAGES)
    if dpi is None:
        dpi = getattr(settings, "pdf_render_dpi", DEFAULT_PDF_RENDER_DPI)

    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        raise PDFEmptyError("PDF file is empty (0 bytes).")

    try:
        doc = fitz.open(file_path)
    except Exception as exc:
        logger.warning("Failed to open PDF '%s': %s", file_path, exc)
        raise PDFCorruptError("Invalid or corrupted PDF file.") from exc

    try:
        if doc.is_encrypted:
            # Attempt empty-string authentication for unauthenticated permissions
            if not doc.authenticate(""):
                raise PDFEncryptedError("PDF is password protected or encrypted and cannot be processed.")

        total_pages = len(doc)
        if total_pages == 0:
            raise PDFEmptyError("PDF contains no pages.")

        if total_pages > max_pages:
            raise PDFPageLimitExceededError(
                f"PDF page count ({total_pages}) exceeds maximum permitted limit ({max_pages})."
            )

        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        for page_idx in range(total_pages):
            try:
                page = doc[page_idx]
                rect = page.rect
                approx_pixels = int(rect.width * zoom) * int(rect.height * zoom)
                if approx_pixels > MAX_RENDER_PIXELS_PER_PAGE:
                    raise PDFRenderError(
                        f"Page {page_idx + 1} dimensions ({int(rect.width * zoom)}x{int(rect.height * zoom)}) "
                        f"exceed the maximum render resolution limit."
                    )
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                yield page_idx + 1, img
            except (PDFRenderError, PDFPageLimitExceededError):
                raise
            except Exception as exc:
                logger.warning("Error rendering PDF page %d: %s", page_idx + 1, exc)
                raise PDFCorruptError(f"Error rendering PDF page {page_idx + 1}.") from exc
    finally:
        doc.close()


def render_pdf_pages(
    file_path: str,
    max_pages: Optional[int] = None,
    dpi: Optional[int] = None,
) -> List[Image.Image]:
    """
    Renders all pages of a PDF into a list of PIL RGB Images up to max_pages.
    """
    return [img for _, img in iter_pdf_pages(file_path, max_pages=max_pages, dpi=dpi)]


def read_pdf_text_layers(file_path: str, max_pages: Optional[int] = None) -> List[str]:
    """
    Returns the embedded (digital) text of each PDF page, in order. Pages that
    are scanned images return an empty string. Applies the same open/encryption
    and page-limit checks as iter_pdf_pages.
    """
    if max_pages is None:
        max_pages = getattr(settings, "max_pdf_pages", DEFAULT_MAX_PDF_PAGES)
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        raise PDFEmptyError("PDF file is empty (0 bytes).")
    try:
        doc = fitz.open(file_path)
    except Exception as exc:
        raise PDFCorruptError("Invalid or corrupted PDF file.") from exc
    try:
        if doc.is_encrypted and not doc.authenticate(""):
            raise PDFEncryptedError("PDF is password protected or encrypted and cannot be processed.")
        if len(doc) == 0:
            raise PDFEmptyError("PDF contains no pages.")
        if len(doc) > max_pages:
            raise PDFPageLimitExceededError(
                f"PDF page count ({len(doc)}) exceeds maximum permitted limit ({max_pages})."
            )
        texts = []
        for page in doc:
            try:
                texts.append((page.get_text("text", sort=True) or "").strip())
            except Exception:
                texts.append("")
        return texts
    finally:
        doc.close()


def _has_usable_text_layer(text: str) -> bool:
    min_chars = getattr(settings, "pdf_text_layer_min_chars", 40)
    return len(re.sub(r"\s+", "", text or "")) >= min_chars


def load_image_or_pdf(file_path: str) -> Image.Image:
    """
    Loads an image or the first page of a PDF as a PIL RGB image.
    Maintained for backward compatibility.
    """
    if file_path.lower().endswith(".pdf"):
        pages = render_pdf_pages(file_path, max_pages=1)
        if not pages:
            raise PDFEmptyError("PDF contains no readable pages.")
        return pages[0]

    return Image.open(file_path).convert("RGB")


# ---------------------------------------------------------------------------
# Image Preprocessing
# ---------------------------------------------------------------------------

def preprocess_pil_image(image: Image.Image) -> Image.Image:
    """
    Applies resolution upscaling, grayscale conversion, and CLAHE contrast enhancement
    to improve OCR accuracy for document images.
    """
    arr = np.array(image)

    # Upscale resolution if needed to improve OCR accuracy for small text,
    # bounded safely so CRAFT / PyTorch does not exceed memory allocation limits.
    h, w = arr.shape[:2]
    max_dim = max(h, w)
    if w < TARGET_WIDTH and max_dim < 1800:
        scale = min(2.5, TARGET_WIDTH / float(w))
        if h * scale > 1800:
            scale = 1800.0 / float(h)
        if scale > 1.05:
            arr = cv2.resize(arr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    # Convert to Grayscale
    if len(arr.shape) == 3:
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    else:
        gray = arr

    # CLAHE contrast enhancement (preserves text structure and prevents letter destruction)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Return RGB image for OCR model engines
    rgb = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)
    return Image.fromarray(rgb)


def preprocess_image(image_or_path: Union[str, Image.Image]) -> Image.Image:
    """
    Preprocesses an image from a filepath or PIL Image object (backward compatible).
    """
    if isinstance(image_or_path, str):
        img = load_image_or_pdf(image_or_path)
    else:
        img = image_or_path
    return preprocess_pil_image(img)


def group_ocr_boxes_into_lines(entries: list[tuple[list[float], str, float]]) -> tuple[list[str], list[float]]:
    """
    entries: list of ( [x_min, y_min, x_max, y_max], text, score )
    Groups OCR bounding boxes that share the same horizontal row into single line strings.
    Returns (raw_lines, confidence_scores).
    """
    valid_entries = []
    for box, text, score in entries:
        if not text or not str(text).strip():
            continue
        valid_entries.append((box, str(text).strip(), float(score) if score is not None else 0.0))

    if not valid_entries:
        return [], []

    # Sort entries by top Y
    valid_entries.sort(key=lambda e: (e[0][1], e[0][0]))

    lines_buckets: list[list[tuple[list[float], str, float]]] = []

    for item in valid_entries:
        box, text, score = item
        y_min, y_max = box[1], box[3]
        y_center = (y_min + y_max) / 2.0
        box_h = max(y_max - y_min, 10.0)

        placed = False
        for bucket in lines_buckets:
            avg_bucket_y = sum((b[0][1] + b[0][3]) / 2.0 for b in bucket) / len(bucket)
            if abs(y_center - avg_bucket_y) < (box_h * 0.65):
                bucket.append(item)
                placed = True
                break
        if not placed:
            lines_buckets.append([item])

    # Sort line buckets top-to-bottom
    lines_buckets.sort(key=lambda b: sum((x[0][1] + x[0][3]) / 2.0 for x in b) / len(b))

    raw_lines: list[str] = []
    confidence_scores: list[float] = []

    for bucket in lines_buckets:
        # Sort left-to-right by x_min
        bucket.sort(key=lambda item: item[0][0])
        line_text = " ".join(item[1] for item in bucket).strip()
        if line_text:
            raw_lines.append(line_text)
            bucket_scores = [item[2] for item in bucket]
            confidence_scores.append(sum(bucket_scores) / len(bucket_scores))

    return raw_lines, confidence_scores


# ---------------------------------------------------------------------------
# OCR Providers
# ---------------------------------------------------------------------------

class OCRProvider(ABC):
    @abstractmethod
    def extract(self, image: Image.Image) -> OCRResult:
        pass


class PaddleOCRProvider(OCRProvider):
    def __init__(self, engine):
        self.engine = engine

    def extract(self, image: Image.Image) -> OCRResult:
        image_array = np.array(image)
        try:
            result = self.engine.ocr(image_array, cls=True)
        except Exception as exc:
            logger.exception("PaddleOCR runtime error: %s", exc)
            result = None

        entries: list[tuple[list[float], str, float]] = []

        if result:
            try:
                for res in result:
                    if not res:
                        continue
                    for line in res:
                        if not line or len(line) < 2:
                            continue
                        box_coords, info = line[0], line[1]
                        if isinstance(info, (list, tuple)) and len(info) >= 2:
                            text = str(info[0])
                            score = float(info[1]) if info[1] is not None else 0.0
                            xs = [pt[0] for pt in box_coords]
                            ys = [pt[1] for pt in box_coords]
                            bbox = [min(xs), min(ys), max(xs), max(ys)]
                            entries.append((bbox, text, score))
            except Exception:
                logger.exception("Error parsing PaddleOCR bounding boxes")

        raw_lines, confidence_scores = group_ocr_boxes_into_lines(entries)
        clean_text = "\n".join(raw_lines).strip()
        average_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        return OCRResult(text=clean_text, confidence=average_confidence, raw_lines=raw_lines)


class EasyOCRProvider(OCRProvider):
    def __init__(self, reader):
        self.reader = reader

    def extract(self, image: Image.Image) -> OCRResult:
        easy_results = self.reader.readtext(np.array(image))
        entries: list[tuple[list[float], str, float]] = []

        for item in easy_results:
            if len(item) >= 3:
                box_coords, text, score = item[:3]
                if text:
                    xs = [pt[0] for pt in box_coords]
                    ys = [pt[1] for pt in box_coords]
                    bbox = [min(xs), min(ys), max(xs), max(ys)]
                    entries.append((bbox, str(text), float(score)))

        raw_lines, confidence_scores = group_ocr_boxes_into_lines(entries)
        clean_text = "\n".join(raw_lines).strip()
        average_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        return OCRResult(text=clean_text, confidence=average_confidence, raw_lines=raw_lines)


class OCRManager:
    def __init__(self):
        self.paddle_provider = None
        self.easy_provider = None
        self._initialized = False
        self._init_lock = threading.Lock()
        # OCR engines are not guaranteed thread-safe; serialize inference per process
        self.inference_lock = threading.Lock()

    def initialize(self):
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            self._load_engines()

    def _load_engines(self):

        logger.info("Initializing OCR Providers...")
        enabled = {e.strip().lower() for e in os.getenv("OCR_ENGINES", "paddleocr,easyocr").split(",") if e.strip()}

        # Load EasyOCR Provider first to avoid MKL library conflict on Windows
        try:
            if "easyocr" not in enabled:
                raise RuntimeError("disabled via OCR_ENGINES")
            import easyocr
            logger.info("Loading EasyOCR Reader model...")
            easy_reader = easyocr.Reader(EASYOCR_LANGUAGES, gpu=False)
            self.easy_provider = EasyOCRProvider(easy_reader)
        except Exception as exc:
            logger.warning("EasyOCR provider could not be loaded: %s", exc)

        # Setup Paddle flags/environments eagerly before import/load
        os.environ['FLAGS_use_mkldnn'] = '0'
        os.environ['FLAGS_enable_mkldnn'] = '0'
        os.environ['FLAGS_mkldnn'] = '0'
        os.environ['PADDLE_DISABLE_FAST_MATH'] = '1'

        # Load PaddleOCR Provider
        try:
            if "paddleocr" not in enabled:
                raise RuntimeError("disabled via OCR_ENGINES")
            import paddle
            try:
                paddle.set_flags({
                    "FLAGS_use_mkldnn": False,
                    "FLAGS_enable_mkldnn": False,
                    "FLAGS_mkldnn": False,
                })
            except Exception:
                logger.warning("Could not set Paddle flags; continuing")

            from paddleocr import PaddleOCR
            logger.info("Loading PaddleOCR models...")
            paddle_engine = PaddleOCR(
                use_angle_cls=True,
                lang=PADDLEOCR_LANG,
                show_log=False,
                use_mkldnn=False,
                use_gpu=False,
            )
            self.paddle_provider = PaddleOCRProvider(paddle_engine)
        except Exception as exc:
            logger.warning("PaddleOCR provider could not be loaded: %s", exc)

        self._initialized = True
        if self.paddle_provider is None and self.easy_provider is None:
            logger.error(
                "No OCR engine could be loaded. Scanned images will only be processed if AI vision "
                "fallback is configured. Install backend/requirements-ocr.txt to enable local OCR."
            )

    def status(self) -> dict:
        return {
            "initialized": self._initialized,
            "paddleocr": self.paddle_provider is not None,
            "easyocr": self.easy_provider is not None,
        }


ocr_manager = OCRManager()


# ---------------------------------------------------------------------------
# Extraction Pipelines
# ---------------------------------------------------------------------------

def extract_text_from_image(image: Image.Image) -> OCRResult:
    """
    Runs the primary OCR engine (PaddleOCR) and fallback (EasyOCR) on a single image.
    """
    ocr_manager.initialize()
    if ocr_manager.paddle_provider is None and ocr_manager.easy_provider is None:
        raise OCREngineUnavailableError(
            "No OCR engine is available (PaddleOCR/EasyOCR failed to load or are not installed). "
            "Install backend/requirements-ocr.txt, or configure an OpenAI key to read images with AI vision."
        )
    preprocessed = preprocess_pil_image(image)
    with ocr_manager.inference_lock:
        return _run_ocr_engines(preprocessed)


def _run_ocr_engines(preprocessed: Image.Image) -> OCRResult:
    # 1. Run PaddleOCR (Primary)
    paddle_result = None
    if ocr_manager.paddle_provider is not None:
        logger.info("Starting PaddleOCR...")
        try:
            paddle_result = ocr_manager.paddle_provider.extract(preprocessed)
            logger.info("PaddleOCR confidence: %.4f", paddle_result.confidence)
        except Exception as exc:
            logger.exception("Error during PaddleOCR execution")
            paddle_result = OCRResult(text="", confidence=0.0, raw_lines=[str(exc)])
    else:
        logger.warning("PaddleOCR provider is not loaded")
        paddle_result = OCRResult(text="", confidence=0.0, raw_lines=["PaddleOCR not available"])

    # 2. Check confidence threshold
    if paddle_result.text and paddle_result.confidence >= OCR_CONFIDENCE_THRESHOLD:
        logger.info("PaddleOCR completed above confidence threshold.")
        return paddle_result

    # 3. Run EasyOCR (Fallback)
    logger.info("PaddleOCR text empty or below threshold (%.2f). Running EasyOCR fallback...", OCR_CONFIDENCE_THRESHOLD)
    easy_result = None
    if ocr_manager.easy_provider is not None:
        try:
            easy_result = ocr_manager.easy_provider.extract(preprocessed)
            logger.info("EasyOCR confidence: %.4f", easy_result.confidence)
        except Exception as exc:
            logger.exception("Error during EasyOCR execution")
            easy_result = OCRResult(text="", confidence=0.0, raw_lines=[str(exc)])
    else:
        logger.warning("EasyOCR provider is not loaded")
        easy_result = OCRResult(text="", confidence=0.0, raw_lines=["EasyOCR not available"])

    # 4. Return best result
    if paddle_result and easy_result:
        return paddle_result if paddle_result.confidence >= easy_result.confidence else easy_result
    return paddle_result or easy_result or OCRResult(text="", confidence=0.0, raw_lines=[])


def extract_text(file_path: str) -> OCRResult:
    """
    Extracts text and confidence scores across all pages of a PDF or image file.
    Preserves page order, marks page boundaries with '--- Page X ---',
    and aggregates confidence across non-empty pages.
    """
    is_pdf = file_path.lower().endswith(".pdf")
    ocr_manager.initialize()

    page_results: List[Tuple[int, OCRResult]] = []

    if is_pdf:
        # Digital PDFs carry exact text; use it directly and only OCR scanned pages
        text_layers = read_pdf_text_layers(file_path)
        engine_missing: Optional[OCREngineUnavailableError] = None
        for page_num, page_img in iter_pdf_pages(file_path):
            layer_text = text_layers[page_num - 1] if page_num - 1 < len(text_layers) else ""
            if _has_usable_text_layer(layer_text):
                lines = [ln.strip() for ln in layer_text.splitlines() if ln.strip()]
                page_results.append((page_num, OCRResult(text="\n".join(lines), confidence=0.99, raw_lines=lines)))
                continue
            try:
                res = extract_text_from_image(page_img)
                page_results.append((page_num, res))
            except OCREngineUnavailableError as exc:
                engine_missing = exc
                page_results.append((page_num, OCRResult(text="", confidence=0.0, raw_lines=[])))
            except Exception as exc:
                logger.warning("OCR failed on PDF page %d: %s", page_num, exc)
                page_results.append((page_num, OCRResult(text="", confidence=0.0, raw_lines=[f"Error: {exc}"])))
        if engine_missing and not any(r.text.strip() for _, r in page_results):
            raise engine_missing
    else:
        try:
            with Image.open(file_path) as img:
                rgb_img = img.convert("RGB")
                res = extract_text_from_image(rgb_img)
                page_results.append((1, res))
        except OCREngineUnavailableError:
            raise
        except Exception as exc:
            logger.warning("Failed to open image file '%s': %s", file_path, exc)
            raise ValueError(f"Unable to process image file: {exc}") from exc

    total_pages = len(page_results)
    if total_pages == 0:
        raise PDFEmptyError("No pages found in document.")

    # Determine if any page had non-empty text
    non_empty_results = [res for _, res in page_results if res.text.strip()]

    if not non_empty_results:
        if is_pdf:
            raise PDFProcessingError(
                f"OCR processing failed or produced no readable text across all {total_pages} pages."
            )
        return OCRResult(text="", confidence=0.0, raw_lines=[])

    # If single image (non-PDF), return single result directly for exact backward compatibility
    if not is_pdf and total_pages == 1:
        return page_results[0][1]

    # Combine multi-page results deterministically
    text_blocks: List[str] = []
    combined_raw_lines: List[str] = []

    for page_num, page_res in page_results:
        page_text = page_res.text.strip()
        if page_text:
            text_blocks.append(f"--- Page {page_num} ---\n{page_text}")
        else:
            text_blocks.append(f"--- Page {page_num} ---")
        combined_raw_lines.append(f"--- Page {page_num} ---")
        combined_raw_lines.extend(page_res.raw_lines)

    combined_text = "\n\n".join(text_blocks).strip()

    # Calculate average confidence across non-empty pages
    valid_confidences = [res.confidence for res in non_empty_results if res.confidence > 0.0]
    aggregate_confidence = (
        sum(valid_confidences) / len(valid_confidences) if valid_confidences else 0.0
    )

    return OCRResult(
        text=combined_text,
        confidence=round(aggregate_confidence, 4),
        raw_lines=combined_raw_lines,
    )
