"""Tests for Dashboard migration script (Session 6, Item 5).

Replaces the single "Total Devices" column with five device-type columns:
Tags, Anchors, Gateways, Charging Docks, Other.
Each column uses SUMIFS to count devices by type from Hardware Inventory.
"""

from unittest.mock import MagicMock

from scripts.migrate_dashboard import migrate, DEVICE_COLUMNS


class TestDashboardMigration:
    """Test the Dashboard tab migration."""

    def _make_ws(self, headers: list[str], num_data_rows: int = 3) -> MagicMock:
        """Create a mock worksheet with given headers and data rows."""
        ws = MagicMock()
        ws.row_values.return_value = headers
        ws.row_count = 1 + num_data_rows
        return ws

    def test_device_columns_constant(self):
        """DEVICE_COLUMNS should list the 5 breakdown columns."""
        assert DEVICE_COLUMNS == ["Tags", "Anchors", "Gateways", "Charging Docks", "Other"]

    def test_replaces_total_devices_header(self):
        """Should replace 'Total Devices' with 5 device-type columns."""
        headers = [
            "Site ID", "Customer", "Status", "Open Issues",
            "Total Devices", "Last Visit",
        ]
        ws = self._make_ws(headers, num_data_rows=2)

        migrate(ws)

        # Should have inserted columns and updated headers
        # Total Devices is at index 4 (0-based), col 5 (1-based)
        # After replacement: header row should be updated
        ws.update_cell.assert_any_call(1, 5, "Tags")
        ws.insert_cols.assert_called_once()

    def test_inserts_4_new_columns(self):
        """Should insert 4 new columns after 'Total Devices' position (replace 1 + add 4 = 5 total)."""
        headers = [
            "Site ID", "Customer", "Status", "Open Issues",
            "Total Devices", "Last Visit",
        ]
        ws = self._make_ws(headers, num_data_rows=2)

        migrate(ws)

        # insert_cols(col, count): insert 4 columns at position 6 (after col 5)
        ws.insert_cols.assert_called_once_with(6, 4)

    def test_all_five_headers_set(self):
        """All 5 device-type column headers should be written."""
        headers = [
            "Site ID", "Customer", "Status", "Open Issues",
            "Total Devices", "Last Visit",
        ]
        ws = self._make_ws(headers, num_data_rows=2)

        migrate(ws)

        # Check headers were set (col 5 through 9)
        header_calls = [
            c for c in ws.update_cell.call_args_list
            if c[0][0] == 1  # row 1
        ]
        header_texts = [c[0][2] for c in header_calls]
        for col_name in DEVICE_COLUMNS:
            assert col_name in header_texts, f"Missing header: {col_name}"

    def test_sumifs_formulas_for_data_rows(self):
        """Each data row should get SUMIFS formulas referencing Hardware Inventory."""
        headers = [
            "Site ID", "Customer", "Status", "Open Issues",
            "Total Devices", "Last Visit",
        ]
        ws = self._make_ws(headers, num_data_rows=3)

        migrate(ws)

        # Check that formulas were set for data rows (rows 2, 3, 4)
        formula_calls = [
            c for c in ws.update_cell.call_args_list
            if c[0][0] > 1  # data rows
        ]
        # Should have 5 formulas per data row × 3 data rows = 15 formula calls
        assert len(formula_calls) == 15

    def test_sumifs_references_hardware_inventory(self):
        """Formulas should use SUMIFS against 'Hardware Inventory' tab."""
        headers = [
            "Site ID", "Customer", "Status", "Open Issues",
            "Total Devices", "Last Visit",
        ]
        ws = self._make_ws(headers, num_data_rows=1)

        migrate(ws)

        formula_calls = [
            c for c in ws.update_cell.call_args_list
            if c[0][0] > 1
        ]
        for call in formula_calls:
            formula = call[0][2]
            assert "'Hardware Inventory'" in formula, f"Formula missing HW ref: {formula}"

    def test_tags_formula_filters_tag_type(self):
        """Tags column formula should filter for 'Tag' device type."""
        headers = [
            "Site ID", "Customer", "Status", "Open Issues",
            "Total Devices", "Last Visit",
        ]
        ws = self._make_ws(headers, num_data_rows=1)

        migrate(ws)

        # Find the Tags formula (first formula call for row 2)
        formula_calls = [
            c for c in ws.update_cell.call_args_list
            if c[0][0] == 2  # row 2 only
        ]
        tags_formula = formula_calls[0][0][2]
        assert '"Tag"' in tags_formula

    def test_other_formula_sums_remaining_types(self):
        """'Other' column should sum device types not covered by the 4 main columns."""
        headers = [
            "Site ID", "Customer", "Status", "Open Issues",
            "Total Devices", "Last Visit",
        ]
        ws = self._make_ws(headers, num_data_rows=1)

        migrate(ws)

        # Find the Other formula (last formula call for row 2)
        formula_calls = [
            c for c in ws.update_cell.call_args_list
            if c[0][0] == 2
        ]
        other_formula = formula_calls[-1][0][2]
        # Other should include Power Bank, Power Adapter, USB Cable, Other
        assert '"Power Bank"' in other_formula or "SUMIFS" in other_formula

    def test_idempotent_already_migrated(self):
        """Should not modify if already migrated (Tags column already exists)."""
        headers = [
            "Site ID", "Customer", "Status", "Open Issues",
            "Tags", "Anchors", "Gateways", "Charging Docks", "Other",
            "Last Visit",
        ]
        ws = self._make_ws(headers, num_data_rows=2)

        migrate(ws)

        ws.insert_cols.assert_not_called()
        ws.update_cell.assert_not_called()

    def test_idempotent_no_total_devices(self):
        """Should warn if neither 'Total Devices' nor 'Tags' found."""
        headers = ["Site ID", "Customer", "Status"]
        ws = self._make_ws(headers, num_data_rows=1)

        # Should not raise, just warn
        migrate(ws)

        ws.insert_cols.assert_not_called()

    def test_site_id_column_reference_in_formula(self):
        """Formulas should reference the Site ID column (A) for matching."""
        headers = [
            "Site ID", "Customer", "Status", "Open Issues",
            "Total Devices", "Last Visit",
        ]
        ws = self._make_ws(headers, num_data_rows=1)

        migrate(ws)

        formula_calls = [
            c for c in ws.update_cell.call_args_list
            if c[0][0] == 2
        ]
        # Each formula should reference the site ID cell in that row
        for call in formula_calls:
            formula = call[0][2]
            assert "$A2" in formula or "A2" in formula, f"Missing Site ID ref: {formula}"
