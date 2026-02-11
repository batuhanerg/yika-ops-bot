"""Migration script: Rename 'Technician' column header to 'Responsible' in Support Log tab.

Usage:
    python -m scripts.migrate_technician_to_responsible

Requires GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON environment variables.
"""

from __future__ import annotations

import json
import os
import sys


def migrate(worksheet) -> None:
    """Rename 'Technician' to 'Responsible' in row 1 of the given worksheet."""
    headers = worksheet.row_values(1)
    if "Technician" in headers:
        col_idx = headers.index("Technician") + 1  # 1-based
        worksheet.update_cell(1, col_idx, "Responsible")
        print(f"Renamed column {col_idx}: 'Technician' → 'Responsible'")
    elif "Responsible" in headers:
        print("Column already named 'Responsible'. No changes needed.")
    else:
        print("WARNING: Neither 'Technician' nor 'Responsible' found in headers.")
        print(f"Headers: {headers}")


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()

    import gspread
    from google.oauth2.service_account import Credentials

    creds_json = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(os.environ["GOOGLE_SHEET_ID"])
    ws = spreadsheet.worksheet("Support Log")

    migrate(ws)


if __name__ == "__main__":
    main()
