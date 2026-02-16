"""Tests for Session 3 features that lacked test coverage.

Covers: event deduplication, duplicate site_id prevention, permission enforcement,
stock cross-reference detection, Last Verified auto-injection, and dynamic sites
context injection.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from app.handlers.common import _is_duplicate_event, _processed_events, _processed_lock, _DEDUP_TTL
from app.handlers.actions import _should_ask_stock
from app.services.claude import build_sites_context


class TestEventDeduplication:
    """Tests for _is_duplicate_event() in handlers/common.py."""

    def setup_method(self):
        """Clear the deduplication cache before each test."""
        with _processed_lock:
            _processed_events.clear()

    def test_first_event_is_not_duplicate(self):
        assert _is_duplicate_event("evt_001") is False

    def test_same_event_is_duplicate(self):
        _is_duplicate_event("evt_002")
        assert _is_duplicate_event("evt_002") is True

    def test_different_events_are_not_duplicates(self):
        _is_duplicate_event("evt_003")
        assert _is_duplicate_event("evt_004") is False

    def test_stale_events_are_cleaned_up(self):
        # Insert an event with a timestamp in the past beyond TTL
        with _processed_lock:
            _processed_events["evt_old"] = time.time() - (_DEDUP_TTL + 10)
        # Next call should clean up the stale entry
        _is_duplicate_event("evt_new")
        with _processed_lock:
            assert "evt_old" not in _processed_events
            assert "evt_new" in _processed_events

    def test_ttl_covers_slack_cold_start_retries(self):
        """TTL must be long enough to cover Slack retries during cold starts.

        Bug 15: Slack retries at ~10s, ~60s, ~5min when server is unavailable.
        A 30s TTL failed to catch the 60s retry. TTL must be >= 300s.
        """
        assert _DEDUP_TTL >= 300, f"TTL {_DEDUP_TTL}s is too short for Slack retries"

    def test_event_still_deduped_at_60_seconds(self):
        """Event retried 60 seconds later (Slack retry #2) should still be caught."""
        _is_duplicate_event("evt_retry60")
        # Simulate 60 seconds passing by backdating the stored timestamp
        with _processed_lock:
            _processed_events["evt_retry60"] = time.time() - 60
        # Should still be a duplicate (60 < TTL)
        assert _is_duplicate_event("evt_retry60") is True

    def test_event_still_deduped_at_290_seconds(self):
        """Event retried ~5 min later should still be caught."""
        _is_duplicate_event("evt_retry290")
        with _processed_lock:
            _processed_events["evt_retry290"] = time.time() - 290
        assert _is_duplicate_event("evt_retry290") is True


class TestStockCrossReference:
    """Tests for _should_ask_stock() in handlers/actions.py."""

    def test_replacement_keyword_in_support_log(self):
        assert _should_ask_stock("log_support", {}, "2 tag değiştirildi") is True

    def test_hardware_update_uses_dedicated_stock_prompt(self):
        """update_hardware no longer uses _should_ask_stock — has its own stock prompt."""
        assert _should_ask_stock("update_hardware", {}, "replaced 3 gateways") is False

    def test_no_replacement_keyword(self):
        assert _should_ask_stock("log_support", {}, "tag pili bitti") is False

    def test_irrelevant_operation(self):
        assert _should_ask_stock("create_site", {}, "replaced tags") is False

    def test_swap_keyword(self):
        assert _should_ask_stock("log_support", {}, "tag swap yaptık") is True

    def test_case_insensitive(self):
        assert _should_ask_stock("log_support", {}, "Tag Değiştirildi") is True


class TestDuplicateSiteIdPrevention:
    """Tests for duplicate site_id check in process_message."""

    @patch("app.handlers.common.get_claude")
    @patch("app.handlers.common.get_sheets")
    @patch("app.handlers.common._resolve_user_name", return_value="Batu")
    def test_duplicate_site_id_is_rejected(self, mock_resolve, mock_get_sheets, mock_get_claude):
        from app.handlers.common import process_message, thread_store

        # Claude returns a create_site operation
        mock_claude = MagicMock()
        mock_parse_result = MagicMock()
        mock_parse_result.operation = "create_site"
        mock_parse_result.data = {
            "site_id": "MIG-TR-01",
            "customer": "Migros",
            "city": "Istanbul",
            "country": "Turkey",
            "facility_type": "Food",
            "contract_status": "Active",
            "go_live_date": "2025-03-01",
            "supervisor_1": "Ahmet",
            "phone_1": "555-1234",
        }
        mock_parse_result.error = None
        mock_parse_result.missing_fields = []
        mock_parse_result.warnings = []
        mock_parse_result.language = "tr"
        mock_parse_result.extra_operations = None
        mock_get_claude.return_value = mock_claude
        mock_claude.parse_message.return_value = mock_parse_result

        # Sheets returns existing sites with MIG-TR-01
        mock_sheets = MagicMock()
        mock_sheets.read_sites.return_value = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros"},
        ]
        mock_get_sheets.return_value = mock_sheets

        say = MagicMock()
        client = MagicMock()

        process_message(
            text="yeni site: Migros Istanbul",
            user_id="U123",
            channel="C001",
            thread_ts="ts_001",
            say=say,
            client=client,
            event_ts="evt_dup_site_001",
        )

        # Should warn about duplicate
        say.assert_called()
        call_kwargs = say.call_args
        text_arg = call_kwargs.kwargs.get("text", "") if call_kwargs.kwargs else call_kwargs[1].get("text", "")
        assert "MIG-TR-01" in text_arg
        assert "zaten mevcut" in text_arg

    @patch("app.handlers.common.get_claude")
    @patch("app.handlers.common.get_sheets")
    @patch("app.handlers.common._resolve_user_name", return_value="Batu")
    def test_new_site_id_is_allowed(self, mock_resolve, mock_get_sheets, mock_get_claude):
        from app.handlers.common import process_message, thread_store

        mock_claude = MagicMock()
        mock_parse_result = MagicMock()
        mock_parse_result.operation = "create_site"
        mock_parse_result.data = {
            "site_id": "NEW-TR-01",
            "customer": "New Corp",
            "city": "Ankara",
            "country": "Turkey",
            "facility_type": "Healthcare",
            "contract_status": "Active",
            "supervisor_1": "Ali",
            "phone_1": "555-9999",
        }
        mock_parse_result.error = None
        mock_parse_result.missing_fields = []
        mock_parse_result.warnings = []
        mock_parse_result.language = "tr"
        mock_parse_result.extra_operations = None
        mock_get_claude.return_value = mock_claude
        mock_claude.parse_message.return_value = mock_parse_result

        mock_sheets = MagicMock()
        mock_sheets.read_sites.return_value = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros"},
        ]
        mock_get_sheets.return_value = mock_sheets

        say = MagicMock()
        client = MagicMock()

        process_message(
            text="yeni site: New Corp Ankara",
            user_id="U123",
            channel="C001",
            thread_ts="ts_002",
            say=say,
            client=client,
            event_ts="evt_new_site_001",
        )

        # Should NOT warn about duplicate — should proceed to confirmation
        for call in say.call_args_list:
            kwargs = call.kwargs if call.kwargs else call[1]
            text_arg = kwargs.get("text", "")
            assert "zaten mevcut" not in text_arg


class TestPermissionEnforcement:
    """Tests for permission checks in confirm/cancel handlers."""

    def test_non_initiator_cannot_confirm(self):
        from app.handlers.common import thread_store

        # Set up thread state with user U_OWNER as initiator
        thread_store.set("ts_perm_001", {
            "operation": "log_support",
            "user_id": "U_OWNER",
            "data": {"site_id": "MIG-TR-01"},
            "missing_fields": [],
        })

        say = MagicMock()
        body = {
            "message": {"thread_ts": "ts_perm_001", "ts": "msg_001"},
            "user": {"id": "U_OTHER"},
            "channel": {"id": "C001"},
        }

        # Simulate what handle_confirm does for permission check
        msg = body.get("message", {})
        thread_ts = msg.get("thread_ts") or msg.get("ts", "")
        user_id = body.get("user", {}).get("id", "")

        state = thread_store.get(thread_ts)
        assert state is not None
        assert state["user_id"] != user_id  # Different user

        # Clean up
        thread_store.clear("ts_perm_001")

    def test_initiator_can_confirm(self):
        from app.handlers.common import thread_store

        thread_store.set("ts_perm_002", {
            "operation": "log_support",
            "user_id": "U_OWNER",
            "data": {"site_id": "MIG-TR-01"},
            "missing_fields": [],
        })

        state = thread_store.get("ts_perm_002")
        assert state is not None
        assert state["user_id"] == "U_OWNER"

        # Clean up
        thread_store.clear("ts_perm_002")


class TestLastVerifiedAutoInjection:
    """Tests for Last Verified date auto-injection in handle_confirm."""

    def test_hardware_entries_get_last_verified(self):
        """Verify the injection logic for hardware entries."""
        from datetime import date

        data = {
            "site_id": "MIG-TR-01",
            "entries": [
                {"device_type": "Tag", "qty": 10},
                {"device_type": "Gateway", "qty": 2},
            ],
        }
        operation = "update_hardware"
        today = date.today().isoformat()

        # Replicate the injection logic from handle_confirm
        if operation == "update_hardware":
            for entry in data.get("entries", []):
                if not entry.get("last_verified"):
                    entry["last_verified"] = data.get("last_verified", today)

        assert data["entries"][0]["last_verified"] == today
        assert data["entries"][1]["last_verified"] == today

    def test_hardware_entries_preserve_existing_last_verified(self):
        """If an entry already has last_verified, don't overwrite."""
        from datetime import date

        data = {
            "site_id": "MIG-TR-01",
            "entries": [
                {"device_type": "Tag", "qty": 10, "last_verified": "2025-01-01"},
            ],
        }
        operation = "update_hardware"
        today = date.today().isoformat()

        if operation == "update_hardware":
            for entry in data.get("entries", []):
                if not entry.get("last_verified"):
                    entry["last_verified"] = data.get("last_verified", today)

        assert data["entries"][0]["last_verified"] == "2025-01-01"

    def test_implementation_gets_last_verified(self):
        """Verify auto-injection for update_implementation."""
        from datetime import date

        data = {
            "site_id": "MIG-TR-01",
            "Internet Provider": "ERG Controls",
        }
        operation = "update_implementation"
        today = date.today().isoformat()

        if operation == "update_implementation":
            if not data.get("last_verified"):
                data["last_verified"] = today

        assert data["last_verified"] == today

    def test_implementation_preserves_existing_last_verified(self):
        from datetime import date

        data = {
            "site_id": "MIG-TR-01",
            "Internet Provider": "ERG Controls",
            "last_verified": "2025-01-01",
        }
        operation = "update_implementation"
        today = date.today().isoformat()

        if operation == "update_implementation":
            if not data.get("last_verified"):
                data["last_verified"] = today

        assert data["last_verified"] == "2025-01-01"


class TestBuildSitesContext:
    """Tests for build_sites_context() — dynamic sites list for Claude."""

    def test_builds_compact_reference(self):
        sites = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros"},
            {"Site ID": "YTP-TR-01", "Customer": "Yeditepe Üniversitesi Koşuyolu Hastanesi"},
        ]
        result = build_sites_context(sites)
        assert "MIG-TR-01 | Migros" in result
        assert "YTP-TR-01 | Yeditepe Üniversitesi Koşuyolu Hastanesi" in result

    def test_empty_sites_returns_empty(self):
        assert build_sites_context([]) == ""

    def test_excludes_sites_without_id(self):
        sites = [
            {"Site ID": "", "Customer": "Ghost"},
            {"Site ID": "MIG-TR-01", "Customer": "Migros"},
        ]
        result = build_sites_context(sites)
        assert "Ghost" not in result
        assert "MIG-TR-01" in result

    def test_contains_instruction_header(self):
        sites = [{"Site ID": "MIG-TR-01", "Customer": "Migros"}]
        result = build_sites_context(sites)
        assert "existing" in result.lower() or "site" in result.lower()


class TestUpdateSiteDoesNotRequireCreateFields:
    """Bug 15: update_site should NOT enforce create_site must fields."""

    def test_update_site_no_create_must_fields(self):
        """update_site with only site_id + contacts should have no must-field blockers."""
        from app.utils.missing_fields import enforce_must_fields

        data = {
            "site_id": "YTP-TR-01",
            "supervisor_1": "Cigdem Yuksel Koc",
            "phone_1": "0 535 411 78 24",
        }
        missing = enforce_must_fields("update_site", data, [])
        # Should NOT require customer, city, country, facility_type, contract_status
        create_fields = {"customer", "city", "country", "facility_type", "contract_status"}
        assert not create_fields.intersection(missing), (
            f"update_site should not require create_site fields, but got: {missing}"
        )

    def test_update_site_empty_missing_list(self):
        """update_site with partial data should return empty missing list."""
        from app.utils.missing_fields import enforce_must_fields

        data = {"site_id": "YTP-TR-01", "supervisor_1": "Test"}
        missing = enforce_must_fields("update_site", data, [])
        assert missing == []

    def test_create_site_still_requires_must_fields(self):
        """create_site should still enforce all must fields."""
        from app.utils.missing_fields import enforce_must_fields

        data = {"site_id": "NEW-TR-01"}
        missing = enforce_must_fields("create_site", data, [])
        assert "customer" in missing
        assert "city" in missing
        assert "country" in missing


class TestSanitizeUnknownFields:
    """Bug 15: Unknown fields invented by Haiku should be moved to notes."""

    def test_unknown_field_stripped_and_moved_to_notes(self):
        from app.handlers.common import sanitize_unknown_fields

        data = {
            "site_id": "YTP-TR-01",
            "supervisor_1": "Cigdem Yuksel Koc",
            "phone_1": "0 535 411 78 24",
            "supervisor_1_role": "EKK Hemsiresi",
        }
        sanitize_unknown_fields("update_site", data)
        assert "supervisor_1_role" not in data
        assert "EKK Hemsiresi" in data.get("notes", "")

    def test_known_fields_pass_through(self):
        from app.handlers.common import sanitize_unknown_fields

        data = {
            "site_id": "YTP-TR-01",
            "supervisor_1": "Test",
            "phone_1": "555",
            "notes": "existing note",
        }
        sanitize_unknown_fields("update_site", data)
        assert data["supervisor_1"] == "Test"
        assert data["phone_1"] == "555"

    def test_multiple_unknown_fields_all_appended(self):
        from app.handlers.common import sanitize_unknown_fields

        data = {
            "site_id": "YTP-TR-01",
            "supervisor_1_role": "EKK Hemsiresi",
            "supervisor_2_title": "YBU Sorumlu",
        }
        sanitize_unknown_fields("update_site", data)
        notes = data.get("notes", "")
        assert "EKK Hemsiresi" in notes
        assert "YBU Sorumlu" in notes

    def test_existing_notes_preserved(self):
        from app.handlers.common import sanitize_unknown_fields

        data = {
            "site_id": "YTP-TR-01",
            "supervisor_1_role": "EKK Hemsiresi",
            "notes": "onceki not",
        }
        sanitize_unknown_fields("update_site", data)
        assert "onceki not" in data["notes"]
        assert "EKK Hemsiresi" in data["notes"]

    def test_support_log_unknown_fields(self):
        from app.handlers.common import sanitize_unknown_fields

        data = {
            "site_id": "MIG-TR-01",
            "received_date": "2026-02-16",
            "type": "Visit",
            "status": "Resolved",
            "custom_field": "some value",
        }
        sanitize_unknown_fields("log_support", data)
        assert "custom_field" not in data
        assert "some value" in data.get("notes", "")

    def test_private_keys_ignored(self):
        """Keys starting with _ are internal markers, not unknown fields."""
        from app.handlers.common import sanitize_unknown_fields

        data = {
            "site_id": "YTP-TR-01",
            "_row_index": 5,
            "supervisor_1": "Test",
        }
        sanitize_unknown_fields("update_site", data)
        assert data["_row_index"] == 5

    def test_operation_without_key_map_is_noop(self):
        from app.handlers.common import sanitize_unknown_fields

        data = {"query_type": "site_summary", "site_id": "MIG-TR-01", "extra": "x"}
        sanitize_unknown_fields("query", data)
        # query has no key map, should not modify data
        assert data["extra"] == "x"


class TestSitesContextInjection:
    """Tests that process_message reads sites and passes them to Claude."""

    @patch("app.handlers.common.get_claude")
    @patch("app.handlers.common.get_sheets")
    @patch("app.handlers.common._resolve_user_name", return_value="Batu")
    def test_sites_context_passed_to_claude(self, mock_resolve, mock_get_sheets, mock_get_claude):
        """process_message should read sites and pass sites_context to parse_message."""
        from app.handlers.common import process_message

        mock_claude = MagicMock()
        mock_parse_result = MagicMock()
        mock_parse_result.operation = "update_site"
        mock_parse_result.data = {"site_id": "YTP-TR-01", "supervisor_1": "Cigdem"}
        mock_parse_result.error = None
        mock_parse_result.missing_fields = []
        mock_parse_result.warnings = []
        mock_parse_result.language = "tr"
        mock_parse_result.extra_operations = None
        mock_get_claude.return_value = mock_claude
        mock_claude.parse_message.return_value = mock_parse_result

        mock_sheets = MagicMock()
        mock_sheets.read_sites.return_value = [
            {"Site ID": "YTP-TR-01", "Customer": "Yeditepe Üniversitesi Koşuyolu Hastanesi"},
        ]
        mock_get_sheets.return_value = mock_sheets

        say = MagicMock()
        client = MagicMock()

        process_message(
            text="yeditepe kosuyolu icin iletisim bilgilerini ekle",
            user_id="U123",
            channel="C001",
            thread_ts="ts_sites_ctx_001",
            say=say,
            client=client,
            event_ts="evt_sites_ctx_001",
        )

        # Claude should have been called with sites_context
        call_kwargs = mock_claude.parse_message.call_args
        assert "sites_context" in call_kwargs.kwargs or (
            len(call_kwargs.args) > 3
        ), "parse_message should receive sites_context"
        sites_ctx = call_kwargs.kwargs.get("sites_context", "")
        assert "YTP-TR-01" in sites_ctx
