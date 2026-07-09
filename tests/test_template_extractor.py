"""Tests for src/extractors/template_extractor.py.

Runs against the real synthetic sample PDFs in sample_data/ - these are
the same documents used in the demo, so a passing test suite here is a
direct guarantee the demo will work.
"""

from __future__ import annotations

from src.document_reader import read_pdf_text
from src.extractors.template_extractor import TemplateExtractor
from src.models import ExtractionStatus


def _extract(config, sample_data_dir, filename):
    extractor = TemplateExtractor(config)
    doc = read_pdf_text(sample_data_dir / filename)
    return extractor.extract(doc.full_text, filename)


def test_standard_invoice_matches_and_extracts_required_fields(config, sample_data_dir):
    result = _extract(config, sample_data_dir, "invoice_acme_supplies.pdf")

    assert result.status == ExtractionStatus.SUCCESS
    assert result.template_id == "standard_invoice_v1"
    assert result.fields["vendor_name"] == "Acme Supplies Ltd"
    assert result.fields["invoice_number"] == "INV-10023"
    assert result.fields["invoice_date"] == "2026-03-14"
    assert result.fields["total_amount"] == 1366.20


def test_second_invoice_also_matches_same_template(config, sample_data_dir):
    result = _extract(config, sample_data_dir, "invoice_brightpath_logistics.pdf")

    assert result.status == ExtractionStatus.SUCCESS
    assert result.template_id == "standard_invoice_v1"
    assert result.fields["total_amount"] == 1081.08


def test_receipt_matches_receipt_template(config, sample_data_dir):
    result = _extract(config, sample_data_dir, "receipt_daily_grind_cafe.pdf")

    assert result.status == ExtractionStatus.SUCCESS
    assert result.template_id == "standard_receipt_v1"
    assert result.fields["total_amount"] == 8.60


def test_irregular_document_fails_template_matching(config, sample_data_dir):
    """This document has no 'Label: value' structure - the template path
    should NOT confidently match it. This is what should trigger the AI
    fallback in `auto` mode (see test_router behavior in integration)."""
    result = _extract(config, sample_data_dir, "irregular_summit_consulting.pdf")

    assert result.status in (ExtractionStatus.PARTIAL, ExtractionStatus.FAILED)
    assert result.confidence < config.auto_fallback_confidence


def test_currency_fields_are_cast_to_float(config, sample_data_dir):
    result = _extract(config, sample_data_dir, "invoice_acme_supplies.pdf")

    assert isinstance(result.fields["total_amount"], float)
    assert isinstance(result.fields["subtotal"], float)


def test_date_fields_are_normalized_iso_format(config, sample_data_dir):
    result = _extract(config, sample_data_dir, "invoice_acme_supplies.pdf")

    assert result.fields["invoice_date"] == "2026-03-14"
    assert result.fields["due_date"] == "2026-04-13"
