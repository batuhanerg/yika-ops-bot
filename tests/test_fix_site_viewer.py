"""Tests for Site Viewer hotfix script.

Fixes:
- Helper cell D4 extracts Site ID from "Customer (Site ID)" selector
- All formulas updated from $C$4 to $D$4
- Support log spill area (B62-M81) cleared so SORT can populate
"""

from unittest.mock import MagicMock, patch

from scripts.fix_site_viewer import fix


class TestFixSiteViewer:

    def _make_viewer_ws(self) -> MagicMock:
        """Create a mock Site Viewer worksheet with realistic layout."""
        ws = MagicMock()
        ws.id = 100
        ws.title = "Site Viewer"
        ws.spreadsheet = MagicMock()
        ws.spreadsheet.id = "test-spreadsheet-id"

        # Mock client auth for API calls
        mock_auth = MagicMock()
        mock_auth.token = "test-token"
        ws.spreadsheet.client.auth = mock_auth

        # Simulate realistic layout
        all_values = [
            [""],                                         # row 1
            ["", "ERG CONTROLS — SITE VIEWER"],           # row 2
            [""],                                         # row 3
            ["", "Select Site:", "Migros (MIG-TR-01)"],   # row 4
            [""],                                         # row 5
        ]
        # Pad to row 59
        while len(all_values) < 59:
            all_values.append([""])
        all_values.append(["", "📞 SUPPORT LOG"])         # row 60
        all_values.append(["", "Ticket ID", "Site ID"])   # row 61 (headers)
        # Add some data rows
        for _ in range(20):
            all_values.append([""])
        ws.get_all_values.return_value = all_values
        return ws

    def _build_api_response(self, formulas: dict[tuple[int, int], str]) -> dict:
        """Build a mock Google Sheets API response with formulas.

        formulas: {(row_0based, col_0based): formula_string}
        """
        max_row = max(r for r, _ in formulas.keys()) + 1 if formulas else 1
        max_col = max(c for _, c in formulas.keys()) + 1 if formulas else 1

        row_data = []
        for i in range(max_row + 20):  # extra rows for support log area
            values = []
            for j in range(max(max_col + 1, 14)):  # at least 14 columns
                cell = {}
                if (i, j) in formulas:
                    cell = {"userEnteredValue": {"formulaValue": formulas[(i, j)]}}
                values.append(cell)
            row_data.append({"values": values})

        return {
            "sheets": [{
                "data": [{
                    "rowData": row_data,
                }]
            }]
        }

    @patch("scripts.fix_site_viewer.requests")
    def test_helper_cell_written(self, mock_requests):
        """Should write REGEXEXTRACT formula in helper cell D4."""
        ws = self._make_viewer_ws()

        # Mock API response with formulas referencing $C$4
        formulas = {
            (6, 2): '=IFERROR(VLOOKUP($C$4,Sites!$A:$P,2,FALSE()),"")',  # C7
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._build_api_response(formulas)
        mock_requests.get.return_value = mock_resp

        fix(ws)

        # Helper cell should be written at D4 (row 4, col 4)
        ws.update_cell.assert_any_call(
            4, 4,
            '=IFERROR(REGEXEXTRACT(C4,"\\(([^)]+)\\)"),C4)',
        )

    @patch("scripts.fix_site_viewer.requests")
    def test_formulas_updated_to_helper_ref(self, mock_requests):
        """Formulas should reference $D$4 instead of $C$4."""
        ws = self._make_viewer_ws()

        formulas = {
            (6, 2): '=IFERROR(VLOOKUP($C$4,Sites!$A:$P,2,FALSE()),"")',  # C7
            (7, 2): '=IFERROR(VLOOKUP($C$4,Sites!$A:$P,3,FALSE()),"")',  # C8
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._build_api_response(formulas)
        mock_requests.get.return_value = mock_resp

        fix(ws)

        # Check batch_update was called with updated formulas
        batch_call = ws.spreadsheet.batch_update.call_args
        requests_list = batch_call[0][0]["requests"]

        updated_formulas = []
        for req in requests_list:
            if "updateCells" in req:
                formula = req["updateCells"]["rows"][0]["values"][0]["userEnteredValue"]["formulaValue"]
                updated_formulas.append(formula)

        # All formulas should now reference $D$4
        for f in updated_formulas:
            assert "$D$4" in f, f"Formula still references $C$4: {f}"
            assert "$C$4" not in f, f"Formula still has old ref: {f}"

    @patch("scripts.fix_site_viewer.requests")
    def test_support_log_spill_area_cleared(self, mock_requests):
        """B62-M81 should be cleared so SORT formula can spill."""
        ws = self._make_viewer_ws()

        # Add formulas in the support log area
        formulas = {
            (61, 0): '=IFERROR(SORT(FILTER(\'Support Log\'!A:M,\'Support Log\'!B:B=REGEXEXTRACT(C4,"\\(([^)]+)\\)")),3,FALSE),)',
            (61, 1): '=IFERROR(INDEX(filter(\'Support Log\'!$C$2:$C$494,\'Support Log\'!$B$2:$B$494=$C$4),1),"")',
            (61, 2): '=IFERROR(INDEX(filter(\'Support Log\'!$F$2:$F$494,\'Support Log\'!$B$2:$B$494=$C$4),1),"")',
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._build_api_response(formulas)
        mock_requests.get.return_value = mock_resp

        fix(ws)

        # The update call should clear B62-M81 with empty values
        update_calls = ws.update.call_args_list
        clear_found = False
        for call in update_calls:
            kwargs = call.kwargs or {}
            range_name = kwargs.get("range_name", call[0][0] if call[0] else "")
            if "B62" in str(range_name):
                clear_found = True
                values = kwargs.get("values") or call[0][1]
                # Should be empty strings
                assert all(cell == "" for row in values for cell in row)
        assert clear_found, "Support log spill area not cleared"

    @patch("scripts.fix_site_viewer.requests")
    def test_sort_formula_uses_helper_cell(self, mock_requests):
        """SORT formula at A62 should reference $D$4 directly."""
        ws = self._make_viewer_ws()

        formulas = {
            (61, 0): '=IFERROR(SORT(FILTER(\'Support Log\'!A:M,\'Support Log\'!B:B=REGEXEXTRACT(C4,"\\(([^)]+)\\)")),3,FALSE),)',
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._build_api_response(formulas)
        mock_requests.get.return_value = mock_resp

        fix(ws)

        # The SORT formula should be rewritten
        sort_calls = [
            call for call in ws.update_cell.call_args_list
            if call[0][0] == 62 and call[0][1] == 1  # row 62, col A
        ]
        assert len(sort_calls) == 1
        formula = sort_calls[0][0][2]
        assert "$D$4" in formula
        assert "REGEXEXTRACT" not in formula
        assert "SORT" in formula
        assert "FILTER" in formula

    @patch("scripts.fix_site_viewer.requests")
    def test_dry_run_no_changes(self, mock_requests):
        """--dry-run should not modify anything."""
        ws = self._make_viewer_ws()

        formulas = {
            (6, 2): '=IFERROR(VLOOKUP($C$4,Sites!$A:$P,2,FALSE()),"")',
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._build_api_response(formulas)
        mock_requests.get.return_value = mock_resp

        result = fix(ws, dry_run=True)

        ws.update_cell.assert_not_called()
        ws.update.assert_not_called()
        ws.spreadsheet.batch_update.assert_not_called()
        assert result["formula_updates"] > 0

    @patch("scripts.fix_site_viewer.requests")
    def test_returns_summary(self, mock_requests):
        """Should return a summary dict with change counts."""
        ws = self._make_viewer_ws()

        formulas = {
            (6, 2): '=IFERROR(VLOOKUP($C$4,Sites!$A:$P,2,FALSE()),"")',
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._build_api_response(formulas)
        mock_requests.get.return_value = mock_resp

        result = fix(ws)

        assert "helper_cell" in result
        assert result["helper_cell"] == "D4"
        assert "formula_updates" in result
        assert "cells_cleared" in result
