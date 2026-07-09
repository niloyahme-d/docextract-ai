"""Processes a folder of documents end-to-end.

Per the spec: one bad document must never take down the whole batch.
Every failure is caught here, logged with a human-readable reason (never a
bare stack trace shown to the user), and processing continues.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from tqdm import tqdm

from src.config import AppConfig
from src.document_reader import get_text_with_ocr_fallback
from src.extractors.router import ExtractionRouter
from src.models import ExtractionMethod, ExtractionResult, ExtractionStatus

logger = logging.getLogger("docextract.batch")

SUPPORTED_EXTENSIONS = {".pdf"}


@dataclass
class BatchSummary:
    total: int = 0
    succeeded: int = 0
    partial: int = 0
    failed: int = 0
    results: list[ExtractionResult] = field(default_factory=list)

    def add(self, result: ExtractionResult) -> None:
        self.results.append(result)
        self.total += 1
        if result.status == ExtractionStatus.SUCCESS:
            self.succeeded += 1
        elif result.status == ExtractionStatus.PARTIAL:
            self.partial += 1
        else:
            self.failed += 1


def process_folder(
    input_dir: str | Path,
    config: AppConfig,
    mode: str | None = None,
    show_progress: bool = True,
) -> BatchSummary:
    """Run extraction on every supported document in `input_dir`."""
    input_dir = Path(input_dir)
    files = sorted(
        p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    router = ExtractionRouter(config)
    summary = BatchSummary()

    iterator = tqdm(files, desc="Processing documents", unit="doc") if show_progress else files
    for file_path in iterator:
        result = process_single_document(file_path, config, router, mode)
        summary.add(result)

    return summary


def process_single_document(
    file_path: str | Path,
    config: AppConfig,
    router: ExtractionRouter,
    mode: str | None = None,
) -> ExtractionResult:
    """Process one document. Never raises - all errors are captured in the result."""
    file_path = Path(file_path)
    try:
        text = get_text_with_ocr_fallback(
            file_path,
            ocr_min_confidence=config.ocr_min_confidence,
            ocr_language=config.ocr_language,
        )

        if not text.strip():
            return ExtractionResult(
                source_file=str(file_path),
                method=ExtractionMethod.TEMPLATE,
                status=ExtractionStatus.FAILED,
                errors=["No extractable text found, even after OCR fallback."],
                confidence=0.0,
            )

        return router.extract(text, str(file_path), mode=mode)

    except Exception as exc:  # noqa: BLE001 - batch must survive a single bad file
        logger.exception("Unexpected error processing %s", file_path)
        return ExtractionResult(
            source_file=str(file_path),
            method=ExtractionMethod.TEMPLATE,
            status=ExtractionStatus.FAILED,
            errors=[f"Unexpected error: {exc}"],
            confidence=0.0,
        )
