"""Common interface for the template-based and AI-based extraction engines.

Both `TemplateExtractor` and `AIExtractor` implement `extract(text) -> ExtractionResult`
so `router.py` can call either one interchangeably. This is what makes the
hybrid routing decision (see docs/architecture.md) a simple if/else instead
of two totally separate code paths downstream.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.config import AppConfig
from src.models import ExtractionResult


class BaseExtractor(ABC):
    """Extraction engines take document text and the field config, and
    return a normalized ExtractionResult."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    @abstractmethod
    def extract(self, text: str, source_file: str) -> ExtractionResult:
        """Extract configured fields from `text`.

        Implementations must never raise for "normal" extraction failures
        (missing field, unparseable date, etc.) - those should be reflected
        in `ExtractionResult.status` and `.errors` instead. Raising is
        reserved for genuinely unexpected/unrecoverable errors, which the
        batch processor will catch and log per-document.
        """
        raise NotImplementedError
