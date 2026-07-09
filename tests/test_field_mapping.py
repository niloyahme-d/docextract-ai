"""Tests for src/config.py - the field-mapping configuration loader."""

from __future__ import annotations

import pytest

from src.config import AppConfig, ConfigError


def test_config_loads_required_fields(config):
    required_names = config.required_field_names()

    assert "vendor_name" in required_names
    assert "invoice_number" in required_names
    assert "total_amount" in required_names


def test_config_loads_all_field_names(config):
    all_names = config.all_field_names()

    assert "line_items" in all_names
    assert len(all_names) == len(config.fields)


def test_config_loads_templates(config):
    template_ids = [t.id for t in config.templates]

    assert "standard_invoice_v1" in template_ids
    assert "standard_receipt_v1" in template_ids


def test_config_routing_defaults(config):
    assert config.default_mode in ("template", "ai", "auto")
    assert 0.0 <= config.auto_fallback_confidence <= 1.0


def test_missing_config_file_raises_clear_error(tmp_path):
    missing_path = tmp_path / "does_not_exist.yaml"

    with pytest.raises(ConfigError):
        AppConfig(missing_path)


def test_config_without_fields_section_raises(tmp_path):
    bad_config = tmp_path / "bad_config.yaml"
    bad_config.write_text("routing:\n  default_mode: auto\n")

    with pytest.raises(ConfigError):
        AppConfig(bad_config)
