"""Writes a batch of ExtractionResults to CSV."""

from __future__ import annotations

import csv
from pathlib import Path

from src.config import AppConfig
from src.models import ExtractionResult


def write_csv(results: list[ExtractionResult], config: AppConfig, output_path: str | Path) -> Path:
    """Write results to a CSV file, one row per document."""
    output_path = Path(output_path)
    field_names = config.all_field_names()
    columns = ["source_file", "status", "method", "confidence", *field_names, "errors"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([c.replace("_", " ").title() for c in columns])
        for result in results:
            row = [
                result.source_file,
                result.status.value,
                result.method.value,
                result.confidence,
                *[result.fields.get(name, "") for name in field_names],
                "; ".join(result.errors),
            ]
            writer.writerow(row)

    return output_path
