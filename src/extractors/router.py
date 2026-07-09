"""The hybrid routing decision - DocExtract AI's core differentiator.

Three modes (set in config.yaml -> routing.default_mode, overridable per
call):
  template  - always use TemplateExtractor. Fast/cheap, fails if no layout matches.
  ai        - always use AIExtractor. Handles anything, costs an LLM call.
  auto      - try TemplateExtractor first. If it matches a known layout AND
              clears the confidence bar, use its result. Otherwise fall
              back to AIExtractor. This gives near-zero cost on the
              documents you see repeatedly (e.g. one client's fixed invoice
              format) while still handling one-off/unusual documents
              correctly.

See docs/architecture.md for the full rationale and a worked example.
"""

from __future__ import annotations

import logging

from src.config import AppConfig
from src.extractors.ai_extractor import AIExtractor
from src.extractors.base import BaseExtractor
from src.extractors.template_extractor import TemplateExtractor
from src.models import ExtractionMethod, ExtractionResult

logger = logging.getLogger("docextract.router")

VALID_MODES = {"template", "ai", "auto"}


class ExtractionRouter:
    """Entry point used by batch_processor.py and the API layer."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.template_extractor: BaseExtractor = TemplateExtractor(config)
        self.ai_extractor: BaseExtractor = AIExtractor(config)

    def extract(self, text: str, source_file: str, mode: str | None = None) -> ExtractionResult:
        mode = (mode or self.config.default_mode).strip().lower()
        if mode not in VALID_MODES:
            raise ValueError(f"Unknown extraction mode '{mode}'. Choose from {VALID_MODES}.")

        if mode == "template":
            return self.template_extractor.extract(text, source_file)

        if mode == "ai":
            return self.ai_extractor.extract(text, source_file)

        # auto: try template first, fall back to AI on no-match or low confidence
        template_result = self.template_extractor.extract(text, source_file)
        if (
            template_result.method == ExtractionMethod.TEMPLATE
            and template_result.template_id is not None
            and template_result.confidence >= self.config.auto_fallback_confidence
        ):
            logger.info(
                "Routed '%s' -> template (%s, confidence=%.2f)",
                source_file,
                template_result.template_id,
                template_result.confidence,
            )
            return template_result

        logger.info(
            "Routed '%s' -> AI fallback (template confidence=%.2f, below %.2f threshold)",
            source_file,
            template_result.confidence,
            self.config.auto_fallback_confidence,
        )
        return self.ai_extractor.extract(text, source_file)
