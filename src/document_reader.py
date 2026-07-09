"""Reads raw text out of a source document.

This is the layer both the template extractor and the AI extractor sit on
top of. It decides, per page, whether a PDF has a real text layer
(digitally generated) or is image-only (scanned) and needs OCR.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber

logger = logging.getLogger("docextract.reader")

# A page with fewer than this many extracted characters is treated as
# "no usable text layer" and routed to OCR instead.
MIN_CHARS_FOR_TEXT_LAYER = 20


@dataclass
class PageText:
    page_number: int
    text: str
    needs_ocr: bool


@dataclass
class DocumentText:
    source_file: str
    pages: list[PageText]

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)

    @property
    def any_page_needs_ocr(self) -> bool:
        return any(p.needs_ocr for p in self.pages)


def read_pdf_text(path: str | Path) -> DocumentText:
    """Extract text from every page of a PDF using pdfplumber.

    Falls back to PyMuPDF if pdfplumber raises on a malformed file, since
    the two libraries have different parsing tolerances.

    Pages with too little extractable text are flagged `needs_ocr=True`
    rather than silently returned empty - the caller (batch_processor /
    ai_extractor) decides whether to run OCR on those pages.
    """
    path = Path(path)
    try:
        return _read_with_pdfplumber(path)
    except Exception as exc:  # noqa: BLE001 - deliberately broad, we fall back
        logger.warning("pdfplumber failed on %s (%s), retrying with PyMuPDF", path, exc)
        return _read_with_pymupdf(path)


def _read_with_pdfplumber(path: Path) -> DocumentText:
    pages: list[PageText] = []
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append(
                PageText(
                    page_number=i,
                    text=text,
                    needs_ocr=len(text.strip()) < MIN_CHARS_FOR_TEXT_LAYER,
                )
            )
    return DocumentText(source_file=str(path), pages=pages)


def _read_with_pymupdf(path: Path) -> DocumentText:
    pages: list[PageText] = []
    doc = fitz.open(str(path))
    try:
        for i, page in enumerate(doc, start=1):
            text = page.get_text() or ""
            pages.append(
                PageText(
                    page_number=i,
                    text=text,
                    needs_ocr=len(text.strip()) < MIN_CHARS_FOR_TEXT_LAYER,
                )
            )
    finally:
        doc.close()
    return DocumentText(source_file=str(path), pages=pages)


def render_page_to_image(path: str | Path, page_number: int, zoom: float = 2.0):
    """Render a single page to a PIL-compatible image for OCR.

    `page_number` is 1-indexed to match `PageText.page_number`.
    """
    doc = fitz.open(str(path))
    try:
        page = doc[page_number - 1]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png")
    finally:
        doc.close()


def get_text_with_ocr_fallback(path: str | Path, ocr_min_confidence: float = 0.6, ocr_language: str = "eng") -> str:
    """Read a PDF's text, running OCR on any page with no usable text layer.

    This is the single source of truth for "get me usable text out of this
    document" - used by BOTH the batch processor and the API endpoint, so
    a scanned document behaves identically whether it's processed via CLI
    or uploaded through /extract. Previously the API skipped OCR entirely,
    which meant scanned PDFs always failed there regardless of mode - this
    function is what fixes that gap.

    If tesseract isn't installed, falls back to whatever text-layer content
    exists rather than raising - callers see this reflected naturally as
    low/failed confidence, not a crash.
    """
    import logging

    from src.ocr.ocr_engine import OCRUnavailableError, ocr_image_bytes

    logger = logging.getLogger("docextract.reader")

    doc_text = read_pdf_text(path)
    if not doc_text.any_page_needs_ocr:
        return doc_text.full_text

    combined = []
    for page in doc_text.pages:
        if not page.needs_ocr:
            combined.append(page.text)
            continue
        try:
            image_bytes = render_page_to_image(path, page.page_number)
            ocr_result = ocr_image_bytes(image_bytes, language=ocr_language)
            if ocr_result.confidence < ocr_min_confidence:
                logger.warning(
                    "OCR confidence %.2f below threshold %.2f for %s page %d",
                    ocr_result.confidence,
                    ocr_min_confidence,
                    path,
                    page.page_number,
                )
            combined.append(ocr_result.text)
        except OCRUnavailableError as exc:
            logger.warning("OCR unavailable for %s: %s", path, exc)
            combined.append(page.text)

    return "\n".join(combined)
