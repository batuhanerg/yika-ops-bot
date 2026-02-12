"""Migration script: Improve Site Viewer tab UX.

Changes:
- Site selector dropdown shows "Customer (Site ID)" format
- Support Log section headers match current schema (with Ticket ID first)
- Key columns widened (Issue Summary, Resolution, Notes)
- Support log sorted by Received Date descending via SORT(FILTER(...))

Safe to run multiple times (idempotent — always overwrites).

Usage:
    python -m scripts.migrate_site_viewer
"""

from __future__ import annotations

import json
import os

# Support Log columns in the current schema
SUPPORT_LOG_HEADERS = [
    "Ticket ID", "Site ID", "Received Date", "Resolved Date", "Type",
    "Status", "Root Cause", "Reported By", "Issue Summary", "Resolution",
    "Devices Affected", "Responsible", "Notes",
]

# Row positions in Site Viewer (these are conventional; adjust if layout differs)
_SELECTOR_ROW = 1       # Row 1: site selector dropdown
_SELECTOR_COL = 2       # Column B: the dropdown cell
_SL_HEADER_ROW = 3      # Row 3: support log section headers
_SL_DATA_ROW = 4        # Row 4: SORT(FILTER(...)) formula starts
_SL_START_COL = 1       # Column A

# Column widths in pixels
_COLUMN_WIDTHS = {
    "Issue Summary": 320,   # ~40 chars
    "Resolution": 320,      # ~40 chars
    "Notes": 240,           # ~30 chars
}


def _build_dropdown_values(sites_data: list[list[str]]) -> list[str]:
    """Build 'Customer (Site ID)' dropdown values from sites data."""
    if len(sites_data) < 2:
        return []
    # Row 0 = headers, rows 1+ = data
    # Expect: col 0 = Site ID, col 1 = Customer
    headers = sites_data[0]
    site_col = 0
    customer_col = 1
    # Try to find columns by header name
    for i, h in enumerate(headers):
        if h == "Site ID":
            site_col = i
        elif h == "Customer":
            customer_col = i

    values = []
    for row in sites_data[1:]:
        if len(row) > max(site_col, customer_col) and row[site_col]:
            site_id = row[site_col]
            customer = row[customer_col] if customer_col < len(row) else ""
            if customer:
                values.append(f"{customer} ({site_id})")
            else:
                values.append(site_id)
    return values


def _build_sort_filter_formula(selected_cell: str) -> str:
    """Build SORT(FILTER(...)) formula for support log sorted by Received Date desc.

    Extracts the Site ID from the selector value (format: "Customer (SITE-ID)")
    and filters Support Log by that Site ID, sorted by Received Date descending.
    """
    # Extract Site ID from "Customer (SITE-ID)" format using REGEXEXTRACT
    site_id_extract = (
        f'REGEXEXTRACT({selected_cell},"\\(([^)]+)\\)")'
    )
    return (
        f'=IFERROR(SORT(FILTER('
        f"'Support Log'!A:M,"
        f"'Support Log'!B:B={site_id_extract}"
        f"),3,FALSE),)"  # Sort by col 3 (Received Date), descending
    )


def _set_column_widths(worksheet, header_row: int) -> None:
    """Set column widths for key columns via batch_update on the spreadsheet."""
    # Read headers to find column indices
    # We use the spreadsheet's batch_update for column sizing
    spreadsheet = worksheet.spreadsheet
    sheet_id = worksheet.id

    requests = []
    for col_idx, header in enumerate(SUPPORT_LOG_HEADERS):
        if header in _COLUMN_WIDTHS:
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": _SL_START_COL - 1 + col_idx,
                        "endIndex": _SL_START_COL + col_idx,
                    },
                    "properties": {
                        "pixelSize": _COLUMN_WIDTHS[header],
                    },
                    "fields": "pixelSize",
                }
            })

    if requests:
        spreadsheet.batch_update({"requests": requests})


def migrate(viewer_ws, sites_ws) -> None:
    """Update Site Viewer with improved selector, headers, sort, and widths."""
    # 1. Build dropdown values from Sites tab
    sites_data = sites_ws.get_all_values()
    dropdown_values = _build_dropdown_values(sites_data)

    # 2. Set up data validation for the selector cell
    if dropdown_values:
        from gspread.utils import ValueInputOption
        # Use batch_update to set data validation
        validation_rule = {
            "setDataValidation": {
                "range": {
                    "sheetId": viewer_ws.id,
                    "startRowIndex": _SELECTOR_ROW - 1,
                    "endRowIndex": _SELECTOR_ROW,
                    "startColumnIndex": _SELECTOR_COL - 1,
                    "endColumnIndex": _SELECTOR_COL,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [
                            {"userEnteredValue": v} for v in dropdown_values
                        ],
                    },
                    "showCustomUi": True,
                    "strict": True,
                },
            }
        }
        viewer_ws.spreadsheet.batch_update({"requests": [validation_rule]})

    # 3. Write Support Log section headers
    for col_offset, header in enumerate(SUPPORT_LOG_HEADERS):
        viewer_ws.update_cell(_SL_HEADER_ROW, _SL_START_COL + col_offset, header)

    # 4. Write SORT(FILTER(...)) formula for support log data
    selector_cell = f"B{_SELECTOR_ROW}"
    formula = _build_sort_filter_formula(selector_cell)
    viewer_ws.update_cell(_SL_DATA_ROW, _SL_START_COL, formula)

    # 5. Set column widths
    _set_column_widths(viewer_ws, _SL_HEADER_ROW)

    print("Site Viewer migration complete.")
    if dropdown_values:
        print(f"  Selector: {len(dropdown_values)} sites in 'Customer (Site ID)' format")
    print(f"  Support Log headers: {len(SUPPORT_LOG_HEADERS)} columns")
    print(f"  Sort: by Received Date descending")
    print(f"  Column widths: {list(_COLUMN_WIDTHS.keys())}")


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

    viewer_ws = spreadsheet.worksheet("Site Viewer")
    sites_ws = spreadsheet.worksheet("Sites")

    migrate(viewer_ws, sites_ws)


if __name__ == "__main__":
    main()
