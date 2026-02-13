"""Tests for conditional formatting migration script (Session 6, Item 7).

Applies color-coded conditional formatting rules across all tabs:
- Red (#FFEBEE): empty must-field cells
- Yellow (#FFF9C4): empty important-field cells
- Blue (#E3F2FD): Last Verified > 30 days
- Orange (#FFF3E0): open support tickets with Received Date > 7 days

Context-aware: skips formatting for "Awaiting Installation" sites.
Idempotent: clears existing rules before applying.
Supports --dry-run flag.
"""

from unittest.mock import MagicMock, patch, call

from scripts.migrate_conditional_formatting import (
    build_formatting_rules,
    migrate,
    _build_site_viewer_requests,
    COLOR_RED,
    COLOR_YELLOW,
    COLOR_BLUE,
    COLOR_ORANGE,
)


class TestColorConstants:
    """Test that color constants are correctly defined."""

    def test_red_for_must_fields(self):
        assert COLOR_RED == {"red": 1.0, "green": 0.922, "blue": 0.933}

    def test_yellow_for_important_fields(self):
        assert COLOR_YELLOW == {"red": 1.0, "green": 0.976, "blue": 0.769}

    def test_blue_for_stale_verified(self):
        assert COLOR_BLUE == {"red": 0.890, "green": 0.949, "blue": 0.992}

    def test_orange_for_stale_tickets(self):
        assert COLOR_ORANGE == {"red": 1.0, "green": 0.953, "blue": 0.878}


class TestBuildFormattingRules:
    """Test the rule-building logic."""

    def test_returns_list_of_rules(self):
        rules = build_formatting_rules()
        assert isinstance(rules, list)
        assert len(rules) > 0

    def test_rules_cover_sites_tab(self):
        rules = build_formatting_rules()
        tab_names = {r["tab"] for r in rules}
        assert "Sites" in tab_names

    def test_rules_cover_hardware_inventory(self):
        rules = build_formatting_rules()
        tab_names = {r["tab"] for r in rules}
        assert "Hardware Inventory" in tab_names

    def test_rules_cover_support_log(self):
        rules = build_formatting_rules()
        tab_names = {r["tab"] for r in rules}
        assert "Support Log" in tab_names

    def test_rules_cover_stock(self):
        rules = build_formatting_rules()
        tab_names = {r["tab"] for r in rules}
        assert "Stock" in tab_names

    def test_rules_cover_implementation_details(self):
        rules = build_formatting_rules()
        tab_names = {r["tab"] for r in rules}
        assert "Implementation Details" in tab_names

    def test_must_field_rules_use_red(self):
        rules = build_formatting_rules()
        must_rules = [r for r in rules if r["severity"] == "must"]
        assert len(must_rules) > 0
        for r in must_rules:
            assert r["color"] == COLOR_RED

    def test_important_field_rules_use_yellow(self):
        rules = build_formatting_rules()
        important_rules = [r for r in rules if r["severity"] == "important"]
        assert len(important_rules) > 0
        for r in important_rules:
            assert r["color"] == COLOR_YELLOW

    def test_stale_verified_rule_uses_blue(self):
        rules = build_formatting_rules()
        blue_rules = [r for r in rules if r["color"] == COLOR_BLUE]
        assert len(blue_rules) > 0

    def test_stale_ticket_rule_uses_orange(self):
        rules = build_formatting_rules()
        orange_rules = [r for r in rules if r["color"] == COLOR_ORANGE]
        assert len(orange_rules) > 0

    def test_sites_must_fields_included(self):
        """Sites must fields (customer, city, etc.) should generate red rules."""
        rules = build_formatting_rules()
        sites_must = [
            r for r in rules
            if r["tab"] == "Sites" and r["severity"] == "must"
        ]
        field_names = [r["field"] for r in sites_must]
        assert "Customer" in field_names
        assert "City" in field_names
        assert "Country" in field_names

    def test_hardware_must_fields_included(self):
        """Hardware must fields should generate red rules."""
        rules = build_formatting_rules()
        hw_must = [
            r for r in rules
            if r["tab"] == "Hardware Inventory" and r["severity"] == "must"
        ]
        field_names = [r["field"] for r in hw_must]
        assert "Device Type" in field_names
        assert "Qty" in field_names

    def test_support_log_must_fields_included(self):
        """Support Log must fields should generate red rules."""
        rules = build_formatting_rules()
        sl_must = [
            r for r in rules
            if r["tab"] == "Support Log" and r["severity"] == "must"
        ]
        field_names = [r["field"] for r in sl_must]
        assert "Received Date" in field_names
        assert "Status" in field_names
        assert "Issue Summary" in field_names
        assert "Responsible" in field_names


class TestMigrate:
    """Test the migrate function."""

    def _make_spreadsheet(self, sheet_ids: dict[str, int] | None = None) -> MagicMock:
        """Create a mock spreadsheet with worksheets."""
        spreadsheet = MagicMock()
        if sheet_ids is None:
            sheet_ids = {
                "Sites": 0,
                "Hardware Inventory": 1,
                "Implementation Details": 2,
                "Support Log": 3,
                "Stock": 4,
                "Site Viewer": 5,
            }

        worksheets = []
        for name, sid in sheet_ids.items():
            ws = MagicMock()
            ws.title = name
            ws.id = sid
            # Default headers based on tab name
            if name == "Sites":
                ws.row_values.return_value = [
                    "Site ID", "Customer", "City", "Country", "Address",
                    "Facility Type", "Dashboard Link", "Supervisor 1", "Phone 1",
                    "Email 1", "Supervisor 2", "Phone 2", "Email 2",
                    "Go-live Date", "Contract Status", "Notes", "Whatsapp Group",
                ]
            elif name == "Hardware Inventory":
                ws.row_values.return_value = [
                    "Site ID", "Device Type", "HW Version", "FW Version",
                    "Qty", "Last Verified", "Notes",
                ]
            elif name == "Support Log":
                ws.row_values.return_value = [
                    "Ticket ID", "Site ID", "Received Date", "Resolved Date",
                    "Type", "Status", "Root Cause", "Reported By",
                    "Issue Summary", "Resolution", "Devices Affected",
                    "Responsible", "Notes",
                ]
            elif name == "Stock":
                ws.row_values.return_value = [
                    "Location", "Device Type", "HW Version", "FW Version",
                    "Qty", "Condition", "Reserved For", "Notes",
                ]
            elif name == "Implementation Details":
                ws.row_values.return_value = [
                    "Site ID", "Internet Provider", "SSID", "Password",
                    "Gateway Placement", "Charging Dock Placement",
                ]
            elif name == "Site Viewer":
                ws.row_values.return_value = []  # No data headers to read
            worksheets.append(ws)

        spreadsheet.worksheets.return_value = worksheets

        def _worksheet(name):
            for ws in worksheets:
                if ws.title == name:
                    return ws
            raise Exception(f"Worksheet not found: {name}")

        spreadsheet.worksheet.side_effect = _worksheet
        return spreadsheet

    def test_applies_rules(self):
        """Should apply conditional formatting rules via batch_update."""
        spreadsheet = self._make_spreadsheet()

        migrate(spreadsheet)

        assert spreadsheet.batch_update.called

    def test_applies_rules_via_batch_update(self):
        """Should apply formatting rules via spreadsheet.batch_update."""
        spreadsheet = self._make_spreadsheet()

        migrate(spreadsheet)

        assert spreadsheet.batch_update.called
        # Check that addConditionalFormatRule requests are included
        all_calls = spreadsheet.batch_update.call_args_list
        all_requests = []
        for c in all_calls:
            body = c[0][0] if c[0] else c[1].get("body", {})
            all_requests.extend(body.get("requests", []))

        add_rules = [r for r in all_requests if "addConditionalFormatRule" in r]
        assert len(add_rules) > 0

    def test_dry_run_does_not_modify(self):
        """--dry-run should not call batch_update."""
        spreadsheet = self._make_spreadsheet()

        migrate(spreadsheet, dry_run=True)

        spreadsheet.batch_update.assert_not_called()

    def test_dry_run_returns_rules(self):
        """--dry-run should return the rules that would be applied."""
        spreadsheet = self._make_spreadsheet()

        result = migrate(spreadsheet, dry_run=True)

        assert isinstance(result, list)
        assert len(result) > 0

    def test_red_rules_for_must_fields(self):
        """Red formatting rules should be included for must fields."""
        spreadsheet = self._make_spreadsheet()

        migrate(spreadsheet)

        all_calls = spreadsheet.batch_update.call_args_list
        all_requests = []
        for c in all_calls:
            body = c[0][0] if c[0] else c[1].get("body", {})
            all_requests.extend(body.get("requests", []))

        add_rules = [r for r in all_requests if "addConditionalFormatRule" in r]
        # Check at least some rules have red background color
        red_found = False
        for rule in add_rules:
            bool_rule = rule["addConditionalFormatRule"]["rule"].get("booleanRule", {})
            bg = bool_rule.get("format", {}).get("backgroundColor", {})
            if bg.get("red") == 1.0 and bg.get("green", 0) < 0.95:
                red_found = True
                break
        assert red_found, "No red formatting rules found for must fields"

    def test_all_rules_use_custom_formula(self):
        """All rules should use CUSTOM_FORMULA (not BLANK) to skip empty rows."""
        spreadsheet = self._make_spreadsheet()

        migrate(spreadsheet)

        all_calls = spreadsheet.batch_update.call_args_list
        all_requests = []
        for c in all_calls:
            body = c[0][0] if c[0] else c[1].get("body", {})
            all_requests.extend(body.get("requests", []))

        add_rules = [r for r in all_requests if "addConditionalFormatRule" in r]
        for rule in add_rules:
            bool_rule = rule["addConditionalFormatRule"]["rule"]["booleanRule"]
            condition = bool_rule["condition"]
            assert condition["type"] == "CUSTOM_FORMULA", (
                f"Expected CUSTOM_FORMULA, got {condition['type']}"
            )

    def test_blank_rules_include_row_has_data_guard(self):
        """Must/important blank rules should check that first column is not empty."""
        spreadsheet = self._make_spreadsheet()

        migrate(spreadsheet)

        all_calls = spreadsheet.batch_update.call_args_list
        all_requests = []
        for c in all_calls:
            body = c[0][0] if c[0] else c[1].get("body", {})
            all_requests.extend(body.get("requests", []))

        add_rules = [r for r in all_requests if "addConditionalFormatRule" in r]
        for rule in add_rules:
            bool_rule = rule["addConditionalFormatRule"]["rule"]["booleanRule"]
            condition = bool_rule["condition"]
            formula = condition["values"][0]["userEnteredValue"]
            # Site Viewer rules (sheet_id=5) use $D$4 as guard instead of $A
            sheet_id = rule["addConditionalFormatRule"]["rule"]["ranges"][0]["sheetId"]
            if sheet_id == 5:
                assert "$D$4" in formula, f"Missing helper cell guard in: {formula}"
            else:
                assert "$A" in formula, f"Missing first-column guard in: {formula}"

    def test_impl_details_header_row_2(self):
        """Implementation Details should use header_row=2 (startRowIndex=2)."""
        spreadsheet = self._make_spreadsheet()

        migrate(spreadsheet)

        all_calls = spreadsheet.batch_update.call_args_list
        all_requests = []
        for c in all_calls:
            body = c[0][0] if c[0] else c[1].get("body", {})
            all_requests.extend(body.get("requests", []))

        add_rules = [r for r in all_requests if "addConditionalFormatRule" in r]
        # Find rules for Implementation Details (sheet_id=2)
        impl_rules = [
            r for r in add_rules
            if r["addConditionalFormatRule"]["rule"]["ranges"][0]["sheetId"] == 2
        ]
        assert len(impl_rules) > 0
        for rule in impl_rules:
            start_row = rule["addConditionalFormatRule"]["rule"]["ranges"][0]["startRowIndex"]
            assert start_row == 2, f"Impl Details rule should skip 2 header rows, got startRowIndex={start_row}"
            # Formula should reference row 3 (first data row after header on row 2)
            formula = rule["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
            assert "3" in formula, f"Impl Details formula should reference row 3: {formula}"

    def test_site_viewer_rules_included(self):
        """Site Viewer should get red/yellow formatting for site info cells."""
        spreadsheet = self._make_spreadsheet()

        migrate(spreadsheet)

        all_calls = spreadsheet.batch_update.call_args_list
        all_requests = []
        for c in all_calls:
            body = c[0][0] if c[0] else c[1].get("body", {})
            all_requests.extend(body.get("requests", []))

        add_rules = [r for r in all_requests if "addConditionalFormatRule" in r]
        # Find rules for Site Viewer (sheet_id=5)
        viewer_rules = [
            r for r in add_rules
            if r["addConditionalFormatRule"]["rule"]["ranges"][0]["sheetId"] == 5
        ]
        assert len(viewer_rules) == 10, f"Expected 10 Site Viewer rules, got {len(viewer_rules)}"

    def test_site_viewer_rules_check_helper_cell(self):
        """Site Viewer rules should reference $D$4 (the helper cell)."""
        viewer_rules = _build_site_viewer_requests(sheet_id=5)
        for rule in viewer_rules:
            formula = rule["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
            assert "$D$4" in formula, f"Missing helper cell ref in: {formula}"

    def test_site_viewer_must_rows_use_red(self):
        """Site Viewer must-field rows should use red background."""
        viewer_rules = _build_site_viewer_requests(sheet_id=5)
        must_rows = {7, 8, 9, 11, 13, 14, 20}
        for rule in viewer_rules:
            row = rule["addConditionalFormatRule"]["rule"]["ranges"][0]["startRowIndex"] + 1
            bg = rule["addConditionalFormatRule"]["rule"]["booleanRule"]["format"]["backgroundColor"]
            if row in must_rows:
                assert bg == COLOR_RED, f"Row {row} should be red"
            else:
                assert bg == COLOR_YELLOW, f"Row {row} should be yellow"
