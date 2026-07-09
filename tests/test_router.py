"""Tests for src/extractors/router.py - the hybrid routing decision.

The AI provider is stubbed out here so these tests run without any API
keys or network access - they verify the *routing logic*, not the LLM
itself (that's covered separately by manual/integration testing since it
requires live credentials).
"""

from __future__ import annotations

from src.document_reader import read_pdf_text
from src.extractors.ai_providers import LLMProvider
from src.extractors.router import ExtractionRouter
from src.models import ExtractionMethod


class StubProvider(LLMProvider):
    """Returns a fixed, valid response - simulates a successful AI call."""

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "vendor_name": "Summit Strategy Consulting Group",
            "invoice_number": "SC-9981-Q3",
            "invoice_date": "2026-07-02",
            "total_amount": 2268.00,
            "subtotal": 2100.00,
            "tax_amount": 168.00,
        }


def test_auto_mode_uses_template_for_well_matched_document(config, sample_data_dir):
    router = ExtractionRouter(config)
    doc = read_pdf_text(sample_data_dir / "invoice_acme_supplies.pdf")

    result = router.extract(doc.full_text, "invoice_acme_supplies.pdf", mode="auto")

    assert result.method == ExtractionMethod.TEMPLATE
    assert result.template_id == "standard_invoice_v1"


def test_auto_mode_falls_back_to_ai_for_irregular_document(config, sample_data_dir):
    router = ExtractionRouter(config)
    router.ai_extractor._provider = StubProvider()  # inject stub, skip real API call

    doc = read_pdf_text(sample_data_dir / "irregular_summit_consulting.pdf")
    result = router.extract(doc.full_text, "irregular_summit_consulting.pdf", mode="auto")

    assert result.method == ExtractionMethod.AI
    assert result.fields["vendor_name"] == "Summit Strategy Consulting Group"
    assert result.fields["total_amount"] == 2268.00


def test_forced_template_mode_ignores_ai_path(config, sample_data_dir):
    router = ExtractionRouter(config)
    doc = read_pdf_text(sample_data_dir / "invoice_acme_supplies.pdf")

    result = router.extract(doc.full_text, "invoice_acme_supplies.pdf", mode="template")

    assert result.method == ExtractionMethod.TEMPLATE


def test_forced_ai_mode_skips_template_even_when_it_would_match(config, sample_data_dir):
    router = ExtractionRouter(config)
    router.ai_extractor._provider = StubProvider()

    doc = read_pdf_text(sample_data_dir / "invoice_acme_supplies.pdf")
    result = router.extract(doc.full_text, "invoice_acme_supplies.pdf", mode="ai")

    assert result.method == ExtractionMethod.AI
