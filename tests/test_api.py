"""Tests for src/api/main.py.

test_extract_scanned_document_runs_ocr specifically guards against a real
bug found during manual testing: the API originally read PDF text without
ever invoking the OCR fallback, so scanned documents always failed
regardless of `mode`. Fixed by routing both the CLI/batch processor and
the API through the same `get_text_with_ocr_fallback()` function.
"""

from __future__ import annotations

import pytest

from tests.test_ocr import requires_tesseract


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from src.api.main import app

    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_extract_digital_pdf_via_template_mode(client, sample_data_dir):
    with open(sample_data_dir / "invoice_acme_supplies.pdf", "rb") as fh:
        response = client.post(
            "/extract?mode=template",
            files={"file": ("invoice_acme_supplies.pdf", fh, "application/pdf")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["fields"]["vendor_name"] == "Acme Supplies Ltd"
    assert body["template_id"] == "standard_invoice_v1"


@requires_tesseract
def test_extract_scanned_document_runs_ocr(client, sample_data_dir):
    """Regression guard: the API must OCR scanned PDFs, not just fail them."""
    with open(sample_data_dir / "scanned_receipt_greenleaf_grocery.pdf", "rb") as fh:
        response = client.post(
            "/extract?mode=template",
            files={"file": ("scanned_receipt_greenleaf_grocery.pdf", fh, "application/pdf")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["fields"]["vendor_name"] == "GreenLeaf Grocery Market"
    assert body["fields"]["total_amount"] == 17.65


def test_extract_mode_param_with_stray_whitespace_still_works(client, sample_data_dir):
    """Swagger UI / some clients can pass a trailing space in query params -
    the router must not treat 'auto ' as an invalid mode."""
    with open(sample_data_dir / "invoice_acme_supplies.pdf", "rb") as fh:
        response = client.post(
            "/extract?mode=auto%20",
            files={"file": ("invoice_acme_supplies.pdf", fh, "application/pdf")},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_extract_rejects_non_pdf_content_type(client, sample_data_dir):
    with open(sample_data_dir / "invoice_acme_supplies.pdf", "rb") as fh:
        response = client.post(
            "/extract",
            files={"file": ("invoice.txt", fh, "text/plain")},
        )

    assert response.status_code == 400
