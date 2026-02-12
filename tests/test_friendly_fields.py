"""Tests for Item 6: Friendly missing fields messages (Session 5).

Validates FRIENDLY_FIELD_MAP and format_missing_fields_message().
"""

import pytest

from app.field_config.friendly_fields import FRIENDLY_FIELD_MAP
from app.utils.missing_fields import format_missing_fields_message


class TestFriendlyFieldMap:
    """Ensure FRIENDLY_FIELD_MAP covers key fields with Turkish questions."""

    def test_responsible_mapped(self):
        assert FRIENDLY_FIELD_MAP["responsible"] == "Bu konuyla kim ilgileniyor?"

    def test_site_id_mapped(self):
        assert FRIENDLY_FIELD_MAP["site_id"] == "Hangi müşteri/saha için?"

    def test_customer_mapped(self):
        assert FRIENDLY_FIELD_MAP["customer"] == "Müşterinin adı ne?"

    def test_device_type_mapped(self):
        assert FRIENDLY_FIELD_MAP["device_type"] == "Hangi cihaz türü?"

    def test_internet_provider_mapped(self):
        assert "internet_provider" in FRIENDLY_FIELD_MAP

    def test_new_implementation_fields_mapped(self):
        """All 6 new implementation columns have friendly mappings."""
        for field in [
            "dispenser_anchor_placement", "clean_hygiene_time", "hp_alert_time",
            "hand_hygiene_time", "hand_hygiene_interval", "hand_hygiene_type",
        ]:
            assert field in FRIENDLY_FIELD_MAP, f"Missing mapping for '{field}'"

    def test_all_must_fields_covered(self):
        """Every must field in FIELD_REQUIREMENTS has a friendly mapping."""
        from app.field_config.field_requirements import FIELD_REQUIREMENTS

        for tab, reqs in FIELD_REQUIREMENTS.items():
            for field in reqs.get("must", []):
                assert field in FRIENDLY_FIELD_MAP, (
                    f"Must field '{field}' in {tab} has no friendly mapping"
                )

    def test_all_facility_type_must_fields_covered(self):
        """Every must_when_facility_type field has a friendly mapping."""
        from app.field_config.field_requirements import FIELD_REQUIREMENTS

        for tab, reqs in FIELD_REQUIREMENTS.items():
            for ftype, fields in reqs.get("must_when_facility_type", {}).items():
                for field in fields:
                    assert field in FRIENDLY_FIELD_MAP, (
                        f"Facility-type must field '{field}' ({ftype}) in {tab} has no friendly mapping"
                    )


class TestFormatMissingFieldsTurkish:
    """Turkish language formatting of missing fields messages."""

    def test_must_fields_header(self):
        msg, _ = format_missing_fields_message(
            ["site_id", "received_date"], "log_support", language="tr",
        )
        assert "Kaydı oluşturabilmem için şu bilgiler gerekli:" in msg

    def test_must_fields_show_friendly_questions(self):
        msg, _ = format_missing_fields_message(
            ["responsible"], "log_support", language="tr",
        )
        assert "Bu konuyla kim ilgileniyor?" in msg

    def test_important_fields_header(self):
        msg, _ = format_missing_fields_message(
            ["devices_affected"], "log_support", language="tr",
        )
        assert "Kaydı zenginleştirmek için şunlar da faydalı olur:" in msg

    def test_must_fields_block(self):
        """has_blockers is True when must fields are missing."""
        _, has_blockers = format_missing_fields_message(
            ["site_id", "received_date"], "log_support", language="tr",
        )
        assert has_blockers is True

    def test_important_only_no_block(self):
        """has_blockers is False when only important fields are missing."""
        _, has_blockers = format_missing_fields_message(
            ["devices_affected"], "log_support", language="tr",
        )
        assert has_blockers is False

    def test_mixed_must_and_important(self):
        """Message shows both sections when both types are missing."""
        msg, has_blockers = format_missing_fields_message(
            ["site_id", "devices_affected"], "log_support", language="tr",
        )
        assert "Kaydı oluşturabilmem için şu bilgiler gerekli:" in msg
        assert "Kaydı zenginleştirmek için şunlar da faydalı olur:" in msg
        assert has_blockers is True

    def test_unknown_field_treated_as_must(self):
        """Fields not in FIELD_REQUIREMENTS default to must."""
        msg, has_blockers = format_missing_fields_message(
            ["some_unknown_field"], "log_support", language="tr",
        )
        assert has_blockers is True


class TestFacilityTypeClassification:
    """Test facility-type aware classification in missing fields."""

    def test_food_field_is_must_when_food(self):
        """clean_hygiene_time is must for Food facility."""
        _, has_blockers = format_missing_fields_message(
            ["clean_hygiene_time"], "update_implementation",
            language="tr", facility_type="Food",
        )
        assert has_blockers is True

    def test_food_field_is_important_when_healthcare(self):
        """clean_hygiene_time is important (not must) for Healthcare facility."""
        _, has_blockers = format_missing_fields_message(
            ["clean_hygiene_time"], "update_implementation",
            language="tr", facility_type="Healthcare",
        )
        assert has_blockers is False

    def test_healthcare_field_is_must_when_healthcare(self):
        """tag_clean_to_red_timeout is must for Healthcare facility."""
        _, has_blockers = format_missing_fields_message(
            ["tag_clean_to_red_timeout"], "update_implementation",
            language="tr", facility_type="Healthcare",
        )
        assert has_blockers is True

    def test_facility_field_important_when_unknown(self):
        """Facility-type fields default to important when facility_type is None."""
        _, has_blockers = format_missing_fields_message(
            ["clean_hygiene_time"], "update_implementation",
            language="tr", facility_type=None,
        )
        assert has_blockers is False


class TestFormatMissingFieldsEnglish:
    """English fallback formatting."""

    def test_english_required_info(self):
        msg, _ = format_missing_fields_message(
            ["site_id"], "log_support", language="en",
        )
        assert "Required information:" in msg
        assert "`site_id`" in msg

    def test_english_optional_info(self):
        msg, _ = format_missing_fields_message(
            ["devices_affected"], "log_support", language="en",
        )
        assert "Optional but helpful:" in msg
