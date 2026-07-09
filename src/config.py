"""Loads and validates config.yaml.

Kept deliberately small and dependency-light so non-developers can edit
config.yaml without needing to understand the rest of the codebase.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigError(RuntimeError):
    """Raised when config.yaml is missing required structure."""


class FieldDefinition:
    """One entry from the `fields:` section of config.yaml."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.name: str = raw["name"]
        self.type: str = raw.get("type", "string")
        self.required: bool = raw.get("required", False)
        self.description: str = raw.get("description", "")


class TemplateDefinition:
    """One entry from the `templates:` section of config.yaml."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.id: str = raw["id"]
        self.match_hint: str = raw.get("match_hint", "")
        self.rules: dict[str, dict[str, Any]] = raw.get("rules", {})


class AppConfig:
    """Typed, validated view over config.yaml."""

    def __init__(self, path: str | Path = "config.yaml") -> None:
        self.path = Path(path)
        if not self.path.exists():
            raise ConfigError(f"Config file not found: {self.path}")

        with self.path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        if "fields" not in raw:
            raise ConfigError("config.yaml must define a top-level 'fields' list")

        self.fields: list[FieldDefinition] = [FieldDefinition(f) for f in raw["fields"]]
        self.templates: list[TemplateDefinition] = [
            TemplateDefinition(t) for t in raw.get("templates", [])
        ]

        routing = raw.get("routing", {})
        self.default_mode: str = routing.get("default_mode", "auto")
        self.auto_fallback_confidence: float = routing.get("auto_fallback_confidence", 0.75)

        ocr = raw.get("ocr", {})
        self.ocr_min_confidence: float = ocr.get("min_confidence", 0.6)
        self.ocr_language: str = ocr.get("language", "eng")

    def required_field_names(self) -> list[str]:
        return [f.name for f in self.fields if f.required]

    def all_field_names(self) -> list[str]:
        return [f.name for f in self.fields]
