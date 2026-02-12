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

# Column widths in pixels
_COLUMN_WIDTHS = {
    "Issue Summary": 320,   # ~40 chars
    "Resolution": 320,      # ~40 chars
    "Notes": 240,           # ~30 chars
}


def _find_selector_cell(all_values: list[list[str]]) -> tuple[int, int] | None:
    """Find the selector cell (the cell next to 'Select Site:'). Returns (row, col) 1-based."""
    for i, row in enumerate(all_values):
        for j, cell in enumerate(row):
            if "Select Site" in cell or "Select site" in cell:
                return i + 1, j + 2  # selector is the next column
    return None


def _find_support_log_section(all_values: list[list[str]]) -> int | None:
    """Find the row containing the SUPPORT LOG section header. Returns 1-based row."""
    for i, row in enumerate(all_values):
        for cell in row:
            if "SUPPORT LOG" in cell.upper():
                return i + 1
    return None


def _build_dropdown_values(sites_data: list[list[str]]) -> list[str]:
    """Build 'Customer (Site ID)' dropdown values from sites data."""
    if len(sites_data) < 2:
        return []
    headers = sites_data[0]
    site_col = 0
    customer_col = 1
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
    site_id_extract = (
        f'REGEXEXTRACT({selected_cell},"\\(([^)]+)\\)")'
    )
    return (
        f'=IFERROR(SORT(FILTER('
        f"'Support Log'!A:M,"
        f"'Support Log'!B:B={site_id_extract}"
        f"),3,FALSE),)"  # Sort by col 3 (Received Date), descending
    )


def migrate(viewer_ws, sites_ws) -> None:
    """Update Site Viewer with improved selector, headers, sort, and widths."""
    all_values = viewer_ws.get_all_values()

    # 1. Find layout positions
    selector_pos = _find_selector_cell(all_values)
    sl_section_row = _find_support_log_section(all_values)

    selector_row = selector_pos[0] if selector_pos else 4
    selector_col = selector_pos[1] if selector_pos else 2
    sl_header_row = (sl_section_row + 1) if sl_section_row else 61
    sl_data_row = sl_header_row + 1

    print(f"  Layout detected: selector at row {selector_row}/col {selector_col}, "
          f"support log headers at row {sl_header_row}")

    # 2. Build dropdown values from Sites tab
    sites_data = sites_ws.get_all_values()
    dropdown_values = _build_dropdown_values(sites_data)

    # 3. Set up data validation for the selector cell
    if dropdown_values:
        validation_rule = {
            "setDataValidation": {
                "range": {
                    "sheetId": viewer_ws.id,
                    "startRowIndex": selector_row - 1,
                    "endRowIndex": selector_row,
                    "startColumnIndex": selector_col - 1,
                    "endColumnIndex": selector_col,
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

    # 4. Write Support Log section headers (batch)
    header_row_data = [SUPPORT_LOG_HEADERS]
    col_letter = "A"
    end_letter = chr(ord("A") + len(SUPPORT_LOG_HEADERS) - 1)
    range_str = f"{col_letter}{sl_header_row}:{end_letter}{sl_header_row}"
    viewer_ws.update(values=header_row_data, range_name=range_str, value_input_option="USER_ENTERED")

    # 5. Write SORT(FILTER(...)) formula for support log data
    selector_col_letter = chr(ord("A") + selector_col - 1)
    selector_cell = f"{selector_col_letter}{selector_row}"
    formula = _build_sort_filter_formula(selector_cell)
    viewer_ws.update_cell(sl_data_row, 1, formula)

    # 6. Set column widths for support log section
    sheet_id = viewer_ws.id
    requests = []
    for col_idx, header in enumerate(SUPPORT_LOG_HEADERS):
        if header in _COLUMN_WIDTHS:
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": col_idx,
                        "endIndex": col_idx + 1,
                    },
                    "properties": {
                        "pixelSize": _COLUMN_WIDTHS[header],
                    },
                    "fields": "pixelSize",
                }
            })
    if requests:
        viewer_ws.spreadsheet.batch_update({"requests": requests})

    print("Site Viewer migration complete.")
    if dropdown_values:
        print(f"  Selector: {len(dropdown_values)} sites in 'Customer (Site ID)' format")
    print(f"  Support Log headers: {len(SUPPORT_LOG_HEADERS)} columns at row {sl_header_row}")
    print(f"  Sort formula at row {sl_data_row}, referencing {selector_cell}")
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
