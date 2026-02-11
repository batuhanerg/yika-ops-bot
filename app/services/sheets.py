"""Google Sheets read/write operations via gspread."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

# Column order for each tab (used when appending rows)
SITES_COLUMNS = [
    "Site ID", "Customer", "City", "Country", "Address", "Facility Type",
    "Dashboard Link", "Supervisor 1", "Phone 1", "Email 1",
    "Supervisor 2", "Phone 2", "Email 2", "Go-live Date",
    "Contract Status", "Notes",
]

HARDWARE_COLUMNS = [
    "Site ID", "Device Type", "HW Version", "FW Version", "Qty",
    "Last Verified", "Notes",
]

SUPPORT_LOG_COLUMNS = [
    "Ticket ID", "Site ID", "Received Date", "Resolved Date", "Type", "Status",
    "Root Cause", "Reported By", "Issue Summary", "Resolution",
    "Devices Affected", "Responsible", "Notes",
]

STOCK_COLUMNS = [
    "Location", "Device Type", "HW Version", "FW Version", "Qty",
    "Condition", "Reserved For", "Notes",
]

AUDIT_LOG_COLUMNS = [
    "Timestamp", "Slack User", "Operation", "Target Tab",
    "Site ID", "Summary", "Raw Message",
]

FEEDBACK_COLUMNS = [
    "Timestamp", "User", "Operation", "Site ID", "Ticket ID",
    "Rating", "Expected Behavior", "Original Message",
]

# Map from snake_case data keys to sheet column names
_SUPPORT_KEY_MAP = {
    "ticket_id": "Ticket ID",
    "site_id": "Site ID",
    "received_date": "Received Date",
    "resolved_date": "Resolved Date",
    "type": "Type",
    "status": "Status",
    "root_cause": "Root Cause",
    "reported_by": "Reported By",
    "issue_summary": "Issue Summary",
    "resolution": "Resolution",
    "devices_affected": "Devices Affected",
    "responsible": "Responsible",
    "notes": "Notes",
}

_HARDWARE_KEY_MAP = {
    "site_id": "Site ID",
    "device_type": "Device Type",
    "hw_version": "HW Version",
    "fw_version": "FW Version",
    "qty": "Qty",
    "last_verified": "Last Verified",
    "notes": "Notes",
}

_SITES_KEY_MAP = {
    "site_id": "Site ID",
    "customer": "Customer",
    "city": "City",
    "country": "Country",
    "address": "Address",
    "facility_type": "Facility Type",
    "dashboard_link": "Dashboard Link",
    "supervisor_1": "Supervisor 1",
    "phone_1": "Phone 1",
    "email_1": "Email 1",
    "supervisor_2": "Supervisor 2",
    "phone_2": "Phone 2",
    "email_2": "Email 2",
    "go_live_date": "Go-live Date",
    "contract_status": "Contract Status",
    "notes": "Notes",
}


class SheetsService:
    """Read/write operations against the ERG Controls Google Sheet."""

    def __init__(self) -> None:
        self._ws_cache: dict[str, gspread.Worksheet] = {}
        self._connect()

    def _connect(self) -> None:
        creds_json = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
        gc = gspread.authorize(creds)
        self.spreadsheet = gc.open_by_key(os.environ["GOOGLE_SHEET_ID"])

    def _ws(self, name: str) -> gspread.Worksheet:
        if name not in self._ws_cache:
            self._ws_cache[name] = self.spreadsheet.worksheet(name)
        return self._ws_cache[name]

    # --- Sites ---

    def read_sites(self) -> list[dict[str, Any]]:
        return self._ws("Sites").get_all_records()

    def create_site(self, data: dict[str, Any]) -> None:
        row = [data.get(k, "") for k in _SITES_KEY_MAP]
        # Map snake_case keys to values
        mapped_row = []
        for col in SITES_COLUMNS:
            # Find the snake_case key for this column
            key = next((k for k, v in _SITES_KEY_MAP.items() if v == col), None)
            mapped_row.append(data.get(key, "") if key else "")
        self._ws("Sites").append_row(mapped_row, value_input_option="USER_ENTERED")

    def update_site(self, site_id: str, updates: dict[str, Any]) -> None:
        ws = self._ws("Sites")
        all_values = ws.get_all_values()
        headers = all_values[0]
        for row_idx, row in enumerate(all_values[1:], start=2):
            if row[0] == site_id:
                for col_name, value in updates.items():
                    if col_name in headers:
                        col_idx = headers.index(col_name) + 1
                        ws.update_cell(row_idx, col_idx, value)
                return

    # --- Hardware Inventory ---

    def read_hardware(self, site_id: str | None = None) -> list[dict[str, Any]]:
        records = self._ws("Hardware Inventory").get_all_records()
        if site_id:
            return [r for r in records if r["Site ID"] == site_id]
        return records

    def append_hardware(self, data: dict[str, Any]) -> None:
        row = []
        for col in HARDWARE_COLUMNS:
            key = next((k for k, v in _HARDWARE_KEY_MAP.items() if v == col), None)
            row.append(data.get(key, "") if key else "")
        self._ws("Hardware Inventory").append_row(row, value_input_option="USER_ENTERED")

    # --- Implementation Details ---

    def read_implementation(self, site_id: str) -> dict[str, Any]:
        ws = self._ws("Implementation Details")
        all_values = ws.get_all_values()
        if len(all_values) < 2:
            return {}
        headers = all_values[1]  # Row 2 has field names
        for row in all_values[2:]:
            if row and row[0] == site_id:
                return {headers[i]: row[i] for i in range(len(headers)) if i < len(row)}
        return {}

    def read_all_implementation(self) -> list[dict[str, Any]]:
        """Read all rows from Implementation Details as a list of dicts."""
        ws = self._ws("Implementation Details")
        all_values = ws.get_all_values()
        if len(all_values) < 3:
            return []
        headers = all_values[1]  # Row 2 has field names
        results = []
        for row in all_values[2:]:
            if row and row[0]:
                results.append({headers[i]: row[i] for i in range(len(headers)) if i < len(row)})
        return results

    def update_implementation(self, site_id: str, updates: dict[str, Any]) -> None:
        ws = self._ws("Implementation Details")
        all_values = ws.get_all_values()
        if len(all_values) < 2:
            return
        headers = all_values[1]  # Row 2 has field names
        target_row = None
        for row_idx, row in enumerate(all_values[2:], start=3):
            if row and row[0] == site_id:
                target_row = row_idx
                break

        if target_row is None:
            # Create new row for this site
            new_row = [""] * len(headers)
            new_row[0] = site_id
            for col_name, value in updates.items():
                if col_name in headers:
                    new_row[headers.index(col_name)] = value
            ws.append_row(new_row, value_input_option="USER_ENTERED")
        else:
            for col_name, value in updates.items():
                if col_name in headers:
                    col_idx = headers.index(col_name) + 1
                    ws.update_cell(target_row, col_idx, value)

    # --- Support Log ---

    def read_support_log(self, site_id: str | None = None) -> list[dict[str, Any]]:
        records = self._ws("Support Log").get_all_records()
        if site_id:
            return [r for r in records if r["Site ID"] == site_id]
        return records

    def _next_ticket_id(self) -> str:
        """Generate the next ticket ID (SUP-001, SUP-002, etc.)."""
        ws = self._ws("Support Log")
        all_values = ws.get_all_values()
        if len(all_values) < 2:
            return "SUP-001"
        # Ticket ID is column A (index 0)
        max_num = 0
        for row in all_values[1:]:
            tid = row[0] if row else ""
            if tid.startswith("SUP-"):
                try:
                    num = int(tid[4:])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        return f"SUP-{max_num + 1:03d}"

    def append_support_log(self, data: dict[str, Any]) -> str:
        """Append a support log entry with auto-generated Ticket ID. Returns the ticket ID."""
        ticket_id = self._next_ticket_id()
        data_with_id = {**data, "ticket_id": ticket_id}
        row = []
        for col in SUPPORT_LOG_COLUMNS:
            key = next((k for k, v in _SUPPORT_KEY_MAP.items() if v == col), None)
            val = data_with_id.get(key, "") if key else ""
            # Convert lists to comma-separated strings (e.g., devices_affected)
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            row.append(val)
        self._ws("Support Log").append_row(row, value_input_option="USER_ENTERED")
        return ticket_id

    def find_support_log_row(self, site_id: str | None = None, ticket_id: str | None = None) -> int | None:
        """Find a support log row by ticket_id or most recent non-resolved for site_id. Returns 1-based row index."""
        ws = self._ws("Support Log")
        all_values = ws.get_all_values()
        if len(all_values) < 2:
            return None
        headers = all_values[0]
        ticket_col = headers.index("Ticket ID")
        site_col = headers.index("Site ID")
        status_col = headers.index("Status")

        # Lookup by ticket ID first
        if ticket_id:
            for row_idx, row in enumerate(all_values[1:], start=2):
                if row[ticket_col] == ticket_id:
                    return row_idx
            return None

        # Lookup by site_id: prefer non-resolved, fall back to any
        if site_id:
            candidates = []
            for row_idx, row in enumerate(all_values[1:], start=2):
                if row[site_col] == site_id and row[status_col] != "Resolved":
                    candidates.append(row_idx)
            if not candidates:
                for row_idx, row in enumerate(all_values[1:], start=2):
                    if row[site_col] == site_id:
                        candidates.append(row_idx)
            return candidates[-1] if candidates else None

        return None

    def list_open_tickets(self, site_id: str) -> list[dict[str, str]]:
        """List open (non-resolved) tickets for a site with ID and summary."""
        ws = self._ws("Support Log")
        all_values = ws.get_all_values()
        if len(all_values) < 2:
            return []
        headers = all_values[0]
        ticket_col = headers.index("Ticket ID")
        site_col = headers.index("Site ID")
        status_col = headers.index("Status")
        summary_col = headers.index("Issue Summary")
        date_col = headers.index("Received Date")

        tickets = []
        for row in all_values[1:]:
            if row[site_col] == site_id and row[status_col] != "Resolved":
                tickets.append({
                    "ticket_id": row[ticket_col],
                    "issue_summary": row[summary_col],
                    "received_date": row[date_col],
                    "status": row[status_col],
                })
        return tickets

    def update_support_log(self, row_index: int, updates: dict[str, Any]) -> None:
        ws = self._ws("Support Log")
        headers = SUPPORT_LOG_COLUMNS
        for col_name, value in updates.items():
            if col_name in headers:
                col_idx = headers.index(col_name) + 1
                ws.update_cell(row_index, col_idx, value)

    # --- Stock ---

    def read_stock(self, location: str | None = None) -> list[dict[str, Any]]:
        records = self._ws("Stock").get_all_records()
        if location:
            return [r for r in records if r["Location"] == location]
        return records

    def append_stock(self, data: dict[str, Any]) -> None:
        row = []
        for col in STOCK_COLUMNS:
            key = col.lower().replace(" ", "_").replace("-", "_")
            row.append(data.get(key, ""))
        self._ws("Stock").append_row(row, value_input_option="USER_ENTERED")

    def update_stock(self, row_index: int, updates: dict[str, Any]) -> None:
        ws = self._ws("Stock")
        headers = STOCK_COLUMNS
        for col_name, value in updates.items():
            if col_name in headers:
                col_idx = headers.index(col_name) + 1
                ws.update_cell(row_index, col_idx, value)

    # --- Audit Log ---

    def append_audit_log(
        self,
        user: str,
        operation: str,
        target_tab: str,
        site_id: str,
        summary: str,
        raw_message: str,
    ) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        row = [timestamp, user, operation, target_tab, site_id, summary, raw_message]
        self._ws("Audit Log").append_row(row, value_input_option="USER_ENTERED")

    # --- Feedback ---

    def append_feedback(
        self,
        user: str,
        operation: str,
        site_id: str,
        ticket_id: str,
        rating: str,
        expected_behavior: str,
        original_message: str,
    ) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        row = [timestamp, user, operation, site_id, ticket_id, rating, expected_behavior, original_message]
        self._ws("Feedback").append_row(row, value_input_option="USER_ENTERED")
