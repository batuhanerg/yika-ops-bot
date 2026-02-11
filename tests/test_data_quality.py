"""Tests for Item 4: Data quality queries — missing_data and stale_data (Session 4).

missing_data: Scan across tabs for empty/incomplete fields.
stale_data: Report records where Last Verified > 30 days old.
"""

import json
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app.services.data_quality import find_missing_data, find_stale_data
from app.utils.formatters import format_data_quality_response


class TestMissingData:
    """Test missing data detection across tabs."""

    def test_missing_email_on_site(self):
        sites = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros", "Email 1": "", "Supervisor 2": "", "Phone 2": "", "Email 2": ""},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[], site_id="MIG-TR-01")
        site_issues = [r for r in result if r["tab"] == "Sites"]
        fields = [r["field"] for r in site_issues]
        assert "Email 1" in fields

    def test_missing_supervisor_2(self):
        sites = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros", "Email 1": "a@b.com", "Supervisor 2": "", "Phone 2": "", "Email 2": ""},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[], site_id="MIG-TR-01")
        site_issues = [r for r in result if r["tab"] == "Sites"]
        fields = [r["field"] for r in site_issues]
        assert "Supervisor 2" in fields

    def test_hardware_missing_fw_version(self):
        hardware = [
            {"Site ID": "MIG-TR-01", "Device Type": "Tag", "Qty": 20, "FW Version": "", "HW Version": ""},
        ]
        result = find_missing_data(sites=[], hardware=hardware, support=[], site_id="MIG-TR-01")
        hw_issues = [r for r in result if r["tab"] == "Hardware Inventory"]
        fields = [r["field"] for r in hw_issues]
        assert "FW Version" in fields

    def test_support_log_pending_root_cause(self):
        support = [
            {"Site ID": "MIG-TR-01", "Ticket ID": "SUP-001", "Status": "Open", "Root Cause": "Pending", "Resolution": ""},
        ]
        result = find_missing_data(sites=[], hardware=[], support=support, site_id="MIG-TR-01")
        sup_issues = [r for r in result if r["tab"] == "Support Log"]
        assert any("Pending" in r["detail"] for r in sup_issues)

    def test_support_log_missing_resolution_when_resolved(self):
        support = [
            {"Site ID": "MIG-TR-01", "Ticket ID": "SUP-002", "Status": "Resolved", "Root Cause": "FW Bug", "Resolution": ""},
        ]
        result = find_missing_data(sites=[], hardware=[], support=support, site_id="MIG-TR-01")
        sup_issues = [r for r in result if r["tab"] == "Support Log"]
        fields = [r["field"] for r in sup_issues]
        assert "Resolution" in fields

    def test_no_issues_when_complete(self):
        sites = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros", "Email 1": "a@b.com",
             "Supervisor 2": "John", "Phone 2": "123", "Email 2": "j@b.com"},
        ]
        hardware = [
            {"Site ID": "MIG-TR-01", "Device Type": "Tag", "Qty": 20, "FW Version": "2.4.1", "HW Version": "1.0"},
        ]
        support = [
            {"Site ID": "MIG-TR-01", "Ticket ID": "SUP-001", "Status": "Resolved",
             "Root Cause": "FW Bug", "Resolution": "Fixed"},
        ]
        result = find_missing_data(sites=sites, hardware=hardware, support=support, site_id="MIG-TR-01")
        assert len(result) == 0

    def test_all_sites_scan(self):
        """When no site_id given, scan all sites."""
        sites = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros", "Email 1": "", "Supervisor 2": "", "Phone 2": "", "Email 2": ""},
            {"Site ID": "MCD-EG-01", "Customer": "McDonald's", "Email 1": "x@y.com", "Supervisor 2": "", "Phone 2": "", "Email 2": ""},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[], site_id=None)
        site_ids_with_issues = {r["site_id"] for r in result}
        assert "MIG-TR-01" in site_ids_with_issues
        assert "MCD-EG-01" in site_ids_with_issues


class TestStaleData:
    """Test stale data detection (Last Verified > threshold)."""

    def test_stale_hardware(self):
        old_date = (date.today() - timedelta(days=45)).isoformat()
        hardware = [
            {"Site ID": "MIG-TR-01", "Device Type": "Tag", "Qty": 20, "Last Verified": old_date},
        ]
        result = find_stale_data(hardware=hardware, implementation=[], site_id="MIG-TR-01", threshold_days=30)
        assert len(result) == 1
        assert result[0]["tab"] == "Hardware Inventory"
        assert result[0]["site_id"] == "MIG-TR-01"

    def test_fresh_hardware_not_stale(self):
        fresh_date = (date.today() - timedelta(days=5)).isoformat()
        hardware = [
            {"Site ID": "MIG-TR-01", "Device Type": "Tag", "Qty": 20, "Last Verified": fresh_date},
        ]
        result = find_stale_data(hardware=hardware, implementation=[], site_id="MIG-TR-01", threshold_days=30)
        assert len(result) == 0

    def test_missing_last_verified_is_stale(self):
        """No Last Verified date means it was never verified — report it."""
        hardware = [
            {"Site ID": "MIG-TR-01", "Device Type": "Gateway", "Qty": 1, "Last Verified": ""},
        ]
        result = find_stale_data(hardware=hardware, implementation=[], site_id="MIG-TR-01", threshold_days=30)
        assert len(result) == 1

    def test_stale_implementation(self):
        old_date = (date.today() - timedelta(days=60)).isoformat()
        implementation = [
            {"Site ID": "MIG-TR-01", "Last Verified": old_date},
        ]
        result = find_stale_data(hardware=[], implementation=implementation, site_id="MIG-TR-01", threshold_days=30)
        assert len(result) == 1
        assert result[0]["tab"] == "Implementation Details"

    def test_custom_threshold(self):
        """45-day-old record should pass a 60-day threshold."""
        old_date = (date.today() - timedelta(days=45)).isoformat()
        hardware = [
            {"Site ID": "MIG-TR-01", "Device Type": "Tag", "Qty": 20, "Last Verified": old_date},
        ]
        result = find_stale_data(hardware=hardware, implementation=[], site_id="MIG-TR-01", threshold_days=60)
        assert len(result) == 0

    def test_all_sites_stale_scan(self):
        old_date = (date.today() - timedelta(days=45)).isoformat()
        hardware = [
            {"Site ID": "MIG-TR-01", "Device Type": "Tag", "Qty": 20, "Last Verified": old_date},
            {"Site ID": "MCD-EG-01", "Device Type": "Tag", "Qty": 15, "Last Verified": ""},
        ]
        result = find_stale_data(hardware=hardware, implementation=[], site_id=None, threshold_days=30)
        site_ids = {r["site_id"] for r in result}
        assert "MIG-TR-01" in site_ids
        assert "MCD-EG-01" in site_ids


class TestDataQualityFormatter:
    """Test Slack Block Kit formatting for data quality responses."""

    def test_missing_data_with_issues(self):
        issues = [
            {"site_id": "MIG-TR-01", "tab": "Sites", "field": "Email 1", "detail": "Email 1 boş"},
            {"site_id": "MIG-TR-01", "tab": "Hardware Inventory", "field": "FW Version", "detail": "Tag: FW Version boş"},
        ]
        blocks = format_data_quality_response("missing_data", issues, site_id="MIG-TR-01")
        text = json.dumps(blocks)
        assert "Eksik Veri Raporu" in text
        assert "MIG-TR-01" in text
        assert "2 sorun" in text

    def test_stale_data_with_issues(self):
        issues = [
            {"site_id": "MIG-TR-01", "tab": "Hardware Inventory", "detail": "Tag: 45 gün önce doğrulanmış"},
        ]
        blocks = format_data_quality_response("stale_data", issues, site_id="MIG-TR-01")
        text = json.dumps(blocks)
        assert "Eski Veri Raporu" in text
        assert "1 sorun" in text

    def test_no_issues_shows_success(self):
        blocks = format_data_quality_response("missing_data", [], site_id="MIG-TR-01")
        text = json.dumps(blocks, ensure_ascii=False)
        assert "Sorun bulunamadı" in text

    def test_all_sites_scope_in_title(self):
        blocks = format_data_quality_response("missing_data", [], site_id=None)
        text = json.dumps(blocks, ensure_ascii=False)
        assert "Tüm siteler" in text


class TestDataQualityQueryWiring:
    """Test that _handle_query correctly routes missing_data and stale_data."""

    @patch("app.handlers.common.get_sheets")
    def test_missing_data_query_calls_sheets(self, mock_get_sheets):
        from app.handlers.common import _handle_query

        mock_sheets = MagicMock()
        mock_sheets.read_sites.return_value = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros", "Email 1": "", "Supervisor 2": "John"},
        ]
        mock_sheets.read_hardware.return_value = []
        mock_sheets.read_support_log.return_value = []
        mock_get_sheets.return_value = mock_sheets

        say = MagicMock()
        _handle_query(
            {"query_type": "missing_data", "site_id": "MIG-TR-01"},
            thread_ts="T001",
            say=say,
        )
        say.assert_called_once()
        blocks = say.call_args[1]["blocks"]
        text = json.dumps(blocks)
        assert "Eksik Veri Raporu" in text

    @patch("app.handlers.common.get_sheets")
    def test_stale_data_query_calls_sheets(self, mock_get_sheets):
        from app.handlers.common import _handle_query

        old_date = (date.today() - timedelta(days=45)).isoformat()
        mock_sheets = MagicMock()
        mock_sheets.read_hardware.return_value = [
            {"Site ID": "MIG-TR-01", "Device Type": "Tag", "Qty": 20, "Last Verified": old_date},
        ]
        mock_sheets.read_all_implementation.return_value = []
        mock_get_sheets.return_value = mock_sheets

        say = MagicMock()
        _handle_query(
            {"query_type": "stale_data", "site_id": "MIG-TR-01"},
            thread_ts="T001",
            say=say,
        )
        say.assert_called_once()
        blocks = say.call_args[1]["blocks"]
        text = json.dumps(blocks)
        assert "Eski Veri Raporu" in text
