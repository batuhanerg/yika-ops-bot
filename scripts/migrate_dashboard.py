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


def _build_sumifs_formula(row: int, site_col_letter: str, device_types: list[str]) -> str:
    """Build a SUMIFS formula for the given device types at the given row."""
    site_ref = f"${site_col_letter}{row}"
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


def _find_header_and_data(worksheet) -> tuple[int, list[str], int] | None:
    """Find headers and count data rows. Returns (1-based header_row, headers, num_data_rows)."""
    all_values = worksheet.get_all_values()
    header_row_idx = None
    for i, row in enumerate(all_values):
        if "Total Devices" in row or "Tags" in row:
            header_row_idx = i
            break
    if header_row_idx is None:
        return None
    headers = all_values[header_row_idx]
    # Count non-empty data rows after header (first column has site ID)
    site_col = headers.index("Site ID") if "Site ID" in headers else 0
    num_data_rows = 0
    for row in all_values[header_row_idx + 1:]:
        if row and len(row) > site_col and row[site_col].strip():
            num_data_rows += 1
        else:
            break  # Stop at first empty row
    return header_row_idx + 1, headers, num_data_rows


def migrate(worksheet) -> None:
    """Replace 'Total Devices' with 5 device-type breakdown columns."""
    result = _find_header_and_data(worksheet)
    if result is None:
        print("WARNING: Neither 'Total Devices' nor 'Tags' found in any row.")
        return

    header_row, headers, num_data_rows = result

    # Idempotent check: already migrated
    if "Tags" in headers:
        print("Dashboard already migrated (Tags column found). No changes needed.")
        return

    td_idx = headers.index("Total Devices")  # 0-based
    td_col = td_idx + 1  # 1-based

    # Find Site ID column for formula references
    site_id_idx = headers.index("Site ID") if "Site ID" in headers else 0
    site_col_letter = chr(ord("A") + site_id_idx)

    # Insert 4 new empty columns after Total Devices position
    # (we reuse Total Devices col for Tags, so insert 4 more after it)
    worksheet.spreadsheet.batch_update({
        "requests": [{
            "insertDimension": {
                "range": {
                    "sheetId": worksheet.id,
                    "dimension": "COLUMNS",
                    "startIndex": td_col,       # 0-based: insert after Total Devices
                    "endIndex": td_col + 4,     # insert 4 columns
                },
                "inheritFromBefore": True,
            }
        }]
    })

    # Build all cell updates in one batch: headers + formulas
    # Use A1 notation range for batch update
    col_start_letter = chr(ord("A") + td_idx)
    col_end_letter = chr(ord("A") + td_idx + 4)

    # Build rows: header row + data rows
    rows = [DEVICE_COLUMNS]  # header
    for row in range(header_row + 1, header_row + 1 + num_data_rows):
        formula_row = []
        for col_name in DEVICE_COLUMNS:
            device_types = _COLUMN_DEVICE_TYPES[col_name]
            formula_row.append(_build_sumifs_formula(row, site_col_letter, device_types))
        rows.append(formula_row)

    # Write all at once using worksheet.update (A1 notation)
    range_str = f"{col_start_letter}{header_row}:{col_end_letter}{header_row + num_data_rows}"
    worksheet.update(range_str, rows, value_input_option="USER_ENTERED")

    print(f"Migrated Dashboard: replaced 'Total Devices' (col {td_col}, row {header_row}) "
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
