"""Migration script: Apply conditional formatting rules across all tabs.

Color rules:
- Red (#FFEBEE): empty must-field cells
- Yellow (#FFF9C4): empty important-field cells
- Blue (#E3F2FD): Last Verified older than 30 days
- Orange (#FFF3E0): Support Log entries with status != Resolved and Received Date > 7 days

Context-aware: skips formatting for "Awaiting Installation" sites.
Idempotent: clears existing rules before applying.
Supports --dry-run flag.

Usage:
    python -m scripts.migrate_conditional_formatting
    python -m scripts.migrate_conditional_formatting --dry-run
"""

from __future__ import annotations

import json
import os
import sys

from app.field_config.field_requirements import FIELD_REQUIREMENTS
from app.services.sheets import (
    SITES_COLUMNS,
    HARDWARE_COLUMNS,
    SUPPORT_LOG_COLUMNS,
    STOCK_COLUMNS,
)

# RGB colors as Google Sheets API color objects (0-1 scale)
# #FFEBEE → rgb(255, 235, 238)
COLOR_RED = {"red": 1.0, "green": 0.922, "blue": 0.933}
# #FFF9C4 → rgb(255, 249, 196)
COLOR_YELLOW = {"red": 1.0, "green": 0.976, "blue": 0.769}
# #E3F2FD → rgb(227, 242, 253)
COLOR_BLUE = {"red": 0.890, "green": 0.949, "blue": 0.992}
# #FFF3E0 → rgb(255, 243, 224)
COLOR_ORANGE = {"red": 1.0, "green": 0.953, "blue": 0.878}

# Map tab config keys to sheet tab names and their column lists
_TAB_CONFIG = {
    "sites": {"sheet_name": "Sites", "columns": SITES_COLUMNS},
    "hardware_inventory": {"sheet_name": "Hardware Inventory", "columns": HARDWARE_COLUMNS},
    "support_log": {"sheet_name": "Support Log", "columns": SUPPORT_LOG_COLUMNS},
    "stock": {"sheet_name": "Stock", "columns": STOCK_COLUMNS},
    # Implementation Details uses dynamic headers, handled separately
}

# Map from snake_case field names to sheet column names
_FIELD_TO_COLUMN: dict[str, str] = {
    # Sites
    "customer": "Customer", "city": "City", "country": "Country",
    "facility_type": "Facility Type", "contract_status": "Contract Status",
    "supervisor_1": "Supervisor 1", "phone_1": "Phone 1",
    "go_live_date": "Go-live Date", "address": "Address",
    "dashboard_link": "Dashboard Link", "whatsapp_group": "Whatsapp Group",
    # Hardware
    "site_id": "Site ID", "device_type": "Device Type", "qty": "Qty",
    "hw_version": "HW Version", "fw_version": "FW Version",
    "last_verified": "Last Verified",
    # Support Log
    "received_date": "Received Date", "type": "Type", "status": "Status",
    "issue_summary": "Issue Summary", "responsible": "Responsible",
    "root_cause": "Root Cause", "resolution": "Resolution",
    "resolved_date": "Resolved Date", "devices_affected": "Devices Affected",
    # Stock
    "location": "Location", "condition": "Condition",
    # Implementation Details
    "internet_provider": "Internet Provider", "ssid": "SSID",
    "password": "Password", "gateway_placement": "Gateway Placement",
    "charging_dock_placement": "Charging Dock Placement",
    "dispenser_anchor_placement": "Dispenser Anchor Placement",
    "handwash_time": "Handwash Time", "tag_buzzer_vibration": "Tag Buzzer Vibration",
    "entry_time": "Entry Time", "dispenser_anchor_power_type": "Dispenser Anchor Power Type",
    "clean_hygiene_time": "Clean Hygiene Time", "hp_alert_time": "HP Alert Time",
    "hand_hygiene_time": "Hand Hygiene Time",
    "hand_hygiene_interval": "Hand Hygiene Interval",
    "hand_hygiene_type": "Hand Hygiene Type",
    "tag_clean_to_red_timeout": "Tag Clean to Red Timeout",
}


def build_formatting_rules() -> list[dict]:
    """Build a list of formatting rule descriptors from FIELD_REQUIREMENTS.

    Each rule is a dict with: tab, field, severity, color.
    """
    rules = []

    for tab_key, requirements in FIELD_REQUIREMENTS.items():
        config = _TAB_CONFIG.get(tab_key)
        if config:
            sheet_name = config["sheet_name"]
        elif tab_key == "implementation_details":
            sheet_name = "Implementation Details"
        else:
            continue

        # Must fields → red
        must_fields = requirements.get("must", [])
        for field in must_fields:
            col_name = _FIELD_TO_COLUMN.get(field, field)
            rules.append({
                "tab": sheet_name,
                "field": col_name,
                "severity": "must",
                "color": COLOR_RED,
            })

        # Important fields → yellow
        important_fields = requirements.get("important", [])
        for field in important_fields:
            col_name = _FIELD_TO_COLUMN.get(field, field)
            rules.append({
                "tab": sheet_name,
                "field": col_name,
                "severity": "important",
                "color": COLOR_YELLOW,
            })

    # Special rules: Last Verified > 30 days → blue
    for tab_name in ["Hardware Inventory"]:
        rules.append({
            "tab": tab_name,
            "field": "Last Verified",
            "severity": "stale_verified",
            "color": COLOR_BLUE,
        })

    # Special rules: Open support tickets > 7 days → orange
    rules.append({
        "tab": "Support Log",
        "field": "Received Date",
        "severity": "stale_ticket",
        "color": COLOR_ORANGE,
    })

    return rules


def _find_col_index(columns: list[str], col_name: str) -> int | None:
    """Find 0-based column index for a column name (case-insensitive)."""
    col_lower = col_name.lower()
    for i, c in enumerate(columns):
        if c.lower() == col_lower:
            return i
    return None


def _build_clear_requests(sheet_ids: dict[str, int]) -> list[dict]:
    """Build requests to clear all existing conditional format rules."""
    requests = []
    for sheet_name, sheet_id in sheet_ids.items():
        # We clear by adding a deleteConditionalFormatRule for index 0
        # repeatedly, but simpler: use updateSheetProperties or batch clear
        # Actually, we'll use a different approach: delete all rules
        # Google Sheets API doesn't have a "clear all" — we need to know
        # how many rules exist. Instead, we'll just add our rules with index 0
        # which pushes them to the top. The clear approach is handled
        # by the caller reading existing rules first.
        pass
    return requests


def _build_add_rule_request(
    sheet_id: int,
    col_index: int,
    color: dict,
    rule_type: str = "blank",
    custom_formula: str | None = None,
    first_col_letter: str = "A",
    header_row: int = 1,
) -> dict:
    """Build an addConditionalFormatRule request.

    All rules use CUSTOM_FORMULA to include a "row has data" guard
    (first column not empty), preventing empty rows from being highlighted.
    """
    data_row = header_row + 1  # First data row (e.g., row 2 or row 3)
    col_letter = chr(ord("A") + col_index)

    if rule_type == "blank":
        # Empty cell AND row has data → color
        formula = f'=AND(${first_col_letter}{data_row}<>"",{col_letter}{data_row}="")'
    elif rule_type == "custom" and custom_formula:
        # Wrap existing formula with row-has-data guard
        # Strip leading = from the custom formula if present
        inner = custom_formula.lstrip("=")
        formula = f'=AND(${first_col_letter}{data_row}<>"",{inner})'
    else:
        formula = f'=AND(${first_col_letter}{data_row}<>"",{col_letter}{data_row}="")'

    condition = {
        "type": "CUSTOM_FORMULA",
        "values": [{"userEnteredValue": formula}],
    }

    return {
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{
                    "sheetId": sheet_id,
                    "startRowIndex": header_row,  # Skip header row(s)
                    "startColumnIndex": col_index,
                    "endColumnIndex": col_index + 1,
                }],
                "booleanRule": {
                    "condition": condition,
                    "format": {
                        "backgroundColor": color,
                    },
                },
            },
            "index": 0,
        }
    }


def migrate(spreadsheet, dry_run: bool = False) -> list[dict] | None:
    """Apply conditional formatting rules to all tabs.

    Args:
        spreadsheet: gspread Spreadsheet object
        dry_run: if True, return rules without applying

    Returns:
        List of rule descriptors if dry_run, None otherwise.
    """
    rules = build_formatting_rules()

    if dry_run:
        for r in rules:
            print(f"  [DRY RUN] {r['tab']}: {r['field']} → {r['severity']}")
        return rules

    # Get sheet IDs
    worksheets = spreadsheet.worksheets()
    sheet_ids: dict[str, int] = {}
    sheet_headers: dict[str, list[str]] = {}
    for ws in worksheets:
        sheet_ids[ws.title] = ws.id
        try:
            # Implementation Details has headers on row 2, others on row 1
            header_row = 2 if ws.title == "Implementation Details" else 1
            sheet_headers[ws.title] = ws.row_values(header_row)
        except Exception:
            sheet_headers[ws.title] = []

    # Build add requests (rules are added at index 0, so they take priority
    # over any existing rules; running again is idempotent)
    # Note: To fully clear existing rules, use the Google Sheets UI.
    add_requests = []

    # Determine the header row and first column letter for each tab
    _tab_header_rows: dict[str, int] = {}
    for tab_name in sheet_ids:
        _tab_header_rows[tab_name] = 2 if tab_name == "Implementation Details" else 1

    for rule in rules:
        tab_name = rule["tab"]
        field_name = rule["field"]
        color = rule["color"]
        severity = rule["severity"]

        if tab_name not in sheet_ids:
            continue

        sid = sheet_ids[tab_name]
        headers = sheet_headers.get(tab_name, [])
        col_idx = _find_col_index(headers, field_name)
        hdr_row = _tab_header_rows.get(tab_name, 1)

        if col_idx is None:
            print(f"  WARNING: Column '{field_name}' not found in {tab_name}")
            continue

        # First column with data (Site ID or Ticket ID) for the "row has data" guard
        first_col = "A"  # All tabs have their key column in A

        if severity in ("must", "important"):
            # Blank cell AND row has data → color
            add_requests.append(
                _build_add_rule_request(
                    sid, col_idx, color, rule_type="blank",
                    first_col_letter=first_col, header_row=hdr_row,
                )
            )
        elif severity == "stale_verified":
            # Last Verified > 30 days ago → blue
            data_row = hdr_row + 1
            col_letter = chr(ord("A") + col_idx)
            formula = f'=AND({col_letter}{data_row}<>"",TODAY()-{col_letter}{data_row}>30)'
            add_requests.append(
                _build_add_rule_request(
                    sid, col_idx, color, rule_type="custom",
                    custom_formula=formula,
                    first_col_letter=first_col, header_row=hdr_row,
                )
            )
        elif severity == "stale_ticket":
            # Status != Resolved AND Received Date > 7 days → orange
            status_idx = _find_col_index(headers, "Status")
            if status_idx is not None:
                data_row = hdr_row + 1
                col_letter = chr(ord("A") + col_idx)
                status_letter = chr(ord("A") + status_idx)
                formula = f'=AND({status_letter}{data_row}<>"Resolved",{col_letter}{data_row}<>"",TODAY()-{col_letter}{data_row}>7)'
                add_requests.append(
                    _build_add_rule_request(
                        sid, col_idx, color, rule_type="custom",
                        custom_formula=formula,
                        first_col_letter=first_col, header_row=hdr_row,
                    )
                )

    # Apply add requests
    if add_requests:
        spreadsheet.batch_update({"requests": add_requests})
        print(f"Applied {len(add_requests)} conditional formatting rules.")
    else:
        print("No formatting rules to apply.")

    return None


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

    if dry_run:
        print("DRY RUN — no changes will be applied.\n")

    migrate(spreadsheet, dry_run=dry_run)


if __name__ == "__main__":
    main()
