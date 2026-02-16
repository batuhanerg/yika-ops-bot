"""Tests for Site Viewer layout fix script."""

from unittest.mock import MagicMock

from scripts.fix_site_viewer_layout import fix_layout, SUPPORT_LOG_HEADERS


class TestFixLayout:

    def _make_mocks(self):
        """Create mock viewer_ws and impl_ws."""
        viewer_ws = MagicMock()
        viewer_ws.id = 100
        viewer_ws.title = "Site Viewer"
        viewer_ws.spreadsheet = MagicMock()

        impl_ws = MagicMock()
        impl_ws.row_values.return_value = [
            "Site ID", "Internet Provider", "SSID", "Password",
            "Gateway placement", "Charging dock placement",
            "Dispenser anchor placement", "Handwash time",
            "Tag buzzer/vibration", "Entry time",
            "Dispenser anchor power type", "Clean hygiene time",
            "HP alert time", "Hand hygiene time",
            "Hand hygiene interval (dashboard)", "Hand hygiene type",
            "Tag clean-to-red timeout", "Other details", "Last Verified",
        ]

        return viewer_ws, impl_ws

    def test_dry_run_no_changes(self):
        viewer_ws, impl_ws = self._make_mocks()

        result = fix_layout(viewer_ws, impl_ws, dry_run=True)

        viewer_ws.update.assert_not_called()
        viewer_ws.update_cell.assert_not_called()
        assert result["impl_params"] == 18

    def test_writes_correct_param_count(self):
        viewer_ws, impl_ws = self._make_mocks()

        result = fix_layout(viewer_ws, impl_ws)

        assert result["impl_params"] == 18

    def test_support_log_headers_at_column_b(self):
        """Support log headers should start at column B, not A."""
        viewer_ws, impl_ws = self._make_mocks()

        fix_layout(viewer_ws, impl_ws)

        # Find the header write call
        header_written = False
        for call in viewer_ws.update.call_args_list:
            kwargs = call.kwargs or {}
            range_name = kwargs.get("range_name", "")
            values = kwargs.get("values", [])
            if "B" in range_name and "N" in range_name and values:
                if values[0] == SUPPORT_LOG_HEADERS:
                    header_written = True
                    # Should NOT start at A
                    assert not range_name.startswith("A"), "Headers should start at B"
        assert header_written, "Support log headers not written at B:N"

    def test_sort_formula_at_column_b(self):
        """SORT formula should be at column B (not A)."""
        viewer_ws, impl_ws = self._make_mocks()

        result = fix_layout(viewer_ws, impl_ws)

        sl_data_row = result["sl_data_row"]
        sort_calls = [
            call for call in viewer_ws.update_cell.call_args_list
            if call[0][0] == sl_data_row and call[0][1] == 2  # column B = 2
        ]
        assert len(sort_calls) == 1
        formula = sort_calls[0][0][2]
        assert "SORT" in formula
        assert "FILTER" in formula

    def test_impl_params_match_actual_headers(self):
        """Implementation Details params should match actual tab headers."""
        viewer_ws, impl_ws = self._make_mocks()

        fix_layout(viewer_ws, impl_ws)

        # Find the impl details data write
        for call in viewer_ws.update.call_args_list:
            kwargs = call.kwargs or {}
            range_name = kwargs.get("range_name", "")
            values = kwargs.get("values", [])
            if "B43" in range_name and values:
                # First param should be "Internet Provider" (not "Internet connection")
                assert values[0][0] == "Internet Provider"
                # Should have VLOOKUP formula
                assert "VLOOKUP" in values[0][1]
                break

    def test_skips_site_id_and_helper_columns(self):
        """Should not include Site ID or _FacilityType in parameters."""
        viewer_ws, impl_ws = self._make_mocks()
        # Add _FacilityType helper column
        headers = impl_ws.row_values.return_value + ["_FacilityType"]
        impl_ws.row_values.return_value = headers

        result = fix_layout(viewer_ws, impl_ws)

        # Should still be 18 params (Site ID and _FacilityType excluded)
        assert result["impl_params"] == 18

    def test_date_formatting_applied(self):
        """Date formatting should be applied to Received/Resolved Date columns."""
        viewer_ws, impl_ws = self._make_mocks()

        fix_layout(viewer_ws, impl_ws)

        batch_call = viewer_ws.spreadsheet.batch_update.call_args
        requests = batch_call[0][0]["requests"]
        date_format_found = False
        for req in requests:
            if "repeatCell" in req:
                cell = req["repeatCell"].get("cell", {})
                fmt = cell.get("userEnteredFormat", {}).get("numberFormat", {})
                if fmt.get("type") == "DATE":
                    date_format_found = True
        assert date_format_found, "Date formatting not applied"

    def test_header_formatting_applied(self):
        """Support log headers should get dark blue background formatting."""
        viewer_ws, impl_ws = self._make_mocks()

        fix_layout(viewer_ws, impl_ws)

        batch_call = viewer_ws.spreadsheet.batch_update.call_args
        requests = batch_call[0][0]["requests"]
        header_format_found = False
        for req in requests:
            if "repeatCell" in req:
                cell = req["repeatCell"].get("cell", {})
                bg = cell.get("userEnteredFormat", {}).get("backgroundColor", {})
                if bg.get("red", 0) < 0.5 and bg.get("blue", 0) > 0.3:
                    header_format_found = True
        assert header_format_found, "Header formatting not applied"
