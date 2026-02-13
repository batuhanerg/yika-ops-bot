"""Migration script: Apply conditional formatting rules across all tabs.

Color rules:
- Red (#FFEBEE): empty must-field cells
- Yellow (#FFF9C4): empty important-field cells
- Blue (#E3F2FD): Last Verified older than 30 days
- Orange (#FFF3E0): Support Log entries with status != Resolved and Received Date > 3 days

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

import requests as http_requests

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

    # Special rules: Last Verified empty or > 30 days → blue (HW, Impl, Stock)
    for tab_name in ["Hardware Inventory", "Implementation Details", "Stock"]:
        rules.append({
            "tab": tab_name,
            "field": "Last Verified",
            "severity": "stale_verified",
            "color": COLOR_BLUE,
        })

    # Special rules: Open support tickets > 3 days → orange (full row)
    rules.append({
        "tab": "Support Log",
        "field": "Received Date",
        "severity": "stale_ticket",
        "color": COLOR_ORANGE,
    })

    # Device type conditional: Tag/Anchor/Gateway → yellow for HW/FW Version
    for field in ["hw_version", "fw_version"]:
        col_name = _FIELD_TO_COLUMN.get(field, field)
        rules.append({
            "tab": "Hardware Inventory",
            "field": col_name,
            "severity": "device_type_conditional",
            "color": COLOR_YELLOW,
        })

    # Facility type conditional: Food/Healthcare → red for specific fields
    # (must_when_facility_type = must-level when condition met)
    facility_rules = FIELD_REQUIREMENTS.get("implementation_details", {}).get(
        "must_when_facility_type", {}
    )
    for facility_type, fields in facility_rules.items():
        for field in fields:
            col_name = _FIELD_TO_COLUMN.get(field, field)
            rules.append({
                "tab": "Implementation Details",
                "field": col_name,
                "severity": f"facility_{facility_type.lower()}",
                "color": COLOR_RED,
            })

    # Support Log conditional rules from important_conditional
    sl_conditional = FIELD_REQUIREMENTS.get("support_log", {}).get(
        "important_conditional", {}
    )
    for field, rule in sl_conditional.items():
        col_name = _FIELD_TO_COLUMN.get(field, field)
        if isinstance(rule, dict):
            if "required_when_status_not" in rule:
                rules.append({
                    "tab": "Support Log",
                    "field": col_name,
                    "severity": "sl_conditional_status_not",
                    "color": COLOR_RED,
                    "status_not": rule["required_when_status_not"],
                })
            elif "required_when_status" in rule:
                rules.append({
                    "tab": "Support Log",
                    "field": col_name,
                    "severity": "sl_conditional_status",
                    "color": COLOR_RED,
                    "status_values": rule["required_when_status"],
                })
        elif rule == "always_important":
            rules.append({
                "tab": "Support Log",
                "field": col_name,
                "severity": "important",
                "color": COLOR_YELLOW,
            })

    return rules


def _find_col_index(columns: list[str], col_name: str) -> int | None:
    """Find 0-based column index for a column name (case-insensitive)."""
    col_lower = col_name.lower()
    for i, c in enumerate(columns):
        if c.lower() == col_lower:
            return i
    return None


def _delete_existing_rules(spreadsheet) -> int:
    """Delete all existing conditional formatting rules from all sheets.

    Uses the Sheets API to discover rule counts, then deletes from
    highest index to lowest so indices don't shift.

    Returns the number of rules deleted.
    """
    try:
        from google.auth.transport.requests import Request
        creds = spreadsheet.client.auth
        if hasattr(creds, "refresh"):
            creds.refresh(Request())

        resp = http_requests.get(
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet.id}",
            params={"fields": "sheets(properties.sheetId,conditionalFormats)"},
            headers={"Authorization": f"Bearer {creds.token}"},
        )
        if resp.status_code != 200:
            print(f"  WARNING: Could not fetch existing rules (HTTP {resp.status_code})")
            return 0

        data = resp.json()
    except Exception as e:
        print(f"  WARNING: Could not fetch existing rules ({e})")
        return 0

    delete_requests = []
    for sheet in data.get("sheets", []):
        sid = sheet.get("properties", {}).get("sheetId")
        if sid is None:
            continue
        formats = sheet.get("conditionalFormats", [])
        # Delete from highest index to lowest
        for i in range(len(formats) - 1, -1, -1):
            delete_requests.append({
                "deleteConditionalFormatRule": {
                    "sheetId": sid,
                    "index": i,
                }
            })

    if delete_requests:
        spreadsheet.batch_update({"requests": delete_requests})

    return len(delete_requests)


# Site Viewer layout: site info fields in column C
# Must fields → red, Important fields → yellow (only when a site is selected)
_SITE_VIEWER_MUST_ROWS = [7, 8, 9, 11, 13, 14, 20]  # Customer,City,Country,Facility,Sup1,Phone1,Contract
_SITE_VIEWER_IMPORTANT_ROWS = [10, 12, 19]  # Address, Dashboard Link, Go-live Date

# Reverse map: Implementation Details column_name_lowercase → severity
_impl_field_severity: dict[str, str] = {}
for _f in FIELD_REQUIREMENTS.get("implementation_details", {}).get("must", []):
    _impl_field_severity[_FIELD_TO_COLUMN.get(_f, _f).lower()] = "must"
for _f in FIELD_REQUIREMENTS.get("implementation_details", {}).get("important", []):
    _impl_field_severity[_FIELD_TO_COLUMN.get(_f, _f).lower()] = "important"


def _build_site_viewer_requests(sheet_id: int) -> list[dict]:
    """Build conditional formatting requests for Site Viewer site info section."""
    add_requests = []
    helper_ref = "$D$4"  # Extracted Site ID
    col_c = 2  # 0-based column index for column C

    for row in _SITE_VIEWER_MUST_ROWS:
        formula = f'=AND({helper_ref}<>"",C{row}="")'
        add_requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": sheet_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": col_c,
                        "endColumnIndex": col_c + 1,
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": formula}],
                        },
                        "format": {"backgroundColor": COLOR_RED},
                    },
                },
                "index": 0,
            }
        })

    for row in _SITE_VIEWER_IMPORTANT_ROWS:
        formula = f'=AND({helper_ref}<>"",C{row}="")'
        add_requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": sheet_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": col_c,
                        "endColumnIndex": col_c + 1,
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": formula}],
                        },
                        "format": {"backgroundColor": COLOR_YELLOW},
                    },
                },
                "index": 0,
            }
        })

    return add_requests


def _build_site_viewer_data_requests(
    sheet_id: int,
    viewer_content: list[list[str]],
) -> list[dict]:
    """Build conditional formatting for Site Viewer data sections.

    Detects section positions from the viewer content and builds rules for:
    - Implementation Details parameter values (column C)
    - Hardware Inventory data (columns B-G)
    - Support Log data (columns B-N)
    """
    add_requests = []
    helper_ref = "$D$4"

    # Detect section positions
    hw_section = impl_section = sl_section = None
    for i, row in enumerate(viewer_content):
        row_text = " ".join(row).upper()
        if "HARDWARE INVENTORY" in row_text:
            hw_section = i + 1  # 1-based
        elif "IMPLEMENTATION DETAILS" in row_text:
            impl_section = i + 1
        elif "SUPPORT LOG" in row_text:
            sl_section = i + 1

    # --- Implementation Details: parameter values in column C ---
    if impl_section:
        impl_data_start = impl_section + 2  # skip section header + sub-header
        for i in range(impl_data_start - 1, len(viewer_content)):
            row = viewer_content[i]
            param_name = row[1].strip() if len(row) > 1 else ""
            if not param_name:
                break
            severity = _impl_field_severity.get(param_name.lower())
            if severity == "must":
                color = COLOR_RED
            elif severity == "important":
                color = COLOR_YELLOW
            else:
                continue
            row_num = i + 1  # 1-based
            formula = f'=AND({helper_ref}<>"",C{row_num}="")'
            add_requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": sheet_id,
                            "startRowIndex": i,
                            "endRowIndex": i + 1,
                            "startColumnIndex": 2,  # C
                            "endColumnIndex": 3,
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "CUSTOM_FORMULA",
                                "values": [{"userEnteredValue": formula}],
                            },
                            "format": {"backgroundColor": color},
                        },
                    },
                    "index": 0,
                }
            })

    # --- Hardware Inventory: columns B-G ---
    if hw_section:
        hw_data_start = hw_section + 2  # section header + column headers
        # Determine end: up to impl_section or 15 rows max
        hw_data_end = min(
            hw_data_start + 14,
            (impl_section - 2) if impl_section else hw_data_start + 14,
        )
        data_row = hw_data_start

        # Must: Device Type (B=1), Qty (E=4)
        for col_idx in [1, 4]:
            col_letter = chr(ord("A") + col_idx)
            formula = f'=AND({helper_ref}<>"",$B{data_row}<>"",{col_letter}{data_row}="")'
            add_requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": sheet_id,
                            "startRowIndex": hw_data_start - 1,
                            "endRowIndex": hw_data_end,
                            "startColumnIndex": col_idx,
                            "endColumnIndex": col_idx + 1,
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "CUSTOM_FORMULA",
                                "values": [{"userEnteredValue": formula}],
                            },
                            "format": {"backgroundColor": COLOR_RED},
                        },
                    },
                    "index": 0,
                }
            })

        # HW/FW Version yellow for Tag/Anchor/Gateway: C(2), D(3)
        for col_idx in [2, 3]:
            col_letter = chr(ord("A") + col_idx)
            formula = (
                f'=AND({helper_ref}<>"",$B{data_row}<>"",'
                f'OR($B{data_row}="Tag",$B{data_row}="Anchor",$B{data_row}="Gateway"),'
                f'{col_letter}{data_row}="")'
            )
            add_requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": sheet_id,
                            "startRowIndex": hw_data_start - 1,
                            "endRowIndex": hw_data_end,
                            "startColumnIndex": col_idx,
                            "endColumnIndex": col_idx + 1,
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "CUSTOM_FORMULA",
                                "values": [{"userEnteredValue": formula}],
                            },
                            "format": {"backgroundColor": COLOR_YELLOW},
                        },
                    },
                    "index": 0,
                }
            })

        # Last Verified stale (F=5): empty or > 30 days
        formula = f'=AND({helper_ref}<>"",$B{data_row}<>"",TODAY()-F{data_row}>30)'
        add_requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": sheet_id,
                        "startRowIndex": hw_data_start - 1,
                        "endRowIndex": hw_data_end,
                        "startColumnIndex": 5,  # F
                        "endColumnIndex": 6,
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": formula}],
                        },
                        "format": {"backgroundColor": COLOR_BLUE},
                    },
                },
                "index": 0,
            }
        })

    # --- Support Log: columns B-N, must fields ---
    if sl_section:
        sl_data_row = sl_section + 2  # section header + column headers
        sl_data_end = sl_data_row + 19  # 20 rows

        # SORT starts at B, so columns are:
        # B=Ticket, C=Site ID, D=Received, E=Resolved, F=Type, G=Status,
        # H=Root Cause, I=Reported By, J=Issue Summary, K=Resolution,
        # L=Devices Affected, M=Responsible, N=Notes
        sl_must_cols = [2, 3, 5, 6, 9, 12]  # C,D,F,G,J,M (0-based)
        for col_idx in sl_must_cols:
            col_letter = chr(ord("A") + col_idx)
            formula = f'=AND({helper_ref}<>"",$B{sl_data_row}<>"",{col_letter}{sl_data_row}="")'
            add_requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": sheet_id,
                            "startRowIndex": sl_data_row - 1,
                            "endRowIndex": sl_data_end,
                            "startColumnIndex": col_idx,
                            "endColumnIndex": col_idx + 1,
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "CUSTOM_FORMULA",
                                "values": [{"userEnteredValue": formula}],
                            },
                            "format": {"backgroundColor": COLOR_RED},
                        },
                    },
                    "index": 0,
                }
            })

    return add_requests


def _build_device_type_version_requests(
    sheet_id: int,
    headers: list[str],
    header_row: int = 1,
) -> list[dict]:
    """Build conditional formatting: yellow for HW/FW Version when Device Type is Tag, Anchor, or Gateway."""
    device_type_idx = _find_col_index(headers, "Device Type")
    hw_idx = _find_col_index(headers, "HW Version")
    fw_idx = _find_col_index(headers, "FW Version")

    if device_type_idx is None:
        return []

    add_requests = []
    data_row = header_row + 1
    dt_letter = chr(ord("A") + device_type_idx)

    for ver_idx in [hw_idx, fw_idx]:
        if ver_idx is None:
            continue
        ver_letter = chr(ord("A") + ver_idx)
        formula = (
            f'=AND($A{data_row}<>"",'
            f'OR(${dt_letter}{data_row}="Tag",${dt_letter}{data_row}="Anchor",${dt_letter}{data_row}="Gateway"),'
            f'{ver_letter}{data_row}="")'
        )
        add_requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": sheet_id,
                        "startRowIndex": header_row,
                        "startColumnIndex": ver_idx,
                        "endColumnIndex": ver_idx + 1,
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": formula}],
                        },
                        "format": {"backgroundColor": COLOR_YELLOW},
                    },
                },
                "index": 0,
            }
        })

    return add_requests


def _setup_facility_type_helper(spreadsheet, impl_headers, sites_headers):
    """Add a _FacilityType helper column to Implementation Details.

    Writes an ARRAYFORMULA that VLOOKUPs each row's Site ID → Facility Type
    from the Sites tab. This is needed because Google Sheets API does not
    support cross-sheet references in conditional formatting formulas.

    Returns the 0-based column index of the helper column, or None.
    """
    ft_idx = _find_col_index(sites_headers, "Facility Type")
    if ft_idx is None:
        return None

    # Check if helper column already exists
    helper_name = "_FacilityType"
    existing_idx = _find_col_index(impl_headers, helper_name)
    if existing_idx is not None:
        return existing_idx

    helper_idx = len(impl_headers)
    ft_col_letter = chr(ord("A") + ft_idx)
    vlookup_col = ft_idx + 1

    try:
        ws = spreadsheet.worksheet("Implementation Details")
        # Write header at row 2
        ws.update_cell(2, helper_idx + 1, helper_name)
        # Write ARRAYFORMULA at row 3 (first data row)
        formula = (
            f'=ARRAYFORMULA(IF(A3:A="","",IFERROR(VLOOKUP(A3:A,'
            f"Sites!$A:${ft_col_letter},{vlookup_col},FALSE)" ',"")))'
        )
        ws.update_cell(3, helper_idx + 1, formula)
        print(f"  Implementation Details: added _FacilityType helper column at {chr(ord('A') + helper_idx)}")
        return helper_idx
    except Exception as e:
        print(f"  WARNING: Could not add facility type helper column ({e})")
        return None


def _build_facility_type_conditional_requests(
    sheet_id: int,
    impl_headers: list[str],
    facility_type_col_idx: int,
    header_row: int = 2,
) -> list[dict]:
    """Build conditional formatting for facility-type-specific Implementation Details fields.

    References the local _FacilityType helper column (not cross-sheet VLOOKUP).
    Food-specific and Healthcare-specific fields get red (must) highlighting.
    """
    add_requests = []
    data_row = header_row + 1  # Row 3 for Implementation Details
    ft_letter = chr(ord("A") + facility_type_col_idx)

    facility_rules = FIELD_REQUIREMENTS.get("implementation_details", {}).get(
        "must_when_facility_type", {}
    )

    for facility_type, fields in facility_rules.items():
        for field in fields:
            col_name = _FIELD_TO_COLUMN.get(field, field)
            col_idx = _find_col_index(impl_headers, col_name)
            if col_idx is None:
                print(f"  WARNING: Column '{col_name}' not found in Implementation Details")
                continue

            col_letter = chr(ord("A") + col_idx)
            formula = (
                f'=AND($A{data_row}<>"",'
                f'${ft_letter}{data_row}="{facility_type}",'
                f'{col_letter}{data_row}="")'
            )
            add_requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": sheet_id,
                            "startRowIndex": header_row,
                            "startColumnIndex": col_idx,
                            "endColumnIndex": col_idx + 1,
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "CUSTOM_FORMULA",
                                "values": [{"userEnteredValue": formula}],
                            },
                            "format": {"backgroundColor": COLOR_RED},
                        },
                    },
                    "index": 0,
                }
            })

    return add_requests


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

    # Delete all existing conditional formatting rules first (idempotent)
    deleted = _delete_existing_rules(spreadsheet)
    if deleted:
        print(f"Deleted {deleted} existing conditional formatting rules.")

    # Build add requests
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
            # Last Verified empty or > 30 days ago → blue
            # Empty cells are treated as 0 by Sheets, so TODAY()-0 > 30 is
            # always true. Add AI guard for HW/Impl (skip Awaiting Installation).
            data_row = hdr_row + 1
            col_letter = chr(ord("A") + col_idx)
            cs_idx = _find_col_index(headers, "_ContractStatus")
            if cs_idx is not None:
                cs_letter = chr(ord("A") + cs_idx)
                formula = f'${cs_letter}{data_row}<>"Awaiting Installation",TODAY()-{col_letter}{data_row}>30'
            else:
                formula = f'TODAY()-{col_letter}{data_row}>30'
            add_requests.append(
                _build_add_rule_request(
                    sid, col_idx, color, rule_type="custom",
                    custom_formula=formula,
                    first_col_letter=first_col, header_row=hdr_row,
                )
            )
        elif severity == "stale_ticket":
            # Status != Resolved AND Received Date > 3 days → orange (full row A:M)
            status_idx = _find_col_index(headers, "Status")
            if status_idx is not None:
                data_row = hdr_row + 1
                col_letter = chr(ord("A") + col_idx)
                status_letter = chr(ord("A") + status_idx)
                # Determine last column (Notes = M for SL)
                end_col_idx = len(headers)
                # Exclude helper columns from range
                for i in range(len(headers) - 1, -1, -1):
                    if not headers[i].startswith("_"):
                        end_col_idx = i + 1
                        break
                formula = (
                    f'=AND(${first_col}{data_row}<>"",'
                    f'${status_letter}{data_row}<>"Resolved",'
                    f'${col_letter}{data_row}<>"",'
                    f'TODAY()-${col_letter}{data_row}>3)'
                )
                add_requests.append({
                    "addConditionalFormatRule": {
                        "rule": {
                            "ranges": [{
                                "sheetId": sid,
                                "startRowIndex": hdr_row,
                                "startColumnIndex": 0,
                                "endColumnIndex": end_col_idx,
                            }],
                            "booleanRule": {
                                "condition": {
                                    "type": "CUSTOM_FORMULA",
                                    "values": [{"userEnteredValue": formula}],
                                },
                                "format": {"backgroundColor": color},
                            },
                        },
                        "index": 0,
                    }
                })
        elif severity == "sl_conditional_status_not":
            # RED when status is NOT in list and field is empty
            status_idx = _find_col_index(headers, "Status")
            if status_idx is not None:
                data_row = hdr_row + 1
                col_letter = chr(ord("A") + col_idx)
                status_letter = chr(ord("A") + status_idx)
                status_values = rule.get("status_not", [])
                status_checks = ",".join(
                    f'${status_letter}{data_row}="{s}"' for s in status_values
                )
                formula = (
                    f'=AND(${first_col}{data_row}<>"",'
                    f'NOT(OR({status_checks})),'
                    f'{col_letter}{data_row}="")'
                )
                add_requests.append(
                    _build_add_rule_request(
                        sid, col_idx, color, rule_type="custom",
                        custom_formula=formula,
                        first_col_letter=first_col, header_row=hdr_row,
                    )
                )
        elif severity == "sl_conditional_status":
            # RED when status IS in list and field is empty
            status_idx = _find_col_index(headers, "Status")
            if status_idx is not None:
                data_row = hdr_row + 1
                col_letter = chr(ord("A") + col_idx)
                status_letter = chr(ord("A") + status_idx)
                status_values = rule.get("status_values", [])
                status_checks = ",".join(
                    f'${status_letter}{data_row}="{s}"' for s in status_values
                )
                formula = (
                    f'=AND(${first_col}{data_row}<>"",'
                    f'OR({status_checks}),'
                    f'{col_letter}{data_row}="")'
                )
                add_requests.append(
                    _build_add_rule_request(
                        sid, col_idx, color, rule_type="custom",
                        custom_formula=formula,
                        first_col_letter=first_col, header_row=hdr_row,
                    )
                )

    # Add Site Viewer conditional formatting
    if "Site Viewer" in sheet_ids:
        # Site info section (rows 7-21)
        viewer_rules = _build_site_viewer_requests(sheet_ids["Site Viewer"])
        add_requests.extend(viewer_rules)

        # Data sections (impl details, hardware, support log)
        try:
            viewer_ws = spreadsheet.worksheet("Site Viewer")
            viewer_content = viewer_ws.get_all_values()
            data_rules = _build_site_viewer_data_requests(
                sheet_ids["Site Viewer"], viewer_content,
            )
            viewer_rules.extend(data_rules)
            add_requests.extend(data_rules)
        except Exception as e:
            print(f"  WARNING: Could not build Site Viewer data rules ({e})")

        print(f"  Site Viewer: {len(viewer_rules)} formatting rules")

    # Device type conditional: Tag/Anchor/Gateway → yellow for HW/FW Version
    if "Hardware Inventory" in sheet_ids:
        hw_rules = _build_device_type_version_requests(
            sheet_ids["Hardware Inventory"],
            sheet_headers.get("Hardware Inventory", []),
            header_row=1,
        )
        add_requests.extend(hw_rules)
        if hw_rules:
            print(f"  Hardware Inventory: {len(hw_rules)} device-type version rules (Tag/Anchor/Gateway)")

    # Facility type conditional: Food/Healthcare → red for specific fields
    # Uses a local _FacilityType helper column (cross-sheet refs not supported
    # in conditional formatting API)
    if "Implementation Details" in sheet_ids and "Sites" in sheet_ids:
        ft_helper_idx = _setup_facility_type_helper(
            spreadsheet,
            sheet_headers.get("Implementation Details", []),
            sheet_headers.get("Sites", []),
        )
        if ft_helper_idx is not None:
            ft_rules = _build_facility_type_conditional_requests(
                sheet_ids["Implementation Details"],
                sheet_headers.get("Implementation Details", []),
                facility_type_col_idx=ft_helper_idx,
                header_row=2,
            )
            add_requests.extend(ft_rules)
            if ft_rules:
                print(f"  Implementation Details: {len(ft_rules)} facility-type rules (Food/Healthcare)")

    # Apply all add requests in one batch
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
