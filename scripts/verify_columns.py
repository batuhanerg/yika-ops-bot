"""Verify that code column constants match actual Google Sheet headers.

Reads each tab's header row from the live sheet and compares against
the column lists defined in app/services/sheets.py.

Usage:
    python -m scripts.verify_columns
"""

from __future__ import annotations

import json
import os
import sys

from app.services.sheets import (
    SITES_COLUMNS,
    HARDWARE_COLUMNS,
    SUPPORT_LOG_COLUMNS,
    STOCK_COLUMNS,
    AUDIT_LOG_COLUMNS,
    FEEDBACK_COLUMNS,
)

# Tabs to verify: (tab name, expected columns, header row)
_TABS = [
    ("Sites", SITES_COLUMNS, 1),
    ("Hardware Inventory", HARDWARE_COLUMNS, 1),
    ("Support Log", SUPPORT_LOG_COLUMNS, 1),
    ("Stock", STOCK_COLUMNS, 1),
    ("Audit Log", AUDIT_LOG_COLUMNS, 1),
    ("Feedback", FEEDBACK_COLUMNS, 1),
    ("Implementation Details", None, 2),  # dynamic headers, just report
]


def verify(spreadsheet) -> bool:
    """Compare sheet headers against code constants. Returns True if all match."""
    all_ok = True

    for tab_name, expected_cols, header_row in _TABS:
        try:
            ws = spreadsheet.worksheet(tab_name)
        except Exception:
            print(f"  SKIP  {tab_name} — tab not found")
            continue

        actual = ws.row_values(header_row)
        # Strip trailing empty cells
        while actual and actual[-1] == "":
            actual.pop()

        if expected_cols is None:
            # Just report dynamic headers
            print(f"  INFO  {tab_name} (row {header_row}): {actual}")
            continue

        if actual == expected_cols:
            print(f"  OK    {tab_name} ({len(actual)} columns)")
        else:
            all_ok = False
            print(f"  FAIL  {tab_name}")
            # Show differences
            max_len = max(len(actual), len(expected_cols))
            for i in range(max_len):
                a = actual[i] if i < len(actual) else "<missing>"
                e = expected_cols[i] if i < len(expected_cols) else "<extra>"
                marker = "  " if a == e else "!!"
                print(f"         {marker} [{i}] expected={e!r}  actual={a!r}")

    return all_ok


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

    print("Verifying column alignment...\n")
    ok = verify(spreadsheet)
    print()

    if ok:
        print("All tabs match code constants.")
    else:
        print("MISMATCH detected — see above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
