"""Generates synthetic, clearly-fake sample documents for demo/testing.

Run once with: python sample_data/generate_samples.py
All data below is fictional - fake companies, fake amounts, fake dates.
Three documents match the template-based path (standard_invoice_v1 /
standard_receipt_v1 in config.yaml); one uses a deliberately irregular
layout to demonstrate the AI-extraction fallback path.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT_DIR = Path(__file__).parent


def _write_lines(path: Path, lines: list[str]) -> None:
    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 72
    c.setFont("Helvetica", 11)
    for line in lines:
        c.drawString(72, y, line)
        y -= 18
    c.save()


def invoice_1() -> None:
    _write_lines(
        OUT_DIR / "invoice_acme_supplies.pdf",
        [
            "Acme Supplies Ltd",
            "123 Fictional Ave, Springfield, ST 00000",
            "",
            "INVOICE",
            "Invoice # : INV-10023",
            "Invoice Date : 2026-03-14",
            "Due Date : 2026-04-13",
            "",
            "Bill To: Northwind Traders (fictional)",
            "",
            "Description                Qty   Unit Price   Amount",
            "Office chairs               4      120.00      480.00",
            "Standing desks              2      350.00      700.00",
            "Cable organizers           10        8.50       85.00",
            "",
            "Subtotal : 1265.00",
            "Tax : 101.20",
            "Total : 1366.20",
            "",
            "Thank you for your business. (This is a synthetic sample document.)",
        ],
    )


def invoice_2() -> None:
    _write_lines(
        OUT_DIR / "invoice_brightpath_logistics.pdf",
        [
            "BrightPath Logistics Inc",
            "88 Harbor Road, Rivertown, ST 00001",
            "",
            "INVOICE",
            "Invoice # : INV-20567",
            "Invoice Date : 2026-05-02",
            "Due Date : 2026-06-01",
            "",
            "Bill To: Cedar & Vine Retail Co (fictional)",
            "",
            "Description                Qty   Unit Price   Amount",
            "Freight - regional          1      890.00      890.00",
            "Fuel surcharge               1       45.00       45.00",
            "Warehouse handling           3       22.00       66.00",
            "",
            "Subtotal : 1001.00",
            "Tax : 80.08",
            "Total : 1081.08",
            "",
            "Thank you for your business. (This is a synthetic sample document.)",
        ],
    )


def receipt_1() -> None:
    _write_lines(
        OUT_DIR / "receipt_daily_grind_cafe.pdf",
        [
            "Daily Grind Cafe",
            "45 Bean Street, Portville, ST 00002",
            "",
            "RECEIPT",
            "Receipt # : RCT-4471",
            "Date : 2026-06-19",
            "",
            "Item                          Amount",
            "Large Cold Brew                 4.75",
            "Blueberry Muffin                 3.25",
            "Oat Milk Add-on                  0.60",
            "",
            "Total : 8.60",
            "",
            "Thanks for visiting! (This is a synthetic sample document.)",
        ],
    )


def irregular_layout_document() -> None:
    """Deliberately does NOT match either template - exercises the AI fallback.

    Real-world unstructured documents rarely use clean 'Label: value' lines;
    this mimics that by burying the same facts in prose-like formatting.
    """
    _write_lines(
        OUT_DIR / "irregular_summit_consulting.pdf",
        [
            "Summit Strategy Consulting Group",
            "",
            "Billing summary prepared for our client, dated the 2nd of July, 2026.",
            "Reference code assigned to this engagement: SC-9981-Q3",
            "",
            "Services rendered this period included strategic advisory sessions",
            "(3 sessions at 450.00 each), a market analysis deliverable (750.00),",
            "and follow-up correspondence (complimentary).",
            "",
            "Amount owed before applicable tax comes to 2100.00.",
            "After adding the regional tax of 168.00, the client's final",
            "balance due is 2268.00, payable within 30 days of receipt.",
            "",
            "(This is a synthetic sample document with an intentionally",
            "irregular layout, used to demonstrate the AI extraction path.)",
        ],
    )


def scanned_receipt() -> None:
    """Simulates a phone-photographed receipt: an IMAGE-ONLY PDF with no
    embedded text layer at all. This is what exercises the OCR fallback
    path in document_reader.py / ocr_engine.py - pdfplumber/PyMuPDF will
    find zero extractable text on this page, exactly like a real scan.

    We render the receipt as a bitmap (via PIL), add mild rotation and
    noise to mimic a real phone photo, then embed ONLY that image into a
    PDF page - never using the PDF text-drawing API for this one.
    """
    from PIL import Image, ImageDraw, ImageFont
    import random

    random.seed(42)

    W, H = 900, 1400
    img = Image.new("RGB", (W, H), color=(250, 248, 244))
    draw = ImageDraw.Draw(img)

    try:
        font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
        font_reg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
    except OSError:
        font_bold = ImageFont.load_default()
        font_reg = ImageFont.load_default()

    lines = [
        ("GreenLeaf Grocery Market", font_bold),
        ("", font_reg),
        ("742 Fictional Blvd, Rivertown, ST 00003", font_reg),
        ("", font_reg),
        ("RECEIPT", font_bold),
        ("Receipt # : RCT-8842", font_reg),
        ("Date : 2026-07-05", font_reg),
        ("", font_reg),
        ("Item                          Amount", font_reg),
        ("Organic Bananas (2 lb)          3.40", font_reg),
        ("Whole Wheat Bread               4.25", font_reg),
        ("Free-Range Eggs (dozen)         5.90", font_reg),
        ("Almond Milk (1L)                4.10", font_reg),
        ("", font_reg),
        ("Total : 17.65", font_bold),
        ("", font_reg),
        ("Thanks for shopping with us!", font_reg),
        ("(Synthetic sample - phone-photo simulation)", font_reg),
    ]

    y = 60
    for text, font in lines:
        if text:
            draw.text((60, y), text, fill=(20, 20, 20), font=font)
        y += 46

    # --- mimic a phone photo: slight rotation + per-pixel noise ---
    img = img.rotate(1.4, expand=True, fillcolor=(250, 248, 244))

    noisy = img.copy()
    pixels = noisy.load()
    nw, nh = noisy.size
    for _ in range(35000):
        x = random.randint(0, nw - 1)
        y2 = random.randint(0, nh - 1)
        r, g, b = pixels[x, y2]
        jitter = random.randint(-18, 18)
        pixels[x, y2] = (
            max(0, min(255, r + jitter)),
            max(0, min(255, g + jitter)),
            max(0, min(255, b + jitter)),
        )

    img_path = OUT_DIR / "_scanned_receipt_tmp.png"
    noisy.save(img_path)

    # Embed the bitmap into a PDF page as an IMAGE ONLY - no text layer.
    pdf_path = OUT_DIR / "scanned_receipt_greenleaf_grocery.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    page_w, page_h = letter
    c.drawImage(str(img_path), 0, 0, width=page_w, height=page_h)
    c.save()

    img_path.unlink()


if __name__ == "__main__":
    invoice_1()
    invoice_2()
    receipt_1()
    irregular_layout_document()
    scanned_receipt()
    print(f"Generated 5 synthetic sample documents in {OUT_DIR}")
