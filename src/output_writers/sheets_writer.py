"""Optional Google Sheets output writer.

Only imported/used when the user actually requests Sheets output, so
`gspread`/`google-auth` and a service-account file are not required for
the Excel/CSV-only happy path.
"""

from __future__ import annotations

import os

from src.config import AppConfig
from src.models import ExtractionResult


class SheetsWriterError(RuntimeError):
    """Raised when Sheets output is requested but not properly configured."""


def write_sheets(
    results: list[ExtractionResult],
    config: AppConfig,
    spreadsheet_name: str,
    worksheet_name: str = "Extracted Data",
) -> str:
    """Push results to a Google Sheet, creating it if it doesn't exist.

    Requires GOOGLE_SERVICE_ACCOUNT_FILE to be set in the environment,
    pointing at a service-account JSON key with Sheets + Drive API access.
    Returns the spreadsheet URL on success.
    """
    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not service_account_file:
        raise SheetsWriterError(
            "GOOGLE_SERVICE_ACCOUNT_FILE is not set. Google Sheets output is optional - "
            "set this env var to a service-account JSON key to enable it, or use "
            "--output excel / --output csv instead."
        )

    try:
        import gspread
    except ImportError as exc:
        raise SheetsWriterError("gspread is not installed. Run: pip install gspread google-auth") from exc

    gc = gspread.service_account(filename=service_account_file)

    try:
        sh = gc.open(spreadsheet_name)
    except gspread.SpreadsheetNotFound:
        sh = gc.create(spreadsheet_name)

    try:
        ws = sh.worksheet(worksheet_name)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=26)

    field_names = config.all_field_names()
    columns = ["source_file", "status", "method", "confidence", *field_names, "errors"]

    rows = [[c.replace("_", " ").title() for c in columns]]
    for result in results:
        rows.append(
            [
                result.source_file,
                result.status.value,
                result.method.value,
                str(result.confidence),
                *[str(result.fields.get(name, "")) for name in field_names],
                "; ".join(result.errors),
            ]
        )

    ws.update(rows)
    return sh.url
