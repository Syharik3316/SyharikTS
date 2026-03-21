"""Local OCR transcription for raster images (Tesseract)."""

import base64
import os
from io import BytesIO


def _read_psm() -> int:
    raw = (os.getenv("OCR_PSM") or "").strip()
    if not raw:
        return 6
    try:
        val = int(raw)
        return val if 0 <= val <= 13 else 6
    except ValueError:
        return 6


def _normalize_ocr_text(text: str) -> str:
    # Keep line breaks for downstream prompt quality, but trim noisy spacing.
    lines = [ln.strip() for ln in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join([ln for ln in lines if ln])


def transcribe_image_with_ocr(contents: bytes, file_kind: str) -> str:
    if not contents:
        return ""
    import pytesseract
    from PIL import Image

    lang = (os.getenv("OCR_LANG") or "rus+eng").strip()
    psm = _read_psm()
    config = f"--oem 1 --psm {psm}"
    if file_kind == "tiff":
        # TIFF scans are often sparse forms where this psm is usually more stable.
        config = f"--oem 1 --psm {(os.getenv('OCR_FALLBACK_PSM') or '4').strip() or '4'}"

    with Image.open(BytesIO(contents)) as img:
        text = pytesseract.image_to_string(img, lang=lang, config=config)
    return _normalize_ocr_text(text)


def transcript_utf8_base64_for_prompt(text: str) -> str:
    """ASCII base64 of UTF-8 transcript for embedding in TS via decodeBase64."""
    return base64.b64encode(text.encode("utf-8")).decode("ascii")
