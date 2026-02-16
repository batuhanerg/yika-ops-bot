"""One-time cleanup: strip 'v'/'V' prefix from HW/FW Version columns.

Scans Hardware Inventory and Stock tabs, finds cells with a leading v/V prefix,
and updates them in-place. Logs how many cells were updated per tab.

Usage:
    python -m scripts.normalize_versions
"""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv
load_dotenv()

import gspread
from google.oauth2.service_account import Credentials


def _connect() -> gspread.Spreadsheet:
    creds_json = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_key(os.environ["GOOGLE_SHEET_ID"])


def normalize_tab(spreadsheet: gspread.Spreadsheet, tab_name: str) -> int:
    """Strip v/V prefix from HW Version and FW Version columns in a tab.

    Returns the number of cells updated.
    """
    ws = spreadsheet.worksheet(tab_name)
    all_values = ws.get_all_values()
    if len(all_values) < 2:
        print(f"  {tab_name}: no data rows")
        return 0

    headers = all_values[0]
    version_cols = []
    for i, h in enumerate(headers):
        if h in ("HW Version", "FW Version"):
            version_cols.append((i, h))

    if not version_cols:
        print(f"  {tab_name}: no HW/FW Version columns found")
        return 0

    updated = 0
    for row_idx, row in enumerate(all_values[1:], start=2):
        for col_idx, col_name in version_cols:
            if col_idx < len(row):
                val = row[col_idx]
                if isinstance(val, str) and val and val[0] in ("v", "V"):
                    new_val = val.lstrip("vV")
                    ws.update_cell(row_idx, col_idx + 1, new_val)
                    print(f"  {tab_name} row {row_idx} [{col_name}]: '{val}' → '{new_val}'")
                    updated += 1

    return updated


def main() -> None:
    print("Connecting to Google Sheet...")
    spreadsheet = _connect()

    total = 0
    for tab in ("Hardware Inventory", "Stock"):
        print(f"\nScanning {tab}...")
        count = normalize_tab(spreadsheet, tab)
        total += count
        print(f"  {tab}: {count} cell(s) updated")

    print(f"\nDone. Total cells updated: {total}")


if __name__ == "__main__":
    main()
