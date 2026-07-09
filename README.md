# DocExtract AI

**Turns invoices, receipts, and scanned documents into structured Excel/CSV/Google Sheets data — using template rules where possible and AI extraction where necessary, so you're not paying for an LLM call on every single document.**

![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-informational)
![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC)
![Status](https://img.shields.io/badge/status-active-2E8B57)

> **This is a self-initiated portfolio project, not a client-commissioned build.** It was built to demonstrate the document-extraction approach offered as a paid service — every feature below is implemented and tested, not a sales claim.

---

## What this solves

Small businesses and freelancers who process invoices/receipts by hand (or pay per-document SaaS tools) need a way to turn a folder of PDFs into a spreadsheet without either (a) hand-typing every field, or (b) sending every single document to an LLM and paying for it. DocExtract AI routes each document down the cheapest path that will still get it right — see [Why hybrid extraction](#why-hybrid-extraction) below.

## Demo

*(Screen recording placeholder — run the Quick Start below locally, then record a 20-30s clip of `sample_data/` going in and `output/results.xlsx` coming out. Suggested crop: terminal command → progress bar → opened spreadsheet.)*

`[Coming soon]` — live hosted demo link (Streamlit Cloud / Render), if deployed.

## Why hybrid extraction

Most tools force a choice: brittle-but-free regex parsing, or flexible-but-costly LLM calls on every document. DocExtract AI's router tries a fast, zero-cost **template match** first (regex/positional rules defined in `config.yaml`), and only falls back to an **AI-based extraction** call when no template matches the document's layout, or the match confidence is too low to trust. In practice this means a recurring vendor's invoices cost nothing to process after the first template is written, while genuinely novel document layouts still get extracted correctly via the LLM.

Full technical write-up, including the confidence-scoring formula and a worked example against the sample documents: **[docs/architecture.md](docs/architecture.md)**.

## Features

- **Hybrid extraction engine** — template-based (regex/positional, via `pdfplumber`/`PyMuPDF`) with AI-based fallback (OpenAI, Anthropic Claude, or Google Gemini — provider chosen via one env var)
- **OCR fallback** for scanned/image-only PDFs, with a confidence gate so low-quality scans get flagged instead of silently returning bad data. Requires the `tesseract` system binary (see [OCR setup](#ocr-setup) below) — the `pytesseract` Python package alone isn't enough.
- **Configurable field mapping** — add/remove extracted fields by editing `config.yaml`, no code changes needed
- **Three output formats** — Excel (`.xlsx`), CSV, and Google Sheets (optional, via service account)
- **Batch processing** — point it at a folder, get a progress bar and a per-document success/partial/failed summary; one bad file never crashes the run
- **REST API** — `POST /extract` (FastAPI) accepts a document upload and returns structured JSON, for programmatic/integration use
- **Real test coverage** — 22 pytest tests running against the actual synthetic sample documents, including OCR tests that run the real `tesseract` binary against a genuinely image-only PDF, not mocked-out fixtures

## Quick start

Requires Python 3.11+.

```bash
git clone https://github.com/<your-username>/docextract-ai.git
cd docextract-ai

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Template-mode extraction (used below) needs no API key at all.
# To try AI-mode extraction, add ONE provider key to .env, e.g.:
#   AI_PROVIDER=anthropic
#   ANTHROPIC_API_KEY=sk-ant-...

# Run against the bundled synthetic sample documents
python -m src.cli --input sample_data --output-format excel --output output/results.xlsx
```

Open `output/results.xlsx` — you'll see one row per document, with non-successful rows highlighted for easy review.

To also see the AI fallback path in action (extracts the intentionally irregular sample document that no template matches):

```bash
python -m src.cli --input sample_data --mode auto --output-format excel --output output/results.xlsx
```

### Run the API locally

```bash
uvicorn src.api.main:app --reload
```

Then visit `http://127.0.0.1:8000/docs` for interactive Swagger docs, or:

```bash
curl -X POST "http://127.0.0.1:8000/extract?mode=template" \
  -F "file=@sample_data/invoice_acme_supplies.pdf"
```

### Run the tests

```bash
pytest tests/ -v
```

### OCR setup

OCR needs the `tesseract` binary installed separately — it's a C++ program, not something `pip install` can provide:

- **Windows**: install via the [UB Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki), then set `TESSERACT_CMD` in `.env` to the install path (typically `C:\Program Files\Tesseract-OCR\tesseract.exe`)
- **macOS**: `brew install tesseract`
- **Linux**: `sudo apt install tesseract-ocr`

Without it, documents that need OCR return a clear `OCRUnavailableError`-based message in `.errors` — never silently wrong data.

## Sample data

`sample_data/` contains **5 synthetic, clearly fictional** documents (`generate_samples.py` regenerates them) — fake company names, fake amounts, fake dates. Three use a consistent invoice/receipt layout to demonstrate the template path; one uses a deliberately irregular, prose-style layout to demonstrate the AI fallback path; one (`scanned_receipt_greenleaf_grocery.pdf`) is a genuinely **image-only PDF with no embedded text layer** — a simulated phone photo (rotated, with pixel noise) — to exercise the real OCR fallback path end-to-end. `sample_data/expected_output.csv` is the real output of an actual run against these documents in `template` mode (not hand-written) — the irregular document shows `partial`/low-confidence there by design, since resolving it requires the AI path.

No real client or personal data is used anywhere in this repository.

## Configuration

All extractable fields and template layouts live in `config.yaml` — see the comments in that file for the schema. This is intentionally editable by a non-developer: adding a new field to extract, or a new template layout to match against, doesn't require touching any Python code.

## Project structure

```
docextract-ai/
├── README.md
├── LICENSE
├── requirements.txt
├── .env.example
├── config.yaml
├── sample_data/          synthetic sample docs + real (non-fabricated) expected output
├── src/
│   ├── extractors/       template-based + AI-based engines, provider-agnostic client, router
│   ├── ocr/               OCR fallback with confidence gating
│   ├── output_writers/    excel, csv, google sheets
│   ├── api/                FastAPI REST endpoint
│   ├── document_reader.py  PDF text extraction (pdfplumber + PyMuPDF)
│   ├── batch_processor.py  folder processing, per-document error isolation
│   ├── config.py           config.yaml loader/validator
│   ├── models.py           shared data models
│   └── cli.py               command-line entry point
├── tests/                 pytest suite (19 tests, runs against real sample data)
└── docs/
    └── architecture.md    hybrid routing rationale + worked example
```

## What's not included (by design)

- No Docker/Kubernetes orchestration — this is a focused tool, not a platform. See the build brief's explicit scope decision.
- No fabricated accuracy benchmarks — `sample_data/expected_output.csv` is a real run's output, and any accuracy claim you make from this repo should come from testing against your own documents, not from a number in this README.
- Google Sheets output is optional/pluggable and requires you to supply your own service-account credentials — it's not wired into the demo by default.

## License

MIT — see [LICENSE](LICENSE).
