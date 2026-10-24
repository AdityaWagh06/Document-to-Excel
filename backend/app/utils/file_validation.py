"""Upload content checks shared by the upload, WhatsApp and simulator endpoints."""
from typing import Optional

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


def detect_file_type(header: bytes) -> Optional[str]:
    """Returns the canonical extension for supported magic bytes, or None."""
    if not header:
        return None
    if header.startswith(b"%PDF-"):
        return ".pdf"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return ".webp"
    return None


def magic_matches_extension(header: bytes, suffix: str) -> bool:
    detected = detect_file_type(header)
    if detected is None:
        return False
    if suffix in (".jpg", ".jpeg"):
        return detected == ".jpg"
    return detected == suffix
