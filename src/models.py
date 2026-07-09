"""Shared data models for DocExtract AI.

Every extractor (template-based or AI-based) returns an `ExtractionResult`,
regardless of which path produced it. This is what makes the two paths
swappable behind a single interface - see `src/extractors/router.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ExtractionMethod(str, Enum):
    """Which engine produced a given extraction."""

    TEMPLATE = "template"
    AI = "ai"


class ExtractionStatus(str, Enum):
    """Outcome of processing a single document."""

    SUCCESS = "success"
    PARTIAL = "partial"       # some required fields missing / low confidence
    FAILED = "failed"         # unrecoverable error


@dataclass
class LineItem:
    """A single line item row on an invoice/receipt."""

    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None


@dataclass
class ExtractionResult:
    """Normalized output of extracting fields from one document.

    Attributes:
        source_file: Path to the original document.
        method: Which extraction engine produced this result.
        status: Overall outcome for this document.
        fields: Extracted field name -> value pairs (matches config.yaml `fields`).
        confidence: 0.0-1.0 estimate of extraction reliability.
        errors: Human-readable reasons for partial/failed status. Never a raw
            stack trace - this is meant to be read by a non-developer.
        template_id: If method == TEMPLATE, which template matched.
        raw_text: The raw text the extraction was performed on (useful for debugging).
    """

    source_file: str
    method: ExtractionMethod
    status: ExtractionStatus = ExtractionStatus.SUCCESS
    fields: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    errors: list[str] = field(default_factory=list)
    template_id: Optional[str] = None
    raw_text: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (used by the API and output writers)."""
        return {
            "source_file": self.source_file,
            "method": self.method.value,
            "status": self.status.value,
            "fields": self.fields,
            "confidence": round(self.confidence, 3),
            "errors": self.errors,
            "template_id": self.template_id,
        }
