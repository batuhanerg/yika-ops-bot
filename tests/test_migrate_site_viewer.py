"""Tests for Site Viewer migration script (Session 6, Item 6).

Changes:
- Site selector shows "Customer (Site ID)" format
- Support Log section headers match current schema (with Ticket ID)
- Key columns widened, support log sorted by Received Date descending
- Safe to run multiple times (idempotent — always overwrites)
"""

from unittest.mock import MagicMock

from scripts.migrate_site_viewer import migrate, SUPPORT_LOG_HEADERS


class TestSiteViewerMigration:

    def _make_viewer_ws(self) -> MagicMock:
        """Create a mock Site Viewer worksheet with realistic layout."""
        ws = MagicMock()
        ws.id = 100
        ws.spreadsheet = MagicMock()
        # Simulate realistic layout
        all_values = [
            [""],                                         # row 1
            ["", "ERG CONTROLS — SITE VIEWER"],           # row 2
            [""],                                         # row 3
            ["", "Select Site:", "EST-TR-01"],             # row 4
            [""],                                         # row 5
            # ... site info rows ...
        ]
        # Pad to row 59
        while len(all_values) < 59:
            all_values.append([""])
        all_values.append(["", "📞 SUPPORT LOG"])         # row 60
        all_values.append(["", "Received", "Status"])     # row 61 (old headers)
        ws.get_all_values.return_value = all_values
        return ws

    def _make_sites_ws(self) -> MagicMock:
        ws = MagicMock()
        ws.get_all_values.return_value = [
            ["Site ID", "Customer"],
            ["ASM-TR-01", "Anadolu Sağlık Merkezi"],
            ["MIG-TR-01", "Migros"],
            ["EST-TR-01", "Este Nove"],
        ]
        return ws

    def test_selector_dropdown_has_customer_format(self):
        """Dropdown should contain 'Customer (Site ID)' values."""
        viewer_ws = self._make_viewer_ws()
        sites_ws = self._make_sites_ws()

        migrate(viewer_ws, sites_ws)

        # Check batch_update was called with data validation containing customer names
        all_text = str(viewer_ws.spreadsheet.batch_update.call_args_list)
        assert "Anadolu Sağlık Merkezi (ASM-TR-01)" in all_text
        assert "Migros (MIG-TR-01)" in all_text

    def test_support_log_headers_include_ticket_id(self):
        """Support Log section should have Ticket ID as first column header."""
        viewer_ws = self._make_viewer_ws()
        sites_ws = self._make_sites_ws()

        migrate(viewer_ws, sites_ws)

        # Check that the update call contains Ticket ID in headers
        update_call = viewer_ws.update.call_args
        rows = update_call.kwargs.get("values") or update_call[0][1]
        assert rows[0][0] == "Ticket ID"

    def test_support_log_headers_match_schema(self):
        """Support Log headers should match current schema."""
        viewer_ws = self._make_viewer_ws()
        sites_ws = self._make_sites_ws()

        migrate(viewer_ws, sites_ws)

        update_call = viewer_ws.update.call_args
        rows = update_call.kwargs.get("values") or update_call[0][1]
        assert rows[0] == SUPPORT_LOG_HEADERS

    def test_sort_filter_formula_written(self):
        """Should write SORT(FILTER(...)) formula for support log data."""
        viewer_ws = self._make_viewer_ws()
        sites_ws = self._make_sites_ws()

        migrate(viewer_ws, sites_ws)

        # update_cell should be called for the formula
        formula_call = viewer_ws.update_cell.call_args
        formula = formula_call[0][2]
        assert "SORT" in formula
        assert "FILTER" in formula
        assert "'Support Log'" in formula

    def test_column_widths_set(self):
        """Key columns should be widened via batch_update."""
        viewer_ws = self._make_viewer_ws()
        sites_ws = self._make_sites_ws()

        migrate(viewer_ws, sites_ws)

        all_text = str(viewer_ws.spreadsheet.batch_update.call_args_list)
        assert "pixelSize" in all_text

    def test_idempotent_run(self):
        """Running twice should not error or duplicate content."""
        viewer_ws = self._make_viewer_ws()
        sites_ws = self._make_sites_ws()

        migrate(viewer_ws, sites_ws)
        viewer_ws.reset_mock()
        viewer_ws.spreadsheet = MagicMock()
        viewer_ws.id = 100
        # Re-set get_all_values (reset_mock clears it)
        all_values = [[""], ["", "ERG CONTROLS"], [""], ["", "Select Site:", "EST-TR-01"]]
        while len(all_values) < 59:
            all_values.append([""])
        all_values.append(["", "📞 SUPPORT LOG"])
        all_values.append(["", "Ticket ID", "Site ID"])  # already migrated headers
        viewer_ws.get_all_values.return_value = all_values

        migrate(viewer_ws, sites_ws)
        # Should complete without error

    def test_detects_selector_at_row_4(self):
        """Should find 'Select Site:' at row 4 and reference the selector cell."""
        viewer_ws = self._make_viewer_ws()
        sites_ws = self._make_sites_ws()

        migrate(viewer_ws, sites_ws)

        # "Select Site:" is at B4, so selector is at C4 (next column)
        formula_call = viewer_ws.update_cell.call_args
        formula = formula_call[0][2]
        assert "C4" in formula

    def test_detects_support_log_section(self):
        """Should find '📞 SUPPORT LOG' and write headers on the next row."""
        viewer_ws = self._make_viewer_ws()
        sites_ws = self._make_sites_ws()

        migrate(viewer_ws, sites_ws)

        # Headers should be written at row 61 (section at row 60 + 1)
        update_call = viewer_ws.update.call_args
        range_str = update_call.kwargs.get("range_name") or update_call[0][0]
        assert "61" in range_str
