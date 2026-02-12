"""Tests for Dashboard migration script (Session 6, Item 5).

Replaces the single "Total Devices" column with five device-type columns:
Tags, Anchors, Gateways, Charging Docks, Other.
Each column uses SUMIFS to count devices by type from Hardware Inventory.
"""

from unittest.mock import MagicMock

from scripts.migrate_dashboard import migrate, DEVICE_COLUMNS


class TestDashboardMigration:
    """Test the Dashboard tab migration."""

    def _make_ws(
        self,
        headers: list[str],
        num_data_rows: int = 3,
        header_row: int = 1,
    ) -> MagicMock:
        """Create a mock worksheet with given headers and data rows."""
        ws = MagicMock()
        ws.id = 0
        ws.row_count = header_row + num_data_rows
        # Build get_all_values: empty rows before header, then header, then data
        all_values = []
        for _ in range(header_row - 1):
            all_values.append([""] * len(headers))
        all_values.append(headers)
        site_col = headers.index("Site ID") if "Site ID" in headers else 0
        for r in range(num_data_rows):
            row = [""] * len(headers)
            row[site_col] = f"SITE-{r+1:02d}"
            all_values.append(row)
        ws.get_all_values.return_value = all_values
        ws.spreadsheet = MagicMock()
        return ws

    def _get_batch_rows(self, ws) -> list[list[str]]:
        """Extract the rows from the batch update call."""
        return ws.update.call_args[0][1]

    def test_device_columns_constant(self):
        assert DEVICE_COLUMNS == ["Tags", "Anchors", "Gateways", "Charging Docks", "Other"]

    def test_replaces_total_devices_header(self):
        headers = ["Site ID", "Customer", "Status", "Open Issues", "Total Devices", "Last Visit"]
        ws = self._make_ws(headers, num_data_rows=2)

        migrate(ws)

        rows = self._get_batch_rows(ws)
        assert rows[0] == DEVICE_COLUMNS  # header row

    def test_inserts_4_new_columns_via_batch(self):
        headers = ["Site ID", "Customer", "Status", "Open Issues", "Total Devices", "Last Visit"]
        ws = self._make_ws(headers, num_data_rows=2)

        migrate(ws)

        ws.spreadsheet.batch_update.assert_called_once()
        req = ws.spreadsheet.batch_update.call_args[0][0]["requests"][0]
        dim = req["insertDimension"]["range"]
        assert dim["startIndex"] == 5  # after col 5 (0-based)
        assert dim["endIndex"] == 9    # 4 columns

    def test_all_five_headers_set(self):
        headers = ["Site ID", "Customer", "Status", "Open Issues", "Total Devices", "Last Visit"]
        ws = self._make_ws(headers, num_data_rows=2)

        migrate(ws)

        rows = self._get_batch_rows(ws)
        for col_name in DEVICE_COLUMNS:
            assert col_name in rows[0], f"Missing header: {col_name}"

    def test_sumifs_formulas_for_data_rows(self):
        headers = ["Site ID", "Customer", "Status", "Open Issues", "Total Devices", "Last Visit"]
        ws = self._make_ws(headers, num_data_rows=3)

        migrate(ws)

        rows = self._get_batch_rows(ws)
        # header + 3 data rows
        assert len(rows) == 4
        # Each data row has 5 formulas
        for data_row in rows[1:]:
            assert len(data_row) == 5

    def test_sumifs_references_hardware_inventory(self):
        headers = ["Site ID", "Customer", "Status", "Open Issues", "Total Devices", "Last Visit"]
        ws = self._make_ws(headers, num_data_rows=1)

        migrate(ws)

        rows = self._get_batch_rows(ws)
        for formula in rows[1]:  # first data row
            assert "'Hardware Inventory'" in formula, f"Formula missing HW ref: {formula}"

    def test_tags_formula_filters_tag_type(self):
        headers = ["Site ID", "Customer", "Status", "Open Issues", "Total Devices", "Last Visit"]
        ws = self._make_ws(headers, num_data_rows=1)

        migrate(ws)

        rows = self._get_batch_rows(ws)
        tags_formula = rows[1][0]  # first column of first data row
        assert '"Tag"' in tags_formula

    def test_other_formula_sums_remaining_types(self):
        headers = ["Site ID", "Customer", "Status", "Open Issues", "Total Devices", "Last Visit"]
        ws = self._make_ws(headers, num_data_rows=1)

        migrate(ws)

        rows = self._get_batch_rows(ws)
        other_formula = rows[1][-1]  # last column of first data row
        assert '"Power Bank"' in other_formula

    def test_idempotent_already_migrated(self):
        headers = [
            "Site ID", "Customer", "Status", "Open Issues",
            "Tags", "Anchors", "Gateways", "Charging Docks", "Other", "Last Visit",
        ]
        ws = self._make_ws(headers, num_data_rows=2)

        migrate(ws)

        ws.spreadsheet.batch_update.assert_not_called()
        ws.update.assert_not_called()

    def test_idempotent_no_total_devices(self):
        headers = ["Site ID", "Customer", "Status"]
        ws = self._make_ws(headers, num_data_rows=1)

        migrate(ws)

        ws.spreadsheet.batch_update.assert_not_called()

    def test_site_id_column_reference_in_formula(self):
        headers = ["Site ID", "Customer", "Status", "Open Issues", "Total Devices", "Last Visit"]
        ws = self._make_ws(headers, num_data_rows=1)

        migrate(ws)

        rows = self._get_batch_rows(ws)
        for formula in rows[1]:
            assert "$A2" in formula, f"Missing Site ID ref: {formula}"

    def test_header_on_row_5(self):
        """Should find headers on row 5 (Dashboard has title rows above)."""
        headers = [
            "", "Site ID", "Customer", "City", "Facility", "Status",
            "Total Devices", "Last Visit", "Open Issues", "Last Verified",
        ]
        ws = self._make_ws(headers, num_data_rows=4, header_row=5)

        migrate(ws)

        rows = self._get_batch_rows(ws)
        assert "Tags" in rows[0]

    def test_site_id_in_col_b(self):
        """When Site ID is in column B, formulas should reference $B."""
        headers = [
            "", "Site ID", "Customer", "City", "Facility", "Status",
            "Total Devices", "Last Visit",
        ]
        ws = self._make_ws(headers, num_data_rows=1, header_row=5)

        migrate(ws)

        rows = self._get_batch_rows(ws)
        for formula in rows[1]:  # first data row (row 6 in sheet)
            assert "$B6" in formula, f"Expected $B6 reference, got: {formula}"

    def test_batch_range_notation(self):
        """Batch update should use correct A1 range notation."""
        headers = ["Site ID", "Customer", "Status", "Open Issues", "Total Devices", "Last Visit"]
        ws = self._make_ws(headers, num_data_rows=2)

        migrate(ws)

        # Total Devices at index 4 → col E; 5 columns → E through I
        range_str = ws.update.call_args[0][0]
        assert "E1" in range_str
