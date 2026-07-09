"""Template-based extraction: fast, deterministic, zero LLM cost.

Matches document text against the `templates:` section of config.yaml and
applies simple regex/positional rules per field. This is intentionally
"dumb" - it trades flexibility for speed and cost, which is the whole
point of offering it as an alternative to the AI path (see
docs/architecture.md for the routing rationale).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from src.config import AppConfig, TemplateDefinition
from src.extractors.base import BaseExtractor
from src.models import ExtractionMethod, ExtractionResult, ExtractionStatus


class TemplateExtractor(BaseExtractor):
    """Rule-based extractor driven entirely by config.yaml."""

    def find_matching_template(self, text: str) -> Optional[TemplateDefinition]:
        """Pick the best-matching template for this document's text.

        Matching strategy: each template's `rules` dict is tried against the
        text; the template whose rules successfully extract the most
        *required* fields wins. This keeps the matching logic in one place
        instead of requiring a separate "detector" per template.
        """
        best_template = None
        best_score = -1

        for template in self.config.templates:
            score = self._score_template(template, text)
            if score > best_score:
                best_score = score
                best_template = template

        # Require at least one required field to have matched, or we're
        # better off falling back to AI extraction.
        if best_score <= 0:
            return None
        return best_template

    def _score_template(self, template: TemplateDefinition, text: str) -> int:
        score = 0
        required_names = set(self.config.required_field_names())
        for field_name, rule in template.rules.items():
            if field_name not in required_names:
                continue
            value = self._apply_rule(rule, text)
            if value is not None:
                score += 1
        return score

    def extract(self, text: str, source_file: str) -> ExtractionResult:
        template = self.find_matching_template(text)
        if template is None:
            return ExtractionResult(
                source_file=source_file,
                method=ExtractionMethod.TEMPLATE,
                status=ExtractionStatus.FAILED,
                errors=["No configured template matched this document's layout."],
                confidence=0.0,
                raw_text=text,
            )

        fields: dict[str, Any] = {}
        errors: list[str] = []

        for field_def in self.config.fields:
            rule = template.rules.get(field_def.name)
            if rule is None:
                if field_def.required:
                    errors.append(
                        f"Template '{template.id}' has no rule for required field "
                        f"'{field_def.name}'."
                    )
                continue

            raw_value = self._apply_rule(rule, text)
            if raw_value is None:
                if field_def.required:
                    errors.append(f"Required field '{field_def.name}' not found in document.")
                continue

            fields[field_def.name] = self._cast(raw_value, field_def.type, field_def.name, errors)

        missing_required = [
            f.name for f in self.config.fields if f.required and f.name not in fields
        ]
        if missing_required:
            status = ExtractionStatus.PARTIAL if fields else ExtractionStatus.FAILED
        else:
            status = ExtractionStatus.SUCCESS

        confidence = self._confidence(fields, errors)

        return ExtractionResult(
            source_file=source_file,
            method=ExtractionMethod.TEMPLATE,
            status=status,
            fields=fields,
            confidence=confidence,
            errors=errors,
            template_id=template.id,
            raw_text=text,
        )

    def _apply_rule(self, rule: dict[str, Any], text: str) -> Optional[str]:
        strategy = rule.get("strategy")
        if strategy == "regex":
            pattern = rule["pattern"]
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
            return None
        if strategy == "first_line":
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return lines[0] if lines else None
        return None

    def _cast(self, raw_value: str, field_type: str, field_name: str, errors: list[str]) -> Any:
        try:
            if field_type == "currency":
                return float(raw_value.replace(",", "").replace("$", ""))
            if field_type == "date":
                return datetime.strptime(raw_value, "%Y-%m-%d").date().isoformat()
            if field_type == "list":
                return raw_value  # line items are handled separately; kept as-is here
            return raw_value
        except (ValueError, TypeError) as exc:
            errors.append(f"Could not parse '{field_name}' value '{raw_value}' as {field_type}: {exc}")
            return raw_value

    def _confidence(self, fields: dict[str, Any], errors: list[str]) -> float:
        required = self.config.required_field_names()
        if not required:
            return 1.0 if not errors else 0.5
        found = sum(1 for name in required if name in fields)
        base = found / len(required)
        penalty = min(0.1 * len(errors), base)  # errors erode confidence, floor at 0
        return max(0.0, round(base - penalty, 3))
