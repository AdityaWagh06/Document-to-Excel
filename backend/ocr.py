# Compatibility Wrapper for OCR Engine
from backend.app.models.document import OCRResult
from backend.app.ocr.ocr_engine import preprocess_image, extract_text

# Keep extract_text_with_paddleocr alias for compatibility
extract_text_with_paddleocr = extract_text

# Dummy placeholder for removed ocr.space function
def _extract_text_with_ocr_space(image_path: str) -> OCRResult:
    return OCRResult(text="", confidence=0.0, raw_lines=[])
