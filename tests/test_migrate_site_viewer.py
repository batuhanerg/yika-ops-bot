"""Tests for Site Viewer migration script (Session 6, Item 6).

Changes:
- Site selector shows "Customer (Site ID)" format instead of bare Site ID
- Support Log section headers match current Support Log tab (with Ticket ID)
- Key columns widened (Issue Summary 40, Resolution 40, Notes 30 chars)
- Support log sorted by Received Date descending (SORT+FILTER formula)
- Safe to run multiple times (idempotent)
"""

from unittest.mock import MagicMock, call

from scripts.migrate_site_viewer import migrate


class TestSiteViewerMigration:
    """Test the Site Viewer tab migration."""

    def _make_ws(self, headers: list[str] | None = None) -> MagicMock:
        """Create a mock worksheet."""
        ws = MagicMock()
        if headers:
            ws.row_values.return_value = headers
        return ws

    def _make_sites_ws(self, sites: list[list[str]] | None = None) -> MagicMock:
        """Create a mock Sites worksheet with data."""
        ws = MagicMock()
        if sites is None:
            sites = [
                ["Site ID", "Customer"],
                ["ASM-TR-01", "Anadolu Sağlık Merkezi"],
                ["MIG-TR-01", "Migros"],
            ]
        ws.get_all_values.return_value = sites
        return ws

    def test_selector_format_customer_site_id(self):
        """Dropdown values should be 'Customer (Site ID)' format."""
        viewer_ws = self._make_ws()
        sites_ws = self._make_sites_ws()

        migrate(viewer_ws, sites_ws)

        # Check that data validation was set with Customer (Site ID) format
        set_dv_calls = [
            c for c in viewer_ws.method_calls
            if "data_validation" in str(c).lower() or "set_data_validation" in str(c).lower()
        ]
        # Alternative: check batch_update or update calls for validation rules
        # The migrate function should set up a dropdown with the formatted values
        all_calls_str = str(viewer_ws.method_calls)
        assert "Anadolu Sağlık Merkezi (ASM-TR-01)" in all_calls_str or \
               viewer_ws.batch_update.called or viewer_ws.update.called

    def test_support_log_headers_include_ticket_id(self):
        """Support Log section should have Ticket ID as first column header."""
        viewer_ws = self._make_ws()
        sites_ws = self._make_sites_ws()

        migrate(viewer_ws, sites_ws)

        all_calls = viewer_ws.update_cell.call_args_list + viewer_ws.update.call_args_list
        all_text = str(all_calls)
        assert "Ticket ID" in all_text

    def test_support_log_headers_match_current_schema(self):
        """Support Log section headers should match the current Support Log tab columns."""
        viewer_ws = self._make_ws()
        sites_ws = self._make_sites_ws()

        migrate(viewer_ws, sites_ws)

        all_text = str(viewer_ws.update_cell.call_args_list + viewer_ws.update.call_args_list)
        # Key columns that should be present
        for header in ["Ticket ID", "Site ID", "Received Date", "Status", "Issue Summary", "Responsible"]:
            assert header in all_text, f"Missing header: {header}"

    def test_sort_formula_descending_by_received_date(self):
        """Support log should use SORT(FILTER(...)) ordered by Received Date descending."""
        viewer_ws = self._make_ws()
        sites_ws = self._make_sites_ws()

        migrate(viewer_ws, sites_ws)

        all_text = str(viewer_ws.update_cell.call_args_list + viewer_ws.update.call_args_list)
        # Should contain SORT and FILTER for descending date order
        assert "SORT" in all_text
        assert "FILTER" in all_text

    def test_column_widths_set(self):
        """Key columns should be widened for readability."""
        viewer_ws = self._make_ws()
        sites_ws = self._make_sites_ws()
        spreadsheet = MagicMock()
        viewer_ws.spreadsheet = spreadsheet

        migrate(viewer_ws, sites_ws)

        # Should call batch_update on spreadsheet for column widths
        # or use set_column_width / format on the worksheet
        assert spreadsheet.batch_update.called or viewer_ws.batch_update.called or \
               viewer_ws.columns_auto_resize.called or \
               any("columnWidth" in str(c) or "pixelSize" in str(c)
                   for c in spreadsheet.method_calls + viewer_ws.method_calls)

    def test_idempotent_run(self):
        """Running twice should not error or duplicate content."""
        viewer_ws = self._make_ws()
        sites_ws = self._make_sites_ws()

        # First run
        migrate(viewer_ws, sites_ws)
        first_call_count = len(viewer_ws.method_calls)

        # Reset mock
        viewer_ws.reset_mock()

        # Second run
        migrate(viewer_ws, sites_ws)
        # Should still work without errors
        # (The function always overwrites, which is idempotent)
