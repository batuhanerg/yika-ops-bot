"""Tests for Item 3: Field classification config (Session 5).

Validates FIELD_REQUIREMENTS structure and CONTEXT_RULES.
"""

import pytest

from app.field_config.field_requirements import FIELD_REQUIREMENTS, CONTEXT_RULES


class TestFieldRequirementsStructure:
    """Ensure FIELD_REQUIREMENTS has entries for all 5 tabs."""

    def test_has_all_tabs(self):
        expected_tabs = {"sites", "hardware_inventory", "implementation_details", "support_log", "stock"}
        assert set(FIELD_REQUIREMENTS.keys()) == expected_tabs

    def test_each_tab_has_must(self):
        for tab in FIELD_REQUIREMENTS:
            assert "must" in FIELD_REQUIREMENTS[tab], f"{tab} missing 'must' key"


class TestSitesRequirements:
    def test_must_fields(self):
        must = FIELD_REQUIREMENTS["sites"]["must"]
        assert "customer" in must
        assert "city" in must
        assert "country" in must
        assert "facility_type" in must
        assert "contract_status" in must
        assert "supervisor_1" in must
        assert "phone_1" in must

    def test_important_fields(self):
        important = FIELD_REQUIREMENTS["sites"]["important"]
        assert "go_live_date" in important
        assert "address" in important
        assert "dashboard_link" in important
        assert "whatsapp_group" in important

    def test_optional_fields(self):
        optional = FIELD_REQUIREMENTS["sites"]["optional"]
        assert "email_1" in optional
        assert "notes" in optional

    def test_site_id_not_in_must(self):
        """site_id is auto-generated, never ask user for it."""
        must = FIELD_REQUIREMENTS["sites"]["must"]
        assert "site_id" not in must


class TestHardwareRequirements:
    def test_must_fields(self):
        must = FIELD_REQUIREMENTS["hardware_inventory"]["must"]
        assert "site_id" in must
        assert "device_type" in must
        assert "qty" in must

    def test_hw_fw_version_conditional(self):
        cond = FIELD_REQUIREMENTS["hardware_inventory"]["important_conditional"]
        assert "hw_version" in cond
        assert "fw_version" in cond
        # Should have except_device_types for non-electronic accessories
        assert "except_device_types" in cond["hw_version"]
        assert "Charging Dock" in cond["hw_version"]["except_device_types"]
        assert "Power Bank" in cond["hw_version"]["except_device_types"]
        assert "Other" in cond["hw_version"]["except_device_types"]


class TestImplementationRequirements:
    def test_must_fields(self):
        must = FIELD_REQUIREMENTS["implementation_details"]["must"]
        assert "internet_provider" in must
        assert "ssid" in must

    def test_site_id_not_in_must(self):
        """site_id is resolved from context, not listed as must."""
        must = FIELD_REQUIREMENTS["implementation_details"]["must"]
        assert "site_id" not in must

    def test_important_fields(self):
        important = FIELD_REQUIREMENTS["implementation_details"]["important"]
        assert "password" in important
        assert "gateway_placement" in important
        assert "charging_dock_placement" in important
        assert "dispenser_anchor_placement" in important
        assert "handwash_time" in important

    def test_must_when_food(self):
        food = FIELD_REQUIREMENTS["implementation_details"]["must_when_facility_type"]["Food"]
        assert "clean_hygiene_time" in food
        assert "hp_alert_time" in food
        assert "hand_hygiene_time" in food
        assert "hand_hygiene_interval" in food
        assert "hand_hygiene_type" in food

    def test_must_when_healthcare(self):
        hc = FIELD_REQUIREMENTS["implementation_details"]["must_when_facility_type"]["Healthcare"]
        assert "tag_clean_to_red_timeout" in hc


class TestSupportLogRequirements:
    def test_must_fields(self):
        must = FIELD_REQUIREMENTS["support_log"]["must"]
        assert "site_id" in must
        assert "received_date" in must
        assert "type" in must
        assert "status" in must
        assert "issue_summary" in must
        assert "responsible" in must

    def test_root_cause_conditional(self):
        cond = FIELD_REQUIREMENTS["support_log"]["important_conditional"]
        assert "root_cause" in cond
        assert "required_when_status_not" in cond["root_cause"]
        assert "Open" in cond["root_cause"]["required_when_status_not"]

    def test_resolution_conditional(self):
        cond = FIELD_REQUIREMENTS["support_log"]["important_conditional"]
        assert "resolution" in cond
        assert "required_when_status" in cond["resolution"]
        assert "Resolved" in cond["resolution"]["required_when_status"]


class TestStockRequirements:
    def test_must_fields(self):
        must = FIELD_REQUIREMENTS["stock"]["must"]
        assert "location" in must
        assert "device_type" in must
        assert "qty" in must
        assert "condition" in must

    def test_important_fields(self):
        important = FIELD_REQUIREMENTS["stock"]["important"]
        assert "hw_version" in important
        assert "fw_version" in important


class TestContextRules:
    def test_awaiting_installation_skips_tabs(self):
        skip = CONTEXT_RULES["awaiting_installation"]["skip_tabs"]
        assert "implementation_details" in skip
        assert "hardware_inventory" in skip
        assert "support_log" in skip
