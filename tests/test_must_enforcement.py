"""Tests for Item 1: Must-field enforcement independent of Claude.

Validates that FIELD_REQUIREMENTS must fields are always caught,
regardless of what Claude's missing_fields reports.
"""

import pytest

from app.utils.missing_fields import enforce_must_fields


class TestEnforceMustFieldsCreateSite:
    """Ensure FIELD_REQUIREMENTS sites.must fields are enforced."""

    def test_claude_misses_supervisor_and_phone(self):
        """Claude reports ["city"] but supervisor_1 and phone_1 are also empty."""
        data = {
            "customer": "ISS Memorial",
            "city": "",
            "country": "Turkey",
            "facility_type": "Food",
            "contract_status": "Active",
            "supervisor_1": "",
            "phone_1": "",
        }
        claude_missing = ["city"]
        result = enforce_must_fields("create_site", data, claude_missing)
        assert "city" in result
        assert "supervisor_1" in result
        assert "phone_1" in result

    def test_all_must_fields_populated(self):
        """Claude returns [] and all must fields present → no injection."""
        data = {
            "customer": "ISS Memorial",
            "city": "Istanbul",
            "country": "Turkey",
            "facility_type": "Food",
            "contract_status": "Active",
            "supervisor_1": "Ahmet",
            "phone_1": "555-1234",
        }
        claude_missing = []
        result = enforce_must_fields("create_site", data, claude_missing)
        assert len(result) == 0

    def test_important_fields_not_injected(self):
        """Missing important fields (e.g., address) are NOT added to missing list."""
        data = {
            "customer": "ISS Memorial",
            "city": "Istanbul",
            "country": "Turkey",
            "facility_type": "Food",
            "contract_status": "Active",
            "supervisor_1": "Ahmet",
            "phone_1": "555-1234",
            "address": "",  # important, not must
            "dashboard_link": "",  # important, not must
        }
        claude_missing = []
        result = enforce_must_fields("create_site", data, claude_missing)
        assert "address" not in result
        assert "dashboard_link" not in result
        assert len(result) == 0


class TestEnforceMustFieldsFacilityType:
    """Test must_when_facility_type enforcement."""

    def test_food_site_missing_clean_hygiene_time(self):
        """Food site: Claude misses clean_hygiene_time → gets injected."""
        data = {
            "internet_provider": "ERG Controls",
            "ssid": "ERG-Net",
            "clean_hygiene_time": "",
        }
        claude_missing = []
        result = enforce_must_fields(
            "update_implementation", data, claude_missing, facility_type="Food",
        )
        assert "clean_hygiene_time" in result

    def test_healthcare_site_missing_tag_clean_to_red(self):
        """Healthcare site: tag_clean_to_red_timeout missing → gets injected."""
        data = {
            "internet_provider": "ERG Controls",
            "ssid": "ERG-Net",
            "tag_clean_to_red_timeout": "",
        }
        claude_missing = []
        result = enforce_must_fields(
            "update_implementation", data, claude_missing, facility_type="Healthcare",
        )
        assert "tag_clean_to_red_timeout" in result

    def test_food_site_tag_clean_to_red_not_injected(self):
        """Food site: tag_clean_to_red_timeout missing → NOT injected (Healthcare-only)."""
        data = {
            "internet_provider": "ERG Controls",
            "ssid": "ERG-Net",
            "tag_clean_to_red_timeout": "",
        }
        claude_missing = []
        result = enforce_must_fields(
            "update_implementation", data, claude_missing, facility_type="Food",
        )
        assert "tag_clean_to_red_timeout" not in result

    def test_unknown_facility_type_skips_conditional(self):
        """No facility_type: conditional must fields are NOT injected."""
        data = {
            "internet_provider": "ERG Controls",
            "ssid": "ERG-Net",
            "clean_hygiene_time": "",
        }
        claude_missing = []
        result = enforce_must_fields(
            "update_implementation", data, claude_missing, facility_type=None,
        )
        assert "clean_hygiene_time" not in result


class TestEnforceMustFieldsSupportLog:
    """Test support log must field enforcement."""

    def test_support_log_must_fields(self):
        """Missing support log must fields get injected."""
        data = {
            "site_id": "MIG-TR-01",
            "received_date": "2025-01-10",
            "type": "",
            "status": "Open",
            "issue_summary": "",
            "responsible": "",
        }
        claude_missing = ["type"]
        result = enforce_must_fields("log_support", data, claude_missing)
        assert "type" in result
        assert "issue_summary" in result
        assert "responsible" in result


class TestEnforceMustFieldsPreservesClaudeFields:
    """Ensure Claude's original missing_fields are preserved."""

    def test_claude_fields_preserved(self):
        """Fields Claude reported as missing stay in the list."""
        data = {
            "customer": "ISS",
            "city": "",
            "country": "",
            "facility_type": "Food",
            "contract_status": "",
            "supervisor_1": "",
            "phone_1": "",
        }
        claude_missing = ["city", "country"]
        result = enforce_must_fields("create_site", data, claude_missing)
        assert "city" in result
        assert "country" in result
        # Also injected
        assert "contract_status" in result
        assert "supervisor_1" in result
        assert "phone_1" in result

    def test_no_duplicates(self):
        """Fields already in Claude's list are not duplicated."""
        data = {
            "customer": "ISS",
            "city": "",
            "supervisor_1": "",
            "phone_1": "",
        }
        claude_missing = ["city", "supervisor_1"]
        result = enforce_must_fields("create_site", data, claude_missing)
        assert result.count("city") == 1
        assert result.count("supervisor_1") == 1


class TestNoRawFieldNamesInOutput:
    """Verify that format_missing_fields_message never outputs raw field names in Turkish."""

    def test_all_must_fields_have_friendly_names(self):
        """Every must field in FIELD_REQUIREMENTS has a FRIENDLY_FIELD_MAP entry."""
        from app.field_config.field_requirements import FIELD_REQUIREMENTS
        from app.field_config.friendly_fields import FRIENDLY_FIELD_MAP

        for tab, reqs in FIELD_REQUIREMENTS.items():
            for field in reqs.get("must", []):
                assert field in FRIENDLY_FIELD_MAP, (
                    f"Must field '{field}' in {tab} has no friendly mapping — "
                    f"would show raw name in Slack"
                )

    def test_all_important_fields_have_friendly_names(self):
        """Every important field has a FRIENDLY_FIELD_MAP entry."""
        from app.field_config.field_requirements import FIELD_REQUIREMENTS
        from app.field_config.friendly_fields import FRIENDLY_FIELD_MAP

        for tab, reqs in FIELD_REQUIREMENTS.items():
            for field in reqs.get("important", []):
                assert field in FRIENDLY_FIELD_MAP, (
                    f"Important field '{field}' in {tab} has no friendly mapping — "
                    f"would show raw name in Slack"
                )

    def test_turkish_output_contains_no_snake_case(self):
        """Turkish missing fields message should not contain snake_case field names."""
        from app.utils.missing_fields import format_missing_fields_message

        # Test with all sites must fields missing
        msg, _ = format_missing_fields_message(
            ["customer", "city", "country", "facility_type",
             "contract_status", "supervisor_1", "phone_1"],
            "create_site", language="tr",
        )
        # None of these raw names should appear
        assert "customer" not in msg.lower() or "müşteri" in msg.lower()
        assert "supervisor_1" not in msg
        assert "phone_1" not in msg
        assert "contract_status" not in msg
        assert "facility_type" not in msg
