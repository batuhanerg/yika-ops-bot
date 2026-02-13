"""Tests for field validation logic."""

from datetime import date, timedelta
import pytest

from app.utils.validators import (
    validate_site_id_format,
    validate_date_not_future,
    validate_date_not_too_old,
    validate_resolved_after_received,
    validate_required_fields,
    validate_dropdown_value,
    validate_positive_integer,
)


# --- Site ID format (XXX-CC-NN) ---

class TestSiteIdFormat:
    def test_valid_standard(self):
        assert validate_site_id_format("ASM-TR-01") is True

    def test_valid_two_letter_prefix(self):
        assert validate_site_id_format("MG-TR-01") is True

    def test_valid_four_letter_prefix(self):
        assert validate_site_id_format("ABCD-EG-02") is True

    def test_invalid_no_dashes(self):
        assert validate_site_id_format("ASMTR01") is False

    def test_invalid_lowercase(self):
        assert validate_site_id_format("asm-tr-01") is False

    def test_invalid_empty(self):
        assert validate_site_id_format("") is False

    def test_invalid_wrong_country_length(self):
        assert validate_site_id_format("ASM-TUR-01") is False

    def test_invalid_single_digit(self):
        assert validate_site_id_format("ASM-TR-1") is False


# --- Future date rejection ---

class TestFutureDateRejection:
    def test_today_is_allowed(self):
        result = validate_date_not_future(date.today())
        assert result.valid is True

    def test_past_date_is_allowed(self):
        result = validate_date_not_future(date.today() - timedelta(days=5))
        assert result.valid is True

    def test_future_date_is_rejected(self):
        result = validate_date_not_future(date.today() + timedelta(days=1))
        assert result.valid is False
        assert "future" in result.message.lower() or "gelecek" in result.message.lower()


# --- Old date warning (>90 days) ---

class TestOldDateWarning:
    def test_recent_date_no_warning(self):
        result = validate_date_not_too_old(date.today() - timedelta(days=10))
        assert result.warning is False

    def test_old_date_warning(self):
        result = validate_date_not_too_old(date.today() - timedelta(days=91))
        assert result.warning is True
        assert "90" in result.message


# --- Resolved date >= Received date ---

class TestResolvedAfterReceived:
    def test_same_day_is_valid(self):
        d = date.today()
        result = validate_resolved_after_received(received=d, resolved=d)
        assert result.valid is True

    def test_resolved_after_received_is_valid(self):
        received = date(2025, 1, 1)
        resolved = date(2025, 1, 5)
        result = validate_resolved_after_received(received=received, resolved=resolved)
        assert result.valid is True

    def test_resolved_before_received_is_invalid(self):
        received = date(2025, 1, 10)
        resolved = date(2025, 1, 5)
        result = validate_resolved_after_received(received=received, resolved=resolved)
        assert result.valid is False


# --- Required fields per operation type ---

class TestRequiredFields:
    def test_support_log_all_present(self):
        data = {
            "site_id": "ASM-TR-01",
            "received_date": "2025-01-15",
            "type": "Visit",
            "status": "Resolved",
            "root_cause": "HW Fault (Production)",
            "issue_summary": "Tag replacement",
            "responsible": "Gökhan",
            "resolved_date": "2025-01-15",
            "resolution": "Tags replaced",
        }
        missing = validate_required_fields("log_support", data)
        assert missing == []

    def test_support_log_missing_fields(self):
        data = {
            "site_id": "ASM-TR-01",
            "type": "Visit",
        }
        missing = validate_required_fields("log_support", data)
        assert "received_date" in missing
        assert "status" in missing
        assert "issue_summary" in missing
        assert "responsible" in missing
        # root_cause is NOT in base required fields — it's conditional on status

    def test_support_log_open_no_root_cause_required(self):
        data = {
            "site_id": "ASM-TR-01",
            "received_date": "2025-01-15",
            "type": "Call",
            "status": "Open",
            "issue_summary": "Tag data issue",
            "responsible": "Batu",
        }
        missing = validate_required_fields("log_support", data)
        assert missing == []  # root_cause not required for Open

    def test_support_log_non_open_requires_root_cause(self):
        data = {
            "site_id": "ASM-TR-01",
            "received_date": "2025-01-15",
            "type": "Visit",
            "status": "Follow-up (ERG)",
            "issue_summary": "Tag replacement",
            "responsible": "Gökhan",
        }
        missing = validate_required_fields("log_support", data)
        assert "root_cause" in missing

    def test_support_log_resolved_requires_resolution(self):
        data = {
            "site_id": "ASM-TR-01",
            "received_date": "2025-01-15",
            "type": "Visit",
            "status": "Resolved",
            "issue_summary": "Tag replacement",
            "responsible": "Gökhan",
            "resolved_date": "2025-01-15",
            # resolution and root_cause missing
        }
        missing = validate_required_fields("log_support", data)
        assert "resolution" in missing
        assert "root_cause" in missing

    def test_create_site_missing_fields(self):
        data = {"customer": "Test Corp"}
        missing = validate_required_fields("create_site", data)
        assert "city" in missing
        assert "country" in missing
        assert "facility_type" in missing

    def test_create_site_go_live_date_not_required(self):
        """go_live_date is important, not must — should not be in REQUIRED_FIELDS."""
        data = {
            "customer": "Test Corp", "city": "Istanbul", "country": "Turkey",
            "facility_type": "Food", "contract_status": "Active",
            "supervisor_1": "Ahmet", "phone_1": "555",
        }
        missing = validate_required_fields("create_site", data)
        assert "go_live_date" not in missing

    def test_create_site_supervisor_phone_required(self):
        """supervisor_1 and phone_1 are must fields for create_site."""
        data = {
            "customer": "Test Corp", "city": "Istanbul", "country": "Turkey",
            "facility_type": "Food", "contract_status": "Active",
        }
        missing = validate_required_fields("create_site", data)
        assert "supervisor_1" in missing
        assert "phone_1" in missing


# --- Dropdown validation ---

class TestDropdownValidation:
    def test_valid_support_type(self):
        assert validate_dropdown_value("support_type", "Visit") is True

    def test_valid_support_status(self):
        assert validate_dropdown_value("support_status", "Resolved") is True

    def test_valid_root_cause(self):
        assert validate_dropdown_value("root_cause", "HW Fault (Production)") is True

    def test_valid_facility_type(self):
        assert validate_dropdown_value("facility_type", "Food") is True

    def test_valid_device_type(self):
        assert validate_dropdown_value("device_type", "Tag") is True

    def test_valid_contract_status_awaiting_installation(self):
        assert validate_dropdown_value("contract_status", "Awaiting Installation") is True

    def test_invalid_contract_status_pending(self):
        """'Pending' was renamed to 'Awaiting Installation'."""
        assert validate_dropdown_value("contract_status", "Pending") is False

    def test_valid_internet_provider(self):
        assert validate_dropdown_value("internet_provider", "ERG Controls") is True

    def test_invalid_value(self):
        assert validate_dropdown_value("support_type", "Teleport") is False

    def test_invalid_field_name(self):
        assert validate_dropdown_value("nonexistent_field", "anything") is False


# --- Positive integer ---

class TestPositiveInteger:
    def test_valid_positive(self):
        assert validate_positive_integer(5) is True

    def test_zero_is_invalid(self):
        assert validate_positive_integer(0) is False

    def test_negative_is_invalid(self):
        assert validate_positive_integer(-3) is False

    def test_none_is_invalid(self):
        assert validate_positive_integer(None) is False
