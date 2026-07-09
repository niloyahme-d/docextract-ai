"""AI-based extraction: handles varied / unstructured document layouts.

Used when no template matches (see router.py), or when explicitly forced.
Builds a JSON-schema-style prompt from config.yaml's field list so the
fields extracted stay in sync with the template path automatically - add a
field to config.yaml and both extraction paths pick it up.
"""

from __future__ import annotations

from typing import Any

from src.config import AppConfig
from src.extractors.ai_providers import LLMProvider, ProviderError, get_provider
from src.extractors.base import BaseExtractor
from src.models import ExtractionMethod, ExtractionResult, ExtractionStatus

SYSTEM_PROMPT = """You are a precise document data extraction engine.
You will be given the raw text of an invoice or receipt.
Extract ONLY the fields described in the schema. If a field is not present
in the document, set it to null - never guess or hallucinate a value.
Return ONLY a single JSON object matching the schema. No prose, no markdown
code fences, no explanation."""


def _build_schema_description(config: AppConfig) -> str:
    lines = []
    for f in config.fields:
        req = "required" if f.required else "optional"
        lines.append(f'  "{f.name}": {f.type} ({req}) - {f.description}')
    return "\n".join(lines)


class AIExtractor(BaseExtractor):
    """LLM-backed extractor. Provider is chosen via AI_PROVIDER env var."""

    def __init__(self, config: AppConfig, provider: LLMProvider | None = None) -> None:
        super().__init__(config)
        self._provider = provider  # allow injection for testing

    def _get_provider(self) -> LLMProvider:
        if self._provider is None:
            self._provider = get_provider()
        return self._provider

    def extract(self, text: str, source_file: str) -> ExtractionResult:
        schema_desc = _build_schema_description(self.config)
        user_prompt = (
            f"Schema:\n{schema_desc}\n\n"
            f"Document text:\n---\n{text}\n---\n\n"
            f"Return a JSON object with exactly these keys: "
            f"{', '.join(self.config.all_field_names())}."
        )

        try:
            provider = self._get_provider()
            raw_fields = provider.complete_json(SYSTEM_PROMPT, user_prompt)
        except ProviderError as exc:
            return ExtractionResult(
                source_file=source_file,
                method=ExtractionMethod.AI,
                status=ExtractionStatus.FAILED,
                errors=[str(exc)],
                confidence=0.0,
                raw_text=text,
            )

        fields, errors = self._normalize(raw_fields)

        missing_required = [
            f.name
            for f in self.config.fields
            if f.required and (f.name not in fields or fields[f.name] in (None, ""))
        ]
        if missing_required:
            errors.append(f"AI extraction missing required fields: {', '.join(missing_required)}")
            status = ExtractionStatus.PARTIAL if fields else ExtractionStatus.FAILED
        else:
            status = ExtractionStatus.SUCCESS

        confidence = 0.9 if status == ExtractionStatus.SUCCESS else (0.5 if fields else 0.0)

        return ExtractionResult(
            source_file=source_file,
            method=ExtractionMethod.AI,
            status=status,
            fields=fields,
            confidence=confidence,
            errors=errors,
            raw_text=text,
        )

    def _normalize(self, raw_fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """Keep only configured fields, drop nulls, coerce obviously wrong types."""
        fields: dict[str, Any] = {}
        errors: list[str] = []
        valid_names = set(self.config.all_field_names())

        for name, value in raw_fields.items():
            if name not in valid_names:
                continue
            if value in (None, ""):
                continue
            fields[name] = value

        for f in self.config.fields:
            if f.type == "currency" and f.name in fields:
                try:
                    fields[f.name] = float(str(fields[f.name]).replace(",", "").replace("$", ""))
                except (ValueError, TypeError):
                    errors.append(f"AI returned non-numeric value for '{f.name}': {fields[f.name]}")

        return fields, errors
