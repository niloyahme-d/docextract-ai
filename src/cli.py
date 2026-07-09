"""Command-line entry point for DocExtract AI.

Usage:
    python -m src.cli --input sample_data --output-format excel --output output/results.xlsx
    python -m src.cli --input sample_data --mode ai --output-format csv --output output/results.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.batch_processor import process_folder
from src.config import AppConfig
from src.output_writers.csv_writer import write_csv
from src.output_writers.excel_writer import write_excel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docextract-ai",
        description="Extract structured data from a folder of invoices/receipts.",
    )
    parser.add_argument("--input", required=True, help="Folder of PDF documents to process")
    parser.add_argument(
        "--mode",
        choices=["template", "ai", "auto"],
        default=None,
        help="Extraction mode. Defaults to config.yaml's routing.default_mode (auto).",
    )
    parser.add_argument(
        "--output-format",
        choices=["excel", "csv", "sheets"],
        default="excel",
        help="Output format (default: excel)",
    )
    parser.add_argument(
        "--output",
        default="output/results.xlsx",
        help="Output file path (for excel/csv) or spreadsheet name (for sheets)",
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--quiet", action="store_true", help="Suppress the progress bar")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    parser = build_parser()
    args = parser.parse_args(argv)

    config = AppConfig(args.config)
    input_dir = Path(args.input)
    if not input_dir.is_dir():
        print(f"Error: '{input_dir}' is not a directory.", file=sys.stderr)
        return 1

    summary = process_folder(input_dir, config, mode=args.mode, show_progress=not args.quiet)

    print(
        f"\nProcessed {summary.total} document(s): "
        f"{summary.succeeded} succeeded, {summary.partial} partial, {summary.failed} failed."
    )
    for result in summary.results:
        if result.status.value != "success":
            print(f"  [{result.status.value.upper()}] {result.source_file}: {'; '.join(result.errors)}")

    if args.output_format == "excel":
        out = write_excel(summary.results, config, args.output)
        print(f"\nWrote {out}")
    elif args.output_format == "csv":
        out = write_csv(summary.results, config, args.output)
        print(f"\nWrote {out}")
    elif args.output_format == "sheets":
        from src.output_writers.sheets_writer import write_sheets

        url = write_sheets(summary.results, config, spreadsheet_name=args.output)
        print(f"\nWrote to Google Sheet: {url}")

    return 0 if summary.failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
