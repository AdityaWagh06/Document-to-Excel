import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
from PIL import Image
import requests

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    text: str
    confidence: float
    raw_lines: list[str]


def preprocess_image(image_path: str) -> Image.Image:
    # Use OpenCV for stronger preprocessing: resize, denoise, adaptive threshold
    pil = Image.open(image_path).convert("RGB")
    arr = np.array(pil)

    # Resize up to improve OCR accuracy for small text
    h, w = arr.shape[:2]
    target_w = 1600
    if w < target_w:
        scale = target_w / w
        arr = cv2.resize(arr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    # Convert to grayscale
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    # Denoise while preserving edges
    denoised = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

    # Adaptive threshold to handle uneven lighting
    th = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 10)

    # Slight sharpening
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(th, -1, kernel)

    return Image.fromarray(sharpened)


def _extract_text_with_ocr_space(image_path: str) -> OCRResult:
    try:
        with open(image_path, "rb") as handle:
            response = requests.post(
                "https://api.ocr.space/parse/image",
                files={"file": handle},
                data={"apikey": "helloworld", "language": "eng"},
                timeout=45,
            )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return OCRResult(text="", confidence=0.0, raw_lines=[str(exc)])

    parsed = payload.get("ParsedResults") or []
    if not parsed:
        return OCRResult(text="", confidence=0.0, raw_lines=[])

    text = parsed[0].get("ParsedText", "").strip()
    lines = [line for line in text.splitlines() if line.strip()]
    return OCRResult(text=text, confidence=0.5 if text else 0.0, raw_lines=lines)


def extract_text_with_paddleocr(image_path: str, paddleocr_instance: Optional[object] = None) -> OCRResult:
    import os
    os.environ['FLAGS_use_mkldnn'] = '0'
    os.environ['FLAGS_enable_mkldnn'] = '0'
    os.environ['FLAGS_mkldnn'] = '0'
    os.environ['PADDLE_DISABLE_FAST_MATH'] = '1'
    
    try:
        import easyocr
    except ImportError:
        easyocr = None

    image = preprocess_image(image_path)
    # paddleocr expects BGR image arrays; preprocess returns single-channel image
    image_array = cv2.cvtColor(np.array(image), cv2.COLOR_GRAY2BGR)

    if easyocr is not None:
        reader = easyocr.Reader(["en"], gpu=False)
        easy_results = reader.readtext(np.array(image))
        raw_lines: list[str] = []
        confidence_scores: list[float] = []
        for item in (entry for entry in easy_results if len(entry) >= 3):
            _, text, score = item[:3]
            if text:
                raw_lines.append(text.strip())
                confidence_scores.append(float(score))
        clean_text = "\n".join(raw_lines).strip()
        average_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        if clean_text:
            logger.info("EasyOCR extracted %s characters with avg confidence %.4f", len(clean_text), average_confidence)
            return OCRResult(text=clean_text, confidence=average_confidence, raw_lines=raw_lines)

        ocr_space_result = _extract_text_with_ocr_space(image_path)
        if ocr_space_result.text:
            logger.info("OCR.Space extracted %s characters", len(ocr_space_result.text))
            return ocr_space_result

    ocr_space_result = _extract_text_with_ocr_space(image_path)
    if ocr_space_result.text:
        logger.info("OCR.Space extracted %s characters", len(ocr_space_result.text))
        return ocr_space_result

    try:
        import paddle
        try:
            paddle.set_flags({
                "FLAGS_use_mkldnn": False,
                "FLAGS_enable_mkldnn": False,
                "FLAGS_mkldnn": False,
            })
        except Exception:
            logger.warning("Could not set Paddle flags; continuing without them")

        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError("PaddleOCR is not installed") from exc

    ocr = paddleocr_instance or PaddleOCR(
        use_angle_cls=True,
        lang="en",
        show_log=False,
        use_mkldnn=False,
        use_gpu=False,
    )
    try:
        result = ocr.ocr(image_array, cls=True)
    except RuntimeError as exc:
        logger.exception("PaddleOCR runtime error")
        result = None

    raw_lines: list[str] = []
    confidence_scores: list[float] = []

    # PaddleOCR may return different structures; handle common shapes robustly
    if result:
        try:
            for entry in result:
                if not entry:
                    continue
                # common format: [box, (text, score)]
                if isinstance(entry, (list, tuple)) and len(entry) >= 2 and isinstance(entry[1], (list, tuple)):
                    txt = entry[1][0]
                    score = float(entry[1][1]) if entry[1][1] is not None else 0.0
                    if txt:
                        raw_lines.append(str(txt).strip())
                        confidence_scores.append(score)
                else:
                    # nested or alternative format
                    for sub in entry:
                        if not sub or len(sub) < 2:
                            continue
                        info = sub[1]
                        if isinstance(info, (list, tuple)) and len(info) >= 2:
                            txt = info[0]
                            score = float(info[1]) if info[1] is not None else 0.0
                            if txt:
                                raw_lines.append(str(txt).strip())
                                confidence_scores.append(score)
        except Exception:
            logger.exception("Error parsing PaddleOCR result; falling back to raw string capture")
            # best-effort flatten
            for block in result or []:
                try:
                    text = str(block)
                    raw_lines.append(text)
                except Exception:
                    continue

    clean_text = "\n".join([l for l in raw_lines if l]).strip()
    average_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
    logger.info("OCR extracted %s lines with avg confidence %.4f", len(raw_lines), average_confidence)
    return OCRResult(text=clean_text, confidence=average_confidence, raw_lines=raw_lines)
