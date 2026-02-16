"""Tests for HW/FW Version normalization — strip 'v'/'V' prefix on write."""

import pytest
from unittest.mock import MagicMock, patch

from app.services.sheets import SheetsService, _normalize_version_fields


class TestNormalizeVersionFields:
    """Test the _normalize_version_fields helper."""

    def test_strip_lowercase_v(self):
        """'v3.6.0' → '3.6.0'."""
        data = {"hw_version": "v3.6.0", "fw_version": "v1.2.3"}
        result = _normalize_version_fields(data)
        assert result["hw_version"] == "3.6.0"
        assert result["fw_version"] == "1.2.3"

    def test_strip_uppercase_v(self):
        """'V2' → '2'."""
        data = {"hw_version": "V2", "fw_version": "V10.0"}
        result = _normalize_version_fields(data)
        assert result["hw_version"] == "2"
        assert result["fw_version"] == "10.0"

    def test_no_prefix_unchanged(self):
        """'3.6.1' stays '3.6.1'."""
        data = {"hw_version": "3.6.1", "fw_version": "2.0.0"}
        result = _normalize_version_fields(data)
        assert result["hw_version"] == "3.6.1"
        assert result["fw_version"] == "2.0.0"

    def test_other_fields_not_affected(self):
        """Fields other than HW/FW Version are NOT affected."""
        data = {"device_type": "vGateway", "notes": "version v5", "hw_version": "v1.0"}
        result = _normalize_version_fields(data)
        assert result["device_type"] == "vGateway"
        assert result["notes"] == "version v5"
        assert result["hw_version"] == "1.0"

    def test_empty_version_unchanged(self):
        """Empty string stays empty."""
        data = {"hw_version": "", "fw_version": ""}
        result = _normalize_version_fields(data)
        assert result["hw_version"] == ""
        assert result["fw_version"] == ""

    def test_missing_version_keys(self):
        """Data without version keys passes through unchanged."""
        data = {"site_id": "MIG-TR-01", "device_type": "Gateway"}
        result = _normalize_version_fields(data)
        assert result == data

    def test_does_not_mutate_original(self):
        """Returns a new dict, does not mutate the input."""
        data = {"hw_version": "v3.0", "device_type": "Gateway"}
        result = _normalize_version_fields(data)
        assert data["hw_version"] == "v3.0"  # original unchanged
        assert result["hw_version"] == "3.0"


class TestAppendHardwareNormalization:
    """Verify normalization is applied when writing hardware rows."""

    @pytest.fixture
    def sheets_service(self):
        mock_gc = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_gc.open_by_key.return_value = mock_spreadsheet
        hw_ws = MagicMock()
        hw_ws.title = "Hardware Inventory"
        mock_spreadsheet.worksheet.return_value = hw_ws

        with patch("app.services.sheets.SheetsService._connect"):
            service = SheetsService.__new__(SheetsService)
            service.spreadsheet = mock_spreadsheet
            service._ws_cache = {}
            yield service, hw_ws

    def test_append_hardware_strips_v_prefix(self, sheets_service):
        """append_hardware normalizes v-prefix on HW/FW Version."""
        service, ws = sheets_service
        service.append_hardware({
            "site_id": "MIG-TR-01",
            "device_type": "Gateway",
            "hw_version": "v3.6.0",
            "fw_version": "V2.1",
            "qty": 1,
        })
        ws.append_row.assert_called_once()
        row = ws.append_row.call_args[0][0]
        # HARDWARE_COLUMNS: Site ID, Device Type, HW Version, FW Version, Qty, Last Verified, Notes
        assert row[2] == "3.6.0"  # HW Version
        assert row[3] == "2.1"    # FW Version


class TestAppendStockNormalization:
    """Verify normalization is applied when writing stock rows."""

    @pytest.fixture
    def sheets_service(self):
        mock_gc = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_gc.open_by_key.return_value = mock_spreadsheet
        stock_ws = MagicMock()
        stock_ws.title = "Stock"
        mock_spreadsheet.worksheet.return_value = stock_ws

        with patch("app.services.sheets.SheetsService._connect"):
            service = SheetsService.__new__(SheetsService)
            service.spreadsheet = mock_spreadsheet
            service._ws_cache = {}
            yield service, stock_ws

    def test_append_stock_strips_v_prefix(self, sheets_service):
        """append_stock normalizes v-prefix on HW/FW Version."""
        service, ws = sheets_service
        service.append_stock({
            "location": "Istanbul",
            "device_type": "Gateway",
            "hw_version": "v4.0",
            "fw_version": "V1.5",
            "qty": 5,
            "condition": "New",
        })
        ws.append_row.assert_called_once()
        row = ws.append_row.call_args[0][0]
        # STOCK_COLUMNS: Location, Device Type, HW Version, FW Version, Qty, Condition, Reserved For, Notes, Last Verified
        assert row[2] == "4.0"  # HW Version
        assert row[3] == "1.5"  # FW Version
