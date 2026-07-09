"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import AppConfig  # noqa: E402


@pytest.fixture(scope="session")
def config() -> AppConfig:
    return AppConfig(str(ROOT / "config.yaml"))


@pytest.fixture(scope="session")
def sample_data_dir() -> Path:
    return ROOT / "sample_data"
