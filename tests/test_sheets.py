"""Tests for Google Sheets service.

These tests use mocked gspread to avoid hitting the real sheet during CI.
Integration tests against the real sheet can be run with --run-sheets flag.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.sheets import SheetsService


@pytest.fixture
def mock_gspread():
    """Create a mocked gspread setup with realistic sheet data."""
    mock_gc = MagicMock()
    mock_spreadsheet = MagicMock()
    mock_gc.open_by_key.return_value = mock_spreadsheet

    # Sites tab
    sites_ws = MagicMock()
    sites_ws.title = "Sites"
    sites_ws.get_all_records.return_value = [
        {
            "Site ID": "MIG-TR-01",
            "Customer": "Migros",
            "City": "Istanbul",
            "Country": "Turkey",
            "Facility Type": "Food",
            "Contract Status": "Active",
            "Go-live Date": "2021-03-15",
            "Address": "",
            "Dashboard Link": "",
            "Supervisor 1": "Ahmet",
            "Phone 1": "",
            "Email 1": "",
            "Supervisor 2": "",
            "Phone 2": "",
            "Email 2": "",
            "Notes": "",
        },
        {
            "Site ID": "MCD-EG-01",
            "Customer": "McDonald's",
            "City": "Cairo",
            "Country": "Egypt",
            "Facility Type": "Food",
            "Contract Status": "Active",
            "Go-live Date": "2024-11-01",
            "Address": "",
            "Dashboard Link": "",
            "Supervisor 1": "Omar",
            "Phone 1": "",
            "Email 1": "",
            "Supervisor 2": "",
            "Phone 2": "",
            "Email 2": "",
            "Notes": "",
        },
    ]
    sites_ws.get_all_values.return_value = [
        ["Site ID", "Customer", "City", "Country", "Address", "Facility Type",
         "Dashboard Link", "Supervisor 1", "Phone 1", "Email 1",
         "Supervisor 2", "Phone 2", "Email 2", "Go-live Date",
         "Contract Status", "Notes"],
        ["MIG-TR-01", "Migros", "Istanbul", "Turkey", "", "Food", "", "Ahmet",
         "", "", "", "", "", "2021-03-15", "Active", ""],
        ["MCD-EG-01", "McDonald's", "Cairo", "Egypt", "", "Food", "", "Omar",
         "", "", "", "", "", "2024-11-01", "Active", ""],
    ]

    # Hardware Inventory tab
    hw_ws = MagicMock()
    hw_ws.title = "Hardware Inventory"
    hw_ws.get_all_records.return_value = [
        {"Site ID": "MIG-TR-01", "Device Type": "Tag", "HW Version": "", "FW Version": "2.4.1", "Qty": 20, "Last Verified": "2025-01-10", "Notes": ""},
        {"Site ID": "MIG-TR-01", "Device Type": "Gateway", "HW Version": "", "FW Version": "", "Qty": 1, "Last Verified": "", "Notes": ""},
        {"Site ID": "MCD-EG-01", "Device Type": "Tag", "HW Version": "", "FW Version": "", "Qty": 15, "Last Verified": "", "Notes": ""},
    ]

    # Support Log tab
    support_ws = MagicMock()
    support_ws.title = "Support Log"
    support_ws.get_all_records.return_value = [
        {"Ticket ID": "SUP-001", "Site ID": "MIG-TR-01", "Received Date": "2025-01-10", "Resolved Date": "2025-01-10", "Type": "Visit", "Status": "Resolved", "Root Cause": "FW Bug", "Reported By": "Ahmet", "Issue Summary": "3 tags not syncing", "Resolution": "Replaced batteries", "Devices Affected": "Tags", "Responsible": "Batu", "Notes": ""},
        {"Ticket ID": "SUP-002", "Site ID": "MCD-EG-01", "Received Date": "2025-01-18", "Resolved Date": "", "Type": "Visit", "Status": "Follow-up (ERG)", "Root Cause": "HW Fault (Customer)", "Reported By": "Omar", "Issue Summary": "2 anchors intermittent", "Resolution": "", "Devices Affected": "Anchors", "Responsible": "Gökhan", "Notes": ""},
    ]
    support_ws.get_all_values.return_value = [
        ["Ticket ID", "Site ID", "Received Date", "Resolved Date", "Type", "Status", "Root Cause", "Reported By", "Issue Summary", "Resolution", "Devices Affected", "Responsible", "Notes"],
        ["SUP-001", "MIG-TR-01", "2025-01-10", "2025-01-10", "Visit", "Resolved", "FW Bug", "Ahmet", "3 tags not syncing", "Replaced batteries", "Tags", "Batu", ""],
        ["SUP-002", "MCD-EG-01", "2025-01-18", "", "Visit", "Follow-up (ERG)", "HW Fault (Customer)", "Omar", "2 anchors intermittent", "", "Anchors", "Gökhan", ""],
    ]

    # Implementation Details tab (2 header rows)
    impl_ws = MagicMock()
    impl_ws.title = "Implementation Details"
    impl_ws.get_all_values.return_value = [
        ["", "GENERAL", "", "", "", "", "", "", "FOOD", "", "", "", "", "HEALTHCARE", "", "OTHER", ""],
        ["Site ID", "Internet connection", "Gateway placement", "Charging dock placement", "Dispenser anchor placement", "Handwash time", "Tag buzzer/vibration", "Entry time", "Clean hygiene time", "HP alert time", "Hand hygiene time", "Hand hygiene interval (dashboard)", "Hand hygiene type", "Tag clean-to-red timeout", "Dispenser anchor power type", "Other details", "Last Verified"],
        ["MIG-TR-01", "Customer WiFi", "Back office", "", "", "", "", "", "", "", "", "", "", "", "", "", "2025-01-15"],
    ]

    # Stock tab
    stock_ws = MagicMock()
    stock_ws.title = "Stock"
    stock_ws.get_all_records.return_value = [
        {"Location": "Istanbul Office", "Device Type": "Tag", "HW Version": "", "FW Version": "2.4.1", "Qty": 50, "Condition": "New", "Reserved For": "", "Notes": ""},
        {"Location": "Istanbul Office", "Device Type": "Gateway", "HW Version": "", "FW Version": "", "Qty": 5, "Condition": "New", "Reserved For": "", "Notes": ""},
        {"Location": "Adana Storage", "Device Type": "Tag", "HW Version": "", "FW Version": "", "Qty": 10, "Condition": "Refurbished", "Reserved For": "", "Notes": ""},
    ]

    # Audit Log tab
    audit_ws = MagicMock()
    audit_ws.title = "Audit Log"

    def _worksheet(name):
        mapping = {
            "Sites": sites_ws,
            "Hardware Inventory": hw_ws,
            "Implementation Details": impl_ws,
            "Support Log": support_ws,
            "Stock": stock_ws,
            "Audit Log": audit_ws,
        }
        if name in mapping:
            return mapping[name]
        raise gspread.exceptions.WorksheetNotFound(name)

    mock_spreadsheet.worksheet.side_effect = _worksheet
    mock_spreadsheet.worksheets.return_value = [sites_ws, hw_ws, impl_ws, support_ws, stock_ws, audit_ws]

    return mock_gc, mock_spreadsheet, {
        "sites": sites_ws,
        "hardware": hw_ws,
        "implementation": impl_ws,
        "support": support_ws,
        "stock": stock_ws,
        "audit": audit_ws,
    }


@pytest.fixture
def sheets_service(mock_gspread):
    mock_gc, mock_spreadsheet, worksheets = mock_gspread
    with patch("app.services.sheets.SheetsService._connect") as mock_connect:
        service = SheetsService.__new__(SheetsService)
        service.spreadsheet = mock_spreadsheet
        service._ws_cache = {}
        yield service, worksheets


class TestReadSites:
    def test_returns_list_of_site_dicts(self, sheets_service):
        service, ws = sheets_service
        sites = service.read_sites()
        assert len(sites) == 2
        assert sites[0]["Site ID"] == "MIG-TR-01"
        assert sites[1]["Site ID"] == "MCD-EG-01"

    def test_site_has_required_fields(self, sheets_service):
        service, ws = sheets_service
        sites = service.read_sites()
        site = sites[0]
        assert "Customer" in site
        assert "City" in site
        assert "Facility Type" in site


class TestReadHardware:
    def test_returns_filtered_by_site(self, sheets_service):
        service, ws = sheets_service
        hw = service.read_hardware("MIG-TR-01")
        assert len(hw) == 2
        assert all(r["Site ID"] == "MIG-TR-01" for r in hw)

    def test_different_site(self, sheets_service):
        service, ws = sheets_service
        hw = service.read_hardware("MCD-EG-01")
        assert len(hw) == 1
        assert hw[0]["Device Type"] == "Tag"


class TestReadSupportLog:
    def test_returns_filtered_by_site(self, sheets_service):
        service, ws = sheets_service
        logs = service.read_support_log("MIG-TR-01")
        assert len(logs) == 1
        assert logs[0]["Status"] == "Resolved"

    def test_returns_all_when_no_site(self, sheets_service):
        service, ws = sheets_service
        logs = service.read_support_log()
        assert len(logs) == 2


class TestAppendSupportLog:
    def test_append_row_with_ticket_id(self, sheets_service):
        service, ws = sheets_service
        entry = {
            "site_id": "MIG-TR-01",
            "received_date": "2025-02-01",
            "resolved_date": "2025-02-01",
            "type": "Remote",
            "status": "Resolved",
            "root_cause": "User Error",
            "reported_by": "Ahmet",
            "issue_summary": "False alarm",
            "resolution": "Data delay explained",
            "devices_affected": "",
            "responsible": "Batu",
            "notes": "",
        }
        ticket_id = service.append_support_log(entry)
        assert ticket_id == "SUP-003"
        ws["support"].append_row.assert_called_once()
        row = ws["support"].append_row.call_args[0][0]
        assert row[0] == "SUP-003"  # Ticket ID
        assert row[1] == "MIG-TR-01"  # Site ID
        assert row[4] == "Remote"  # Type


class TestUpdateSupportLog:
    def test_update_specific_cells(self, sheets_service):
        service, ws = sheets_service
        # Update row 3 (second data row = MCD-EG-01 entry) status to Resolved
        service.update_support_log(row_index=3, updates={"Status": "Resolved", "Resolution": "Fixed it"})
        assert ws["support"].update_cell.call_count == 2

    def test_find_by_ticket_id(self, sheets_service):
        service, ws = sheets_service
        row = service.find_support_log_row(ticket_id="SUP-002")
        assert row == 3  # Row 3 = second data row

    def test_list_open_tickets(self, sheets_service):
        service, ws = sheets_service
        tickets = service.list_open_tickets("MCD-EG-01")
        assert len(tickets) == 1
        assert tickets[0]["ticket_id"] == "SUP-002"
        assert tickets[0]["issue_summary"] == "2 anchors intermittent"


class TestAppendHardware:
    def test_append_row(self, sheets_service):
        service, ws = sheets_service
        entry = {
            "site_id": "MIG-TR-01",
            "device_type": "Anchor",
            "hw_version": "",
            "fw_version": "",
            "qty": 5,
            "last_verified": "2025-02-01",
            "notes": "Dezenfektan dispenser anchor",
        }
        service.append_hardware(entry)
        ws["hardware"].append_row.assert_called_once()
        row = ws["hardware"].append_row.call_args[0][0]
        assert row[0] == "MIG-TR-01"
        assert row[1] == "Anchor"
        assert row[4] == 5


class TestCreateSite:
    def test_append_to_sites(self, sheets_service):
        service, ws = sheets_service
        site_data = {
            "site_id": "ASM-TR-01",
            "customer": "Anadolu Sağlık",
            "city": "Gebze",
            "country": "Turkey",
            "facility_type": "Healthcare",
            "go_live_date": "2025-03-01",
            "contract_status": "Active",
        }
        service.create_site(site_data)
        ws["sites"].append_row.assert_called_once()
        row = ws["sites"].append_row.call_args[0][0]
        assert row[0] == "ASM-TR-01"
        assert row[1] == "Anadolu Sağlık"


class TestUpdateImplementation:
    def test_update_cell(self, sheets_service):
        service, ws = sheets_service
        service.update_implementation("MIG-TR-01", {"Internet connection": "Fiber optic"})
        ws["implementation"].update_cell.assert_called()


class TestAppendAuditLog:
    def test_append_entry(self, sheets_service):
        service, ws = sheets_service
        service.append_audit_log(
            user="Batu",
            operation="CREATE",
            target_tab="Support Log",
            site_id="MIG-TR-01",
            summary="New support entry",
            raw_message="bugün gittim...",
        )
        ws["audit"].append_row.assert_called_once()
        row = ws["audit"].append_row.call_args[0][0]
        assert row[1] == "Batu"
        assert row[2] == "CREATE"
        assert row[3] == "Support Log"


class TestReadStock:
    def test_returns_filtered_by_location(self, sheets_service):
        service, ws = sheets_service
        stock = service.read_stock(location="Istanbul Office")
        assert len(stock) == 2

    def test_returns_all_when_no_filter(self, sheets_service):
        service, ws = sheets_service
        stock = service.read_stock()
        assert len(stock) == 3
