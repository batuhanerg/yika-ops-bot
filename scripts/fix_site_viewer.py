"""Hotfix: Fix Site Viewer formulas after selector format change.

Bug 1: The selector (C4) now shows "Customer (Site ID)" format, but all
VLOOKUP/INDEX/FILTER formulas downstream reference $C$4 expecting a raw
Site ID. Fix: add a helper cell (D4) that extracts the Site ID via
REGEXEXTRACT, and update all formulas to reference $D$4 instead.

Bug 2: The SORT(FILTER(...)) formula in A62 conflicts with individual
INDEX/FILTER formulas in B62-H81 (SORT tries to spill across columns
but existing formulas block it → #REF!). Fix: clear B62-M81 and let
SORT handle the full spill.

Usage:
    python -m scripts.fix_site_viewer
    python -m scripts.fix_site_viewer --dry-run
"""

from __future__ import annotations

import json
import os
import sys

import requests


# The helper cell column offset from the selector cell (1 column to the right)
_HELPER_COL_OFFSET = 1


def _find_selector_cell(all_values: list[list[str]]) -> tuple[int, int] | None:
    """Find the selector cell (next to 'Select Site:'). Returns (row, col) 1-based."""
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


def _col_letter(idx: int) -> str:
    """Convert 0-based column index to letter (A, B, ..., Z, AA, ...)."""
    if idx < 26:
        return chr(ord("A") + idx)
    return chr(ord("A") + idx // 26 - 1) + chr(ord("A") + idx % 26)


def fix(viewer_ws, dry_run: bool = False) -> dict:
    """Fix Site Viewer formulas to use helper cell for Site ID extraction.

    Returns a summary dict with counts of changes made.
    """
    all_values = viewer_ws.get_all_values()

    # 1. Find layout positions
    selector_pos = _find_selector_cell(all_values)
    sl_section_row = _find_support_log_section(all_values)

    selector_row = selector_pos[0] if selector_pos else 4
    selector_col = selector_pos[1] if selector_pos else 3  # C = 3
    helper_col = selector_col + _HELPER_COL_OFFSET  # D = 4

    selector_letter = _col_letter(selector_col - 1)  # C
    helper_letter = _col_letter(helper_col - 1)  # D

    sl_header_row = (sl_section_row + 1) if sl_section_row else 61
    sl_data_row = sl_header_row + 1

    print(f"  Selector: {selector_letter}{selector_row}")
    print(f"  Helper cell: {helper_letter}{selector_row}")
    print(f"  Support log data starts at row {sl_data_row}")

    # 2. Read all formulas via the Sheets API
    from google.auth.transport.requests import Request

    spreadsheet_id = viewer_ws.spreadsheet.id
    creds = viewer_ws.spreadsheet.client.auth

    if hasattr(creds, "refresh") and hasattr(creds, "token"):
        try:
            creds.refresh(Request())
        except Exception:
            pass
    token = creds.token

    resp = requests.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}",
        params={
            "ranges": f"'{viewer_ws.title}'",
            "fields": "sheets.data.rowData.values.userEnteredValue",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    data = resp.json()

    rows_data = data["sheets"][0]["data"][0].get("rowData", [])

    # 3. Find all cells with formulas referencing the selector
    old_ref = f"${selector_letter}${selector_row}"  # $C$4
    new_ref = f"${helper_letter}${selector_row}"  # $D$4

    formula_updates = []  # (row_1based, col_1based, new_formula)

    for i, row in enumerate(rows_data):
        values = row.get("values", [])
        for j, val in enumerate(values):
            uev = val.get("userEnteredValue", {})
            formula = uev.get("formulaValue")
            if formula and old_ref in formula:
                new_formula = formula.replace(old_ref, new_ref)
                formula_updates.append((i + 1, j + 1, new_formula))

    # Also handle non-absolute references like C4 in REGEXEXTRACT
    selector_cell_ref = f"{selector_letter}{selector_row}"
    for i, row in enumerate(rows_data):
        values = row.get("values", [])
        for j, val in enumerate(values):
            uev = val.get("userEnteredValue", {})
            formula = uev.get("formulaValue")
            if formula and selector_cell_ref in formula and old_ref not in formula:
                # This has C4 but not $C$4 (like the REGEXEXTRACT formula)
                # The SORT formula references C4 — update to use $D$4 directly
                # Remove REGEXEXTRACT wrapper since helper cell does the extraction
                new_formula = formula.replace(
                    f'REGEXEXTRACT({selector_cell_ref},"\\(([^)]+)\\)")',
                    new_ref,
                )
                if new_formula == formula:
                    # Fallback: just replace the cell reference
                    new_formula = formula.replace(selector_cell_ref, new_ref)
                # Only add if not already in formula_updates
                if not any(u[0] == i + 1 and u[1] == j + 1 for u in formula_updates):
                    formula_updates.append((i + 1, j + 1, new_formula))

    # 4. Always clear the full support log spill area (B-M, 20 rows)
    # The SORT formula in column A spills across all columns, so clear B onward
    # We clear unconditionally because get_all_values() may not return rows
    # that only contain formulas (e.g., rows 63-81 with INDEX/FILTER).
    sl_data_end_row = sl_data_row + 19  # always 20 rows

    # 5. Build the helper cell formula
    helper_formula = f'=IFERROR(REGEXEXTRACT({selector_letter}{selector_row},"\\(([^)]+)\\)"),{selector_letter}{selector_row})'

    # 6. Build the updated SORT formula (simplified, using helper cell directly)
    sort_formula = (
        f"=IFERROR(SORT(FILTER("
        f"'Support Log'!A:M,"
        f"'Support Log'!B:B={new_ref}"
        f"),3,FALSE),)"
    )

    clear_range = f"B{sl_data_row}:M{sl_data_end_row}"

    summary = {
        "helper_cell": f"{helper_letter}{selector_row}",
        "helper_formula": helper_formula,
        "formula_updates": len(formula_updates),
        "clear_range": clear_range,
        "sort_formula_cell": f"A{sl_data_row}",
    }

    print(f"\n  Formula updates: {len(formula_updates)}")
    print(f"  Support log clear range: {clear_range}")

    if dry_run:
        print("\n  [DRY RUN] No changes applied.")
        for r, c, f in formula_updates[:10]:
            print(f"    {_col_letter(c-1)}{r}: {f[:80]}...")
        return summary

    # 7. Apply changes

    # 7a. Write the helper cell formula
    viewer_ws.update_cell(selector_row, helper_col, helper_formula)
    print(f"  Written helper cell: {helper_letter}{selector_row}")

    # 7b. Clear the full support log spill area (20 rows × 12 columns)
    empty_rows = [[""] * 12 for _ in range(sl_data_end_row - sl_data_row + 1)]
    viewer_ws.update(
        values=empty_rows,
        range_name=clear_range,
        value_input_option="USER_ENTERED",
    )
    print(f"  Cleared support log spill area: {clear_range}")

    # 7c. Update the SORT formula to use helper cell
    viewer_ws.update_cell(sl_data_row, 1, sort_formula)
    print(f"  Updated SORT formula at A{sl_data_row}")

    # 7d. Update all other formulas that referenced $C$4
    # Batch update: group by contiguous ranges where possible
    # Use individual update_cell calls (there are ~60 formulas)
    # To stay under rate limits, batch into a single batch_update
    batch_requests = []
    sheet_id = viewer_ws.id

    for r, c, new_formula in formula_updates:
        # Skip the SORT formula cell — we already wrote it
        if r == sl_data_row and c == 1:
            continue
        # Skip cells in the cleared support log area
        if sl_data_row <= r <= sl_data_end_row and 2 <= c <= 13:
            continue

        batch_requests.append({
            "updateCells": {
                "rows": [{
                    "values": [{
                        "userEnteredValue": {"formulaValue": new_formula},
                    }],
                }],
                "fields": "userEnteredValue",
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": r - 1,
                    "endRowIndex": r,
                    "startColumnIndex": c - 1,
                    "endColumnIndex": c,
                },
            }
        })

    if batch_requests:
        viewer_ws.spreadsheet.batch_update({"requests": batch_requests})
        print(f"  Updated {len(batch_requests)} formula cells ($C$4 → $D$4)")

    print("\nSite Viewer fix complete.")
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

    if dry_run:
        print("DRY RUN — no changes will be applied.\n")

    fix(viewer_ws, dry_run=dry_run)


if __name__ == "__main__":
    main()
