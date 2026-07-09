"""Minimal REST API: upload a document, get structured JSON back.

Run locally with:
    uvicorn src.api.main:app --reload

This is the "API integration" mode referenced in the project's Premium
tier - it's a real, working endpoint, not a placeholder.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from src.config import AppConfig
from src.document_reader import get_text_with_ocr_fallback
from src.extractors.router import ExtractionRouter
from src.models import ExtractionMethod, ExtractionResult, ExtractionStatus

load_dotenv()
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="DocExtract AI",
    description="Upload an invoice/receipt PDF, get back structured JSON.",
    version="0.1.0",
)

_config: AppConfig | None = None
_router: ExtractionRouter | None = None


def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = AppConfig("config.yaml")
    return _config


def get_router() -> ExtractionRouter:
    global _router
    if _router is None:
        _router = ExtractionRouter(get_config())
    return _router


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/extract")
async def extract_document(
    file: UploadFile = File(...),
    mode: str = Query(default=None, description="template | ai | auto (defaults to config.yaml)"),
) -> JSONResponse:
    """Accept a single PDF upload and return extracted fields as JSON."""
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    config = get_config()
    router = get_router()
    mode = mode.strip() if mode else None

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / file.filename
        with tmp_path.open("wb") as fh:
            shutil.copyfileobj(file.file, fh)

        try:
            text = get_text_with_ocr_fallback(
                tmp_path,
                ocr_min_confidence=config.ocr_min_confidence,
                ocr_language=config.ocr_language,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"Could not read PDF: {exc}") from exc

        if not text.strip():
            result = ExtractionResult(
                source_file=file.filename,
                method=ExtractionMethod.TEMPLATE,
                status=ExtractionStatus.FAILED,
                errors=["No extractable text found, even after OCR fallback."],
                confidence=0.0,
            )
        else:
            try:
                result = router.extract(text, file.filename, mode=mode)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    status_code = 200 if result.status != ExtractionStatus.FAILED else 422
    return JSONResponse(status_code=status_code, content=result.to_dict())
