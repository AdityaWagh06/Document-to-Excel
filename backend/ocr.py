import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageOps

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    text: str
    confidence: float
    raw_lines: list[str]


def preprocess_image(image_path: str) -> Image.Image:
    image = Image.open(image_path).convert("RGB")
    grayscale = ImageOps.grayscale(image)
    enhanced = ImageOps.autocontrast(grayscale)
    sharpened = enhanced.filter(ImageFilter.SHARPEN)
    thresholded = sharpened.point(lambda pixel: 255 if pixel > 160 else 0)
    return thresholded


def extract_text_with_paddleocr(image_path: str, paddleocr_instance: Optional[object] = None) -> OCRResult:
    import os
    os.environ['FLAGS_use_mkldnn'] = '0'
    os.environ['PADDLE_DISABLE_FAST_MATH'] = '1'
    
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError("PaddleOCR is not installed") from exc

    image = preprocess_image(image_path)
    image_array = cv2.cvtColor(np.array(image), cv2.COLOR_GRAY2BGR)

    ocr = paddleocr_instance or PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    result = ocr.ocr(image_array, cls=True)

    raw_lines: list[str] = []
    confidence_scores: list[float] = []

    for block in result or []:
        for line in block or []:
            text = line[1][0] if len(line) > 1 and line[1] else ""
            score = float(line[1][1]) if len(line) > 1 and line[1] else 0.0
            if text:
                raw_lines.append(text.strip())
                confidence_scores.append(score)

    clean_text = "\n".join(raw_lines).strip()
    average_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
    logger.info("OCR extracted %s characters with avg confidence %.4f", len(clean_text), average_confidence)
    return OCRResult(text=clean_text, confidence=average_confidence, raw_lines=raw_lines)
