"""Tests for conditional formatting migration script (Session 6, Item 7).

Applies color-coded conditional formatting rules across all tabs:
- Red (#FFEBEE): empty must-field cells
- Yellow (#FFF9C4): empty important-field cells
- Blue (#E3F2FD): Last Verified > 30 days
- Orange (#FFF3E0): open support tickets with Received Date > 3 days

Context-aware: skips formatting for "Awaiting Installation" sites.
Idempotent: clears existing rules before applying.
Supports --dry-run flag.
"""

from unittest.mock import MagicMock, patch, call

from scripts.migrate_conditional_formatting import (
    build_formatting_rules,
    migrate,
    _build_site_viewer_requests,
    _build_site_viewer_data_requests,
    _build_device_type_version_requests,
    _build_facility_type_conditional_requests,
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
                    "Qty", "Last Verified", "Notes", "_ContractStatus",
                ]
            elif name == "Support Log":
                ws.row_values.return_value = [
                    "Ticket ID", "Site ID", "Received Date", "Resolved Date",
                    "Type", "Status", "Root Cause", "Reported By",
                    "Issue Summary", "Resolution", "Devices Affected",
                    "Responsible", "Notes", "_ContractStatus",
                ]
            elif name == "Stock":
                ws.row_values.return_value = [
                    "Location", "Device Type", "HW Version", "FW Version",
                    "Qty", "Condition", "Reserved For", "Notes", "Last Verified",
                ]
            elif name == "Implementation Details":
                ws.row_values.return_value = [
                    "Site ID", "Internet Provider", "SSID", "Password",
                    "Gateway Placement", "Charging Dock Placement",
                    "Last Verified", "_FacilityType", "_ContractStatus",
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

    def test_device_type_version_rules_for_tag_anchor_gateway(self):
        """HW/FW Version should be yellow when Device Type is Tag, Anchor, or Gateway."""
        headers = ["Site ID", "Device Type", "HW Version", "FW Version", "Qty", "Last Verified", "Notes"]
        rules = _build_device_type_version_requests(sheet_id=1, headers=headers, header_row=1)
        assert len(rules) == 2, f"Expected 2 rules (HW + FW), got {len(rules)}"
        for rule in rules:
            formula = rule["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
            assert "Tag" in formula, f"Formula should check for Tag: {formula}"
            assert "Anchor" in formula, f"Formula should check for Anchor: {formula}"
            assert "Gateway" in formula, f"Formula should check for Gateway: {formula}"
            bg = rule["addConditionalFormatRule"]["rule"]["booleanRule"]["format"]["backgroundColor"]
            assert bg == COLOR_YELLOW, "Device type version rules should be yellow"

    def test_device_type_version_rules_in_migrate(self):
        """migrate() should include Tag/Anchor version rules."""
        spreadsheet = self._make_spreadsheet()

        migrate(spreadsheet)

        all_calls = spreadsheet.batch_update.call_args_list
        all_requests = []
        for c in all_calls:
            body = c[0][0] if c[0] else c[1].get("body", {})
            all_requests.extend(body.get("requests", []))

        add_rules = [r for r in all_requests if "addConditionalFormatRule" in r]
        # Find Hardware Inventory rules (sheet_id=1) with Tag/Anchor in formula
        tag_rules = [
            r for r in add_rules
            if r["addConditionalFormatRule"]["rule"]["ranges"][0]["sheetId"] == 1
            and "Tag" in r["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
        ]
        assert len(tag_rules) == 2, f"Expected 2 Tag/Anchor version rules, got {len(tag_rules)}"

    def test_facility_type_conditional_rules(self):
        """Food/Healthcare-specific fields should get yellow formatting."""
        impl_headers = [
            "Site ID", "Internet Provider", "SSID", "Password",
            "Gateway Placement", "Charging Dock Placement",
            "Clean Hygiene Time", "HP Alert Time", "Hand Hygiene Time",
            "Hand Hygiene Interval", "Hand Hygiene Type", "Tag Clean to Red Timeout",
            "_FacilityType",
        ]
        # _FacilityType helper column is at index 12
        rules = _build_facility_type_conditional_requests(
            sheet_id=2, impl_headers=impl_headers,
            facility_type_col_idx=12, header_row=2,
        )
        # Food has 5 fields, Healthcare has 1 = 6 total
        assert len(rules) == 6, f"Expected 6 facility-type rules, got {len(rules)}"
        for rule in rules:
            formula = rule["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
            # Should reference the local helper column (M), not cross-sheet VLOOKUP
            assert "$M" in formula, f"Should reference helper column $M: {formula}"
            assert "VLOOKUP" not in formula, f"Should NOT use VLOOKUP in formula: {formula}"
            bg = rule["addConditionalFormatRule"]["rule"]["booleanRule"]["format"]["backgroundColor"]
            assert bg == COLOR_RED, "Facility-type rules should be red (must_when_facility_type = must)"

    def test_facility_type_food_checks_correct_type(self):
        """Food rules should check for 'Food' facility type."""
        impl_headers = [
            "Site ID", "Internet Provider", "SSID", "Clean Hygiene Time",
            "_FacilityType",
        ]
        # _FacilityType is at index 4
        rules = _build_facility_type_conditional_requests(
            sheet_id=2, impl_headers=impl_headers,
            facility_type_col_idx=4, header_row=2,
        )
        food_rules = [
            r for r in rules
            if '"Food"' in r["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
        ]
        assert len(food_rules) > 0, "Should have Food-specific rules"

    def test_stale_verified_includes_empty_cells(self):
        """Last Verified rule should highlight empty cells (not just old dates)."""
        spreadsheet = self._make_spreadsheet()

        migrate(spreadsheet)

        all_calls = spreadsheet.batch_update.call_args_list
        all_requests = []
        for c in all_calls:
            body = c[0][0] if c[0] else c[1].get("body", {})
            all_requests.extend(body.get("requests", []))

        add_rules = [r for r in all_requests if "addConditionalFormatRule" in r]
        # Find blue rules for Hardware Inventory (sheet_id=1)
        blue_rules = [
            r for r in add_rules
            if r["addConditionalFormatRule"]["rule"]["ranges"][0]["sheetId"] == 1
            and r["addConditionalFormatRule"]["rule"]["booleanRule"]["format"]["backgroundColor"] == COLOR_BLUE
        ]
        assert len(blue_rules) > 0, "Should have stale_verified blue rule"
        formula = blue_rules[0]["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
        # The formula should NOT require the cell to be non-empty
        assert '<>""' not in formula or formula.count('<>""') == 1, (
            f"Stale verified formula should not exclude empty cells: {formula}"
        )

    def test_build_rules_includes_device_type_conditional(self):
        """build_formatting_rules should include device_type_conditional entries (yellow)."""
        rules = build_formatting_rules()
        dt_rules = [r for r in rules if r["severity"] == "device_type_conditional"]
        assert len(dt_rules) == 2
        fields = {r["field"] for r in dt_rules}
        assert "HW Version" in fields
        assert "FW Version" in fields
        for r in dt_rules:
            assert r["color"] == COLOR_YELLOW

    def test_build_rules_includes_facility_type(self):
        """build_formatting_rules should include facility-type entries."""
        rules = build_formatting_rules()
        food_rules = [r for r in rules if r["severity"] == "facility_food"]
        healthcare_rules = [r for r in rules if r["severity"] == "facility_healthcare"]
        assert len(food_rules) == 5
        assert len(healthcare_rules) == 1


class TestSiteViewerDataRequests:
    """Tests for _build_site_viewer_data_requests."""

    def _make_viewer_content(self) -> list[list[str]]:
        """Build realistic Site Viewer content."""
        content = [[""] for _ in range(80)]
        # Hardware section
        content[22] = ["", "🔧 HARDWARE INVENTORY"]
        content[23] = ["", "Device Type", "HW Version", "FW Version", "Qty", "Last Verified", "Notes"]
        content[24] = ["", "Tag", "v3.6", "v1.1", "10", "2026-01-01"]
        # Implementation Details section
        content[40] = ["", "⚙️ IMPLEMENTATION DETAILS"]
        content[41] = ["", "Parameter", "Value"]
        content[42] = ["", "Internet Provider", "ERG Controls"]
        content[43] = ["", "SSID", "test-wifi"]
        content[44] = ["", "Password", "secret"]
        content[45] = ["", "Gateway placement", ""]
        # Support Log section
        content[61] = ["", "📞 SUPPORT LOG"]
        content[62] = ["", "Ticket ID", "Site ID", "Received Date"]
        content[63] = ["", "SUP-001", "ASM-TR-01", "2026-02-01"]
        return content

    def test_builds_impl_details_rules(self):
        """Should build rules for Implementation Details parameter values."""
        content = self._make_viewer_content()
        rules = _build_site_viewer_data_requests(sheet_id=5, viewer_content=content)

        impl_rules = [
            r for r in rules
            if r["addConditionalFormatRule"]["rule"]["ranges"][0]["startColumnIndex"] == 2  # column C
            and r["addConditionalFormatRule"]["rule"]["ranges"][0]["startRowIndex"] >= 42
        ]
        # Should have rules for must (Internet Provider, SSID) and important (Password, Gateway placement)
        assert len(impl_rules) >= 2, f"Expected impl detail rules, got {len(impl_rules)}"

    def test_builds_support_log_rules(self):
        """Should build rules for Support Log must fields."""
        content = self._make_viewer_content()
        rules = _build_site_viewer_data_requests(sheet_id=5, viewer_content=content)

        sl_rules = [
            r for r in rules
            if r["addConditionalFormatRule"]["rule"]["ranges"][0]["startRowIndex"] >= 63
            and r["addConditionalFormatRule"]["rule"]["ranges"][0]["startColumnIndex"] >= 2
        ]
        # Should have 6 must field rules for support log
        assert len(sl_rules) == 6, f"Expected 6 support log must rules, got {len(sl_rules)}"

    def test_builds_hardware_rules(self):
        """Should build rules for Hardware Inventory (must + version + stale)."""
        content = self._make_viewer_content()
        rules = _build_site_viewer_data_requests(sheet_id=5, viewer_content=content)

        hw_rules = [
            r for r in rules
            if r["addConditionalFormatRule"]["rule"]["ranges"][0]["startRowIndex"] == 24  # row 25
        ]
        # Must(2) + Version Tag/Anchor(2) + Last Verified stale(1) = 5
        assert len(hw_rules) == 5, f"Expected 5 hardware rules, got {len(hw_rules)}"

    def test_all_rules_use_helper_ref_guard(self):
        """All Site Viewer data rules should check $D$4 (site selected)."""
        content = self._make_viewer_content()
        rules = _build_site_viewer_data_requests(sheet_id=5, viewer_content=content)

        for rule in rules:
            formula = rule["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
            assert "$D$4" in formula, f"Missing $D$4 guard in: {formula}"

    def test_hw_version_rules_use_yellow(self):
        """Site Viewer HW/FW version rules should use yellow (not red)."""
        content = self._make_viewer_content()
        rules = _build_site_viewer_data_requests(sheet_id=5, viewer_content=content)

        # HW version rules are at startRowIndex 24, columns 2-3 (C,D)
        version_rules = [
            r for r in rules
            if r["addConditionalFormatRule"]["rule"]["ranges"][0]["startRowIndex"] == 24
            and r["addConditionalFormatRule"]["rule"]["ranges"][0]["startColumnIndex"] in (2, 3)
            and "Tag" in r["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
        ]
        assert len(version_rules) == 2
        for rule in version_rules:
            bg = rule["addConditionalFormatRule"]["rule"]["booleanRule"]["format"]["backgroundColor"]
            assert bg == COLOR_YELLOW, f"HW version rules should be yellow, got {bg}"

    def test_hw_version_rules_check_gateway(self):
        """Site Viewer HW/FW version rules should include Gateway."""
        content = self._make_viewer_content()
        rules = _build_site_viewer_data_requests(sheet_id=5, viewer_content=content)

        version_rules = [
            r for r in rules
            if r["addConditionalFormatRule"]["rule"]["ranges"][0]["startRowIndex"] == 24
            and "Tag" in r["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
        ]
        for rule in version_rules:
            formula = rule["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
            assert "Gateway" in formula, f"Formula should check for Gateway: {formula}"


class TestStaleVerifiedThreeTabs:
    """Stale verified (blue) rules should cover HW, Impl, and Stock."""

    def test_build_rules_three_tabs(self):
        rules = build_formatting_rules()
        stale_rules = [r for r in rules if r["severity"] == "stale_verified"]
        tabs = {r["tab"] for r in stale_rules}
        assert tabs == {"Hardware Inventory", "Implementation Details", "Stock"}

    def test_migrate_generates_blue_for_all_three(self):
        """migrate() should produce blue rules for HW, Impl, and Stock."""
        spreadsheet = TestMigrate()._make_spreadsheet()
        migrate(spreadsheet)
        all_requests = _extract_add_rules(spreadsheet)
        # HW=1, Impl=2, Stock=4
        for sheet_id, tab_name in [(1, "HW"), (2, "Impl"), (4, "Stock")]:
            blue_rules = [
                r for r in all_requests
                if r["addConditionalFormatRule"]["rule"]["ranges"][0]["sheetId"] == sheet_id
                and r["addConditionalFormatRule"]["rule"]["booleanRule"]["format"]["backgroundColor"] == COLOR_BLUE
            ]
            assert len(blue_rules) > 0, f"No blue stale_verified rule for {tab_name} (sheet_id={sheet_id})"

    def test_hw_stale_verified_has_ai_guard(self):
        """HW stale_verified formula should guard against 'Awaiting Installation'."""
        spreadsheet = TestMigrate()._make_spreadsheet()
        migrate(spreadsheet)
        all_requests = _extract_add_rules(spreadsheet)
        blue_hw = [
            r for r in all_requests
            if r["addConditionalFormatRule"]["rule"]["ranges"][0]["sheetId"] == 1
            and r["addConditionalFormatRule"]["rule"]["booleanRule"]["format"]["backgroundColor"] == COLOR_BLUE
        ]
        assert len(blue_hw) > 0
        formula = blue_hw[0]["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
        assert "Awaiting Installation" in formula, f"HW stale formula should have AI guard: {formula}"

    def test_stock_stale_verified_no_ai_guard(self):
        """Stock stale_verified formula should NOT have AI guard (not site-specific)."""
        spreadsheet = TestMigrate()._make_spreadsheet()
        migrate(spreadsheet)
        all_requests = _extract_add_rules(spreadsheet)
        blue_stock = [
            r for r in all_requests
            if r["addConditionalFormatRule"]["rule"]["ranges"][0]["sheetId"] == 4
            and r["addConditionalFormatRule"]["rule"]["booleanRule"]["format"]["backgroundColor"] == COLOR_BLUE
        ]
        assert len(blue_stock) > 0
        formula = blue_stock[0]["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
        assert "Awaiting Installation" not in formula, f"Stock stale formula should NOT have AI guard: {formula}"


class TestStaleTicket:
    """Support Log stale ticket: 3-day threshold, full row A:M."""

    def test_formula_uses_3_day_threshold(self):
        spreadsheet = TestMigrate()._make_spreadsheet()
        migrate(spreadsheet)
        all_requests = _extract_add_rules(spreadsheet)
        orange_rules = [
            r for r in all_requests
            if r["addConditionalFormatRule"]["rule"]["ranges"][0]["sheetId"] == 3
            and r["addConditionalFormatRule"]["rule"]["booleanRule"]["format"]["backgroundColor"] == COLOR_ORANGE
        ]
        assert len(orange_rules) > 0
        formula = orange_rules[0]["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
        assert ">3" in formula, f"Formula should use 3-day threshold: {formula}"
        assert ">7" not in formula, f"Formula should NOT use 7-day threshold: {formula}"

    def test_covers_full_row(self):
        """Orange rule should span columns A through M (0-12)."""
        spreadsheet = TestMigrate()._make_spreadsheet()
        migrate(spreadsheet)
        all_requests = _extract_add_rules(spreadsheet)
        orange_rules = [
            r for r in all_requests
            if r["addConditionalFormatRule"]["rule"]["ranges"][0]["sheetId"] == 3
            and r["addConditionalFormatRule"]["rule"]["booleanRule"]["format"]["backgroundColor"] == COLOR_ORANGE
        ]
        assert len(orange_rules) > 0
        range_ = orange_rules[0]["addConditionalFormatRule"]["rule"]["ranges"][0]
        assert range_["startColumnIndex"] == 0, "Orange rule should start at column A"
        assert range_.get("endColumnIndex", 0) >= 13, "Orange rule should cover through column M"


class TestSLConditionalRules:
    """Support Log conditional rules for root_cause, resolution, resolved_date."""

    def test_build_rules_includes_sl_conditional(self):
        rules = build_formatting_rules()
        sl_cond = [r for r in rules if r["severity"].startswith("sl_conditional")]
        assert len(sl_cond) == 3
        fields = {r["field"] for r in sl_cond}
        assert "Root Cause" in fields
        assert "Resolution" in fields
        assert "Resolved Date" in fields

    def test_sl_conditional_uses_red(self):
        rules = build_formatting_rules()
        sl_cond = [r for r in rules if r["severity"].startswith("sl_conditional")]
        for r in sl_cond:
            assert r["color"] == COLOR_RED

    def test_root_cause_formula_checks_status_not_open(self):
        """Root cause RED rule should check that status is NOT 'Open'."""
        spreadsheet = TestMigrate()._make_spreadsheet()
        migrate(spreadsheet)
        all_requests = _extract_add_rules(spreadsheet)
        # Root Cause is at index 6 in SL headers
        rc_rules = [
            r for r in all_requests
            if r["addConditionalFormatRule"]["rule"]["ranges"][0]["sheetId"] == 3
            and r["addConditionalFormatRule"]["rule"]["ranges"][0]["startColumnIndex"] == 6
            and r["addConditionalFormatRule"]["rule"]["booleanRule"]["format"]["backgroundColor"] == COLOR_RED
        ]
        # Filter for conditional formula (not just blank check)
        rc_cond = [
            r for r in rc_rules
            if "Open" in r["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
        ]
        assert len(rc_cond) == 1, f"Expected 1 root_cause conditional rule, got {len(rc_cond)}"

    def test_resolution_formula_checks_resolved(self):
        """Resolution RED rule should check that status IS 'Resolved'."""
        spreadsheet = TestMigrate()._make_spreadsheet()
        migrate(spreadsheet)
        all_requests = _extract_add_rules(spreadsheet)
        # Resolution is at index 9 in SL headers
        res_rules = [
            r for r in all_requests
            if r["addConditionalFormatRule"]["rule"]["ranges"][0]["sheetId"] == 3
            and r["addConditionalFormatRule"]["rule"]["ranges"][0]["startColumnIndex"] == 9
            and r["addConditionalFormatRule"]["rule"]["booleanRule"]["format"]["backgroundColor"] == COLOR_RED
        ]
        res_cond = [
            r for r in res_rules
            if "Resolved" in r["addConditionalFormatRule"]["rule"]["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
        ]
        assert len(res_cond) == 1, f"Expected 1 resolution conditional rule, got {len(res_cond)}"


class TestDevicesAffectedImportant:
    """devices_affected should get a YELLOW blank rule (always_important)."""

    def test_build_rules_includes_devices_affected(self):
        rules = build_formatting_rules()
        da_rules = [
            r for r in rules
            if r["field"] == "Devices Affected" and r["tab"] == "Support Log"
        ]
        assert len(da_rules) == 1
        assert da_rules[0]["color"] == COLOR_YELLOW
        assert da_rules[0]["severity"] == "important"


def _extract_add_rules(spreadsheet) -> list[dict]:
    """Extract all addConditionalFormatRule requests from batch_update calls."""
    all_calls = spreadsheet.batch_update.call_args_list
    all_requests = []
    for c in all_calls:
        body = c[0][0] if c[0] else c[1].get("body", {})
        all_requests.extend(body.get("requests", []))
    return [r for r in all_requests if "addConditionalFormatRule" in r]
