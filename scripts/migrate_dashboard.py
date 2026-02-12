"""Migration script: Replace 'Total Devices' with device-type breakdown columns.

Replaces the single "Total Devices" column in the Dashboard tab with five
columns: Tags, Anchors, Gateways, Charging Docks, Other. Each uses SUMIFS
to count devices by type from Hardware Inventory.

Safe to run multiple times (idempotent).

Usage:
    python -m scripts.migrate_dashboard
"""

from __future__ import annotations

import json
import os

DEVICE_COLUMNS = ["Tags", "Anchors", "Gateways", "Charging Docks", "Other"]

# Map column names to their SUMIFS device_type criteria
_COLUMN_DEVICE_TYPES: dict[str, list[str]] = {
    "Tags": ["Tag"],
    "Anchors": ["Anchor"],
    "Gateways": ["Gateway"],
    "Charging Docks": ["Charging Dock"],
    "Other": ["Power Bank", "Power Adapter", "USB Cable", "Other"],
}

# Hardware Inventory column letters (A=Site ID, B=Device Type, E=Qty)
_HW_SITE_COL = "A"
_HW_TYPE_COL = "B"
_HW_QTY_COL = "E"


def _build_sumifs_formula(row: int, device_types: list[str]) -> str:
    """Build a SUMIFS formula for the given device types at the given row."""
    site_ref = f"$A{row}"
    parts = []
    for dt in device_types:
        parts.append(
            f"SUMIFS("
            f"'Hardware Inventory'!{_HW_QTY_COL}:{_HW_QTY_COL},"
            f"'Hardware Inventory'!{_HW_SITE_COL}:{_HW_SITE_COL},{site_ref},"
            f"'Hardware Inventory'!{_HW_TYPE_COL}:{_HW_TYPE_COL},\"{dt}\")"
        )
    if len(parts) == 1:
        return "=" + parts[0]
    return "=" + "+".join(parts)


def migrate(worksheet) -> None:
    """Replace 'Total Devices' with 5 device-type breakdown columns."""
    headers = worksheet.row_values(1)

    # Idempotent check: already migrated
    if "Tags" in headers:
        print("Dashboard already migrated (Tags column found). No changes needed.")
        return

    if "Total Devices" not in headers:
        print("WARNING: Neither 'Total Devices' nor 'Tags' found in Dashboard headers.")
        print(f"Headers: {headers}")
        return

    td_idx = headers.index("Total Devices")  # 0-based
    td_col = td_idx + 1  # 1-based

    # Insert 4 new columns after Total Devices position (we reuse Total Devices col for Tags)
    # insert_cols(col, number_of_cols) — inserts empty columns at position col
    worksheet.insert_cols(td_col + 1, 4)

    # Write all 5 headers
    for i, col_name in enumerate(DEVICE_COLUMNS):
        worksheet.update_cell(1, td_col + i, col_name)

    # Write SUMIFS formulas for each data row
    num_data_rows = worksheet.row_count - 1
    for row in range(2, 2 + num_data_rows):
        for i, col_name in enumerate(DEVICE_COLUMNS):
            device_types = _COLUMN_DEVICE_TYPES[col_name]
            formula = _build_sumifs_formula(row, device_types)
            worksheet.update_cell(row, td_col + i, formula)

    print(f"Migrated Dashboard: replaced 'Total Devices' (col {td_col}) "
          f"with {len(DEVICE_COLUMNS)} device-type columns.")
    print(f"Formulas set for {num_data_rows} data rows.")


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
    ws = spreadsheet.worksheet("Dashboard")

    migrate(ws)


if __name__ == "__main__":
    main()
