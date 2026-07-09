"""Tests for src/ocr/ocr_engine.py against the synthetic scanned receipt.

This exercises the REAL tesseract binary (not mocked) against a genuinely
image-only PDF (no embedded text layer) - the closest thing to a real
phone-photographed receipt this repo can ship as a portfolio-safe fixture.
If tesseract isn't installed on the machine running the tests, these are
skipped rather than failed, since OCR is an optional system dependency.
"""

from __future__ import annotations

import pytest

from src.document_reader import read_pdf_text, render_page_to_image
from src.models import ExtractionStatus
from src.ocr.ocr_engine import ocr_image_bytes


def _tesseract_available() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


requires_tesseract = pytest.mark.skipif(
    not _tesseract_available(), reason="tesseract binary not installed on this machine"
)


def test_scanned_receipt_has_no_text_layer(sample_data_dir):
    """Confirms the fixture genuinely simulates a scan - zero embedded text."""
    doc = read_pdf_text(sample_data_dir / "scanned_receipt_greenleaf_grocery.pdf")

    assert doc.pages[0].needs_ocr is True
    assert len(doc.pages[0].text.strip()) == 0


@requires_tesseract
def test_ocr_extracts_readable_text_with_line_breaks(sample_data_dir):
    image_bytes = render_page_to_image(sample_data_dir / "scanned_receipt_greenleaf_grocery.pdf", 1)
    result = ocr_image_bytes(image_bytes, language="eng")

    assert "GreenLeaf Grocery Market" in result.text
    assert "\n" in result.text  # line structure preserved, not one flat blob
    assert result.confidence > 0.5


@requires_tesseract
def test_full_pipeline_extracts_scanned_receipt_via_template_after_ocr(config, sample_data_dir):
    """End-to-end: OCR -> template match -> correct fields, using the same
    code path batch_processor.py uses in production."""
    from src.batch_processor import process_single_document
    from src.extractors.router import ExtractionRouter

    router = ExtractionRouter(config)
    result = process_single_document(
        sample_data_dir / "scanned_receipt_greenleaf_grocery.pdf", config, router, mode="template"
    )

    assert result.status == ExtractionStatus.SUCCESS
    assert result.fields["vendor_name"] == "GreenLeaf Grocery Market"
    assert result.fields["invoice_number"] == "RCT-8842"
    assert result.fields["total_amount"] == 17.65
