"""OCR fallback for scanned / image-only documents.

Design goal from the spec: never silently return garbage. Every OCR run
returns a confidence score, and callers are expected to check it against
`config.yaml -> ocr.min_confidence` before trusting the result.

pytesseract requires the `tesseract` binary to be installed on the host
(apt install tesseract-ocr / brew install tesseract). If it's missing,
we raise a clear, actionable error instead of a bare ImportError/OSError -
this is intentional per the "no silent garbage, no bare stack traces" rule.
"""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger("docextract.ocr")


class OCRUnavailableError(RuntimeError):
    """Raised when the tesseract binary isn't installed/reachable."""


@dataclass
class OCRResult:
    text: str
    confidence: float  # 0.0-1.0, averaged across recognized words


def _get_pytesseract():
    try:
        import pytesseract
    except ImportError as exc:  # pragma: no cover - depends on host install
        raise OCRUnavailableError(
            "pytesseract is not installed. Run: pip install pytesseract"
        ) from exc

    tesseract_cmd = os.getenv("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    return pytesseract


def ocr_image_bytes(image_bytes: bytes, language: str = "eng") -> OCRResult:
    """Run OCR on a raw PNG/JPEG image and return text + confidence.

    Raises OCRUnavailableError if tesseract isn't installed on the host -
    callers should catch this and report it as a per-document error rather
    than crashing the whole batch.
    """
    pytesseract = _get_pytesseract()

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise OCRUnavailableError("Pillow is not installed. Run: pip install Pillow") from exc

    try:
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as exc:  # noqa: BLE001
        raise OCRUnavailableError(f"Could not decode image for OCR: {exc}") from exc

    try:
        data = pytesseract.image_to_data(
            image, lang=language, output_type=pytesseract.Output.DICT
        )
    except Exception as exc:  # noqa: BLE001 - tesseract binary missing/misconfigured
        raise OCRUnavailableError(
            f"OCR failed - is the tesseract binary installed and on PATH? ({exc})"
        ) from exc

    # Reconstruct line breaks from tesseract's block/paragraph/line indices
    # instead of flattening every word onto one line. This matters for
    # anything downstream that relies on line position (e.g. the
    # template extractor's "first_line" strategy for vendor name) -
    # a single flat string of OCR text would silently break that.
    n = len(data.get("text", []))
    lines: dict[tuple[int, int, int], list[str]] = {}
    line_order: list[tuple[int, int, int]] = []
    confidences: list[float] = []

    for i in range(n):
        word = data["text"][i]
        if not word.strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        if key not in lines:
            lines[key] = []
            line_order.append(key)
        lines[key].append(word)

        conf = data["conf"][i]
        if conf not in ("-1", -1):
            confidences.append(float(conf))

    text = "\n".join(" ".join(lines[key]) for key in line_order)
    avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0

    return OCRResult(text=text, confidence=avg_conf)
