"""Fix Site Viewer layout: Implementation Details headers + Support Log table alignment.

Issues fixed:
1. Implementation Details parameter names must match actual tab row 2 headers exactly
2. Implementation Details values merged C:N for wide display
3. Support log table starts at column B (not A) with full header formatting
4. Date columns show formatted dates (not serial numbers)
5. All support log columns styled as one cohesive table
6. Column widths set for balanced layout across both sections

Usage:
    python -m scripts.fix_site_viewer_layout
    python -m scripts.fix_site_viewer_layout --dry-run
"""

from __future__ import annotations

import json
import os
import sys

# Parameters to skip from Implementation Details (internal/auto columns)
_SKIP_HEADERS = {"Site ID", "_FacilityType"}

# Support Log columns matching the SORT(FILTER('Support Log'!A:M,...)) output
SUPPORT_LOG_HEADERS = [
    "Ticket ID", "Site ID", "Received Date", "Resolved Date", "Type",
    "Status", "Root Cause", "Reported By", "Issue Summary", "Resolution",
    "Devices Affected", "Responsible", "Notes",
]

# Dark blue for header rows (matches existing Site Viewer style)
_HEADER_BG = {"red": 0.1, "green": 0.2, "blue": 0.45}
_HEADER_TEXT = {"red": 1.0, "green": 1.0, "blue": 1.0}

# Column widths (0-based index → pixels) for balanced layout
_COL_WIDTHS = [
    (1, 150),   # B - Parameter / Ticket ID
    (2, 80),    # C - Site ID
    (3, 90),    # D - Received Date
    (4, 90),    # E - Resolved Date
    (5, 65),    # F - Type
    (6, 75),    # G - Status
    (7, 115),   # H - Root Cause
    (8, 90),    # I - Reported By
    (9, 190),   # J - Issue Summary
    (10, 120),  # K - Resolution
    (11, 105),  # L - Devices Affected
    (12, 90),   # M - Responsible
    (13, 130),  # N - Notes
]


def _col_letter(idx: int) -> str:
    """0-based column index to letter(s)."""
    if idx < 26:
        return chr(ord("A") + idx)
    return chr(ord("A") + idx // 26 - 1) + chr(ord("A") + idx % 26)


def fix_layout(viewer_ws, impl_ws, dry_run: bool = False) -> dict:
    """Rewrite Implementation Details and Support Log sections on Site Viewer.

    Returns a summary dict.
    """
    # 1. Read actual Implementation Details headers from row 2
    impl_headers = impl_ws.row_values(2)
    # Filter to displayable parameters (skip Site ID and helper columns)
    params = []
    for i, h in enumerate(impl_headers):
        if h in _SKIP_HEADERS or not h.strip():
            continue
        params.append({"name": h, "col_num": i + 1})  # 1-based for VLOOKUP

    last_impl_col_letter = _col_letter(len(impl_headers) - 1)
    impl_range = f"'Implementation Details'!$A:${last_impl_col_letter}"

    # 2. Determine section positions
    # Implementation Details: starts at row 41
    impl_section_row = 41
    impl_sub_header_row = 42
    impl_data_start = 43
    impl_data_end = impl_data_start + len(params) - 1

    # Support Log: 1 empty row after impl details
    sl_section_row = impl_data_end + 2
    sl_header_row = sl_section_row + 1
    sl_data_row = sl_header_row + 1
    sl_data_end_row = sl_data_row + 19  # 20 data rows

    print(f"  Implementation Details: {len(params)} parameters at rows {impl_data_start}-{impl_data_end}")
    print(f"  Support Log: section at row {sl_section_row}, headers at {sl_header_row}, data at {sl_data_row}")

    summary = {
        "impl_params": len(params),
        "impl_range": f"{impl_data_start}-{impl_data_end}",
        "sl_section_row": sl_section_row,
        "sl_header_row": sl_header_row,
        "sl_data_row": sl_data_row,
    }

    if dry_run:
        print("\n  [DRY RUN] Parameters:")
        for p in params:
            print(f"    {p['name']} → VLOOKUP col {p['col_num']}")
        print(f"\n  [DRY RUN] Support Log headers at B{sl_header_row}:N{sl_header_row}")
        return summary

    sheet_id = viewer_ws.id

    # 2.5. Unmerge ALL cells in both sections
    # Original template had merges (C:I for impl values, H:I for support log)
    # that create mismatched column widths. Unmerge everything, re-merge properly.
    viewer_ws.spreadsheet.batch_update({"requests": [{
        "unmergeCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": impl_section_row - 1,
                "endRowIndex": sl_data_end_row,
                "startColumnIndex": 0,
                "endColumnIndex": 14,
            }
        }
    }]})
    print(f"  Unmerged cells in rows {impl_section_row}-{sl_data_end_row}")

    # 3. Clear everything from impl section through support log data area
    clear_start = impl_section_row
    clear_end = sl_data_end_row
    clear_rows = clear_end - clear_start + 1
    # Clear A through O (15 columns to cover both sections)
    empty_rows = [[""] * 15 for _ in range(clear_rows)]
    viewer_ws.update(
        values=empty_rows,
        range_name=f"A{clear_start}:O{clear_end}",
        value_input_option="USER_ENTERED",
    )
    print(f"  Cleared A{clear_start}:O{clear_end}")

    # 4. Write Implementation Details section
    # Section header
    viewer_ws.update_cell(impl_section_row, 2, "⚙️ IMPLEMENTATION DETAILS")
    # Sub-headers
    viewer_ws.update(
        values=[["Parameter", "Value"]],
        range_name=f"B{impl_sub_header_row}:C{impl_sub_header_row}",
        value_input_option="USER_ENTERED",
    )

    # Parameter labels and VLOOKUP formulas
    impl_data = []
    for p in params:
        formula = f'=IFERROR(VLOOKUP($D$4,{impl_range},{p["col_num"]},FALSE),"")'
        impl_data.append([p["name"], formula])

    viewer_ws.update(
        values=impl_data,
        range_name=f"B{impl_data_start}:C{impl_data_end}",
        value_input_option="USER_ENTERED",
    )
    print(f"  Written {len(params)} Implementation Details parameters")

    # 5. Write Support Log section
    # Section header
    viewer_ws.update_cell(sl_section_row, 2, "📞 SUPPORT LOG")

    # Column headers at B (not A) — 13 columns from B to N
    viewer_ws.update(
        values=[SUPPORT_LOG_HEADERS],
        range_name=f"B{sl_header_row}:N{sl_header_row}",
        value_input_option="USER_ENTERED",
    )
    print(f"  Written support log headers at B{sl_header_row}:N{sl_header_row}")

    # SORT formula at B (not A) — spills from B to N
    sort_formula = (
        "=IFERROR(SORT(FILTER("
        "'Support Log'!A:M,"
        "'Support Log'!B:B=$D$4"
        "),3,FALSE),)"
    )
    viewer_ws.update_cell(sl_data_row, 2, sort_formula)  # column B = 2
    print(f"  Written SORT formula at B{sl_data_row}")

    # 6. Build all batch requests: merges + formatting + column widths
    all_requests = []

    # ── 6a. Re-merge Implementation Details cells for wide value display ──

    # Section title: merge B:N for full-width banner
    all_requests.append({"mergeCells": {
        "range": {
            "sheetId": sheet_id,
            "startRowIndex": impl_section_row - 1,
            "endRowIndex": impl_section_row,
            "startColumnIndex": 1, "endColumnIndex": 14,
        },
        "mergeType": "MERGE_ALL",
    }})
    # Sub-header "Value": merge C:N
    all_requests.append({"mergeCells": {
        "range": {
            "sheetId": sheet_id,
            "startRowIndex": impl_sub_header_row - 1,
            "endRowIndex": impl_sub_header_row,
            "startColumnIndex": 2, "endColumnIndex": 14,
        },
        "mergeType": "MERGE_ALL",
    }})
    # Data rows: merge C:N for each value cell
    for row in range(impl_data_start, impl_data_end + 1):
        all_requests.append({"mergeCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row - 1,
                "endRowIndex": row,
                "startColumnIndex": 2, "endColumnIndex": 14,
            },
            "mergeType": "MERGE_ALL",
        }})
    # Support log section title: merge B:N
    all_requests.append({"mergeCells": {
        "range": {
            "sheetId": sheet_id,
            "startRowIndex": sl_section_row - 1,
            "endRowIndex": sl_section_row,
            "startColumnIndex": 1, "endColumnIndex": 14,
        },
        "mergeType": "MERGE_ALL",
    }})
    merge_count = len(all_requests)

    # ── 6b. Section title formatting — dark blue band ──
    for title_row in [impl_section_row, sl_section_row]:
        all_requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": title_row - 1,
                    "endRowIndex": title_row,
                    "startColumnIndex": 1,   # B
                    "endColumnIndex": 14,    # N+1
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _HEADER_BG,
                        "textFormat": {
                            "foregroundColor": _HEADER_TEXT,
                            "bold": True,
                        },
                    },
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        })

    # ── 6c. Impl Details sub-header formatting (dark blue, matches SL headers) ──
    all_requests.append({
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": impl_sub_header_row - 1,
                "endRowIndex": impl_sub_header_row,
                "startColumnIndex": 1,   # B
                "endColumnIndex": 14,    # N+1 (covers merged Value cell)
            },
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {
                        "foregroundColor": _HEADER_TEXT,
                        "bold": True,
                    },
                    "horizontalAlignment": "CENTER",
                },
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
        }
    })

    # ── 6d. Support Log header formatting (dark blue bg, white text, bold) B:N ──
    all_requests.append({
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": sl_header_row - 1,
                "endRowIndex": sl_header_row,
                "startColumnIndex": 1,   # B
                "endColumnIndex": 14,    # N+1
            },
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {
                        "foregroundColor": _HEADER_TEXT,
                        "bold": True,
                    },
                    "horizontalAlignment": "CENTER",
                },
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
        }
    })

    # ── 6e. Date formatting for Received Date (D) and Resolved Date (E) ──
    all_requests.append({
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": sl_data_row - 1,
                "endRowIndex": sl_data_end_row,
                "startColumnIndex": 3,   # D (Received Date)
                "endColumnIndex": 5,     # E+1 (Resolved Date)
            },
            "cell": {
                "userEnteredFormat": {
                    "numberFormat": {
                        "type": "DATE",
                        "pattern": "yyyy-MM-dd",
                    },
                },
            },
            "fields": "userEnteredFormat.numberFormat",
        }
    })

    # ── 6f. Column widths for cohesive table layout ──
    for col_idx, width in _COL_WIDTHS:
        all_requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": col_idx,
                    "endIndex": col_idx + 1,
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize",
            }
        })

    viewer_ws.spreadsheet.batch_update({"requests": all_requests})
    print(f"  Applied {merge_count} merges + formatting + {len(_COL_WIDTHS)} column widths")

    print("\nSite Viewer layout fix complete.")
    return summary


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()

    import gspread
    from google.oauth2.service_account import Credentials

    dry_run = "--dry-run" in sys.argv

    creds_json = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(os.environ["GOOGLE_SHEET_ID"])

    viewer_ws = spreadsheet.worksheet("Site Viewer")
    impl_ws = spreadsheet.worksheet("Implementation Details")

    if dry_run:
        print("DRY RUN — no changes will be applied.\n")

    fix_layout(viewer_ws, impl_ws, dry_run=dry_run)


if __name__ == "__main__":
    main()
