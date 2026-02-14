"""Tests for Session 6 bug fixes."""

import pytest

from app.services.site_resolver import SiteResolver
from app.utils.formatters import format_chain_input_prompt
from app.utils.missing_fields import enforce_must_fields


class TestBug1ChainSiteIdContext:
    """Bug 1: Chain step should not ask for site_id when it's already known."""

    def test_chain_step_hardware_site_id_not_in_missing(self):
        """Chain step 2 (hardware) with site_id in data → site_id not in missing."""
        data = {"site_id": "TCO-TR-01", "device_type": "Gateway", "qty": 5}
        missing = enforce_must_fields("update_hardware", data, [])
        assert "site_id" not in missing

    def test_chain_step_hardware_site_id_removed_from_claude_missing(self):
        """Even if Claude reports site_id as missing, enforce removes it when present."""
        data = {"site_id": "TCO-TR-01", "device_type": "Gateway", "qty": 5}
        missing = enforce_must_fields("update_hardware", data, ["site_id"])
        assert "site_id" not in missing

    def test_chain_step_implementation_site_id_not_in_missing(self):
        """Chain step 3 (implementation) with site_id in data → site_id not in missing."""
        data = {"site_id": "TCO-TR-01", "internet_provider": "ERG Controls", "ssid": "ERG-Net"}
        missing = enforce_must_fields("update_implementation", data, [])
        assert "site_id" not in missing

    def test_bulk_hardware_entries_satisfy_device_type_qty(self):
        """Bulk hardware with entries list should not flag device_type/qty as missing."""
        data = {
            "site_id": "TST-TR-01",
            "entries": [
                {"device_type": "Tag", "qty": 10},
                {"device_type": "Anchor", "qty": 15},
                {"device_type": "Gateway", "qty": 1},
            ],
        }
        missing = enforce_must_fields("update_hardware", data, [])
        assert "device_type" not in missing
        assert "qty" not in missing
        assert "site_id" not in missing

    def test_bulk_hardware_entries_from_claude_missing(self):
        """Even if Claude reports device_type/qty missing, entries should override."""
        data = {
            "site_id": "TST-TR-01",
            "entries": [{"device_type": "Tag", "qty": 10}],
        }
        missing = enforce_must_fields("update_hardware", data, ["device_type", "qty"])
        assert "device_type" not in missing
        assert "qty" not in missing

    def test_empty_entries_still_flags_device_type_qty(self):
        """Empty entries list should still flag device_type/qty as missing."""
        data = {"site_id": "TST-TR-01", "entries": []}
        missing = enforce_must_fields("update_hardware", data, [])
        assert "device_type" in missing
        assert "qty" in missing

    def test_chain_prompt_excludes_site_id(self):
        """format_chain_input_prompt() should not list site_id in must fields."""
        blocks = format_chain_input_prompt(2, 4, "update_hardware")
        body_text = blocks[0]["text"]["text"]
        assert "Hangi müşteri/saha için?" not in body_text
        # Should still mention other must fields
        assert "Hangi cihaz türü?" in body_text
        assert "Kaç adet?" in body_text

    def test_chain_prompt_excludes_site_id_for_implementation(self):
        """format_chain_input_prompt() for implementation should not ask for site."""
        blocks = format_chain_input_prompt(3, 4, "update_implementation", facility_type="Food")
        body_text = blocks[0]["text"]["text"]
        assert "Hangi müşteri/saha için?" not in body_text
        # Should still mention implementation must fields
        assert "İnternet" in body_text or "SSID" in body_text


class TestBug1ChainSiteIdInjection:
    """Bug 1 part 2: Chain site_id must be injected into Claude context."""

    def test_chain_input_prepends_site_context(self):
        """When awaiting_chain_input, message sent to Claude should include site context."""
        from unittest.mock import MagicMock, patch
        from app.handlers.common import process_message, thread_store

        thread_ts = "chain-site-inject-ts"
        thread_store.set(thread_ts, {
            "operation": "update_hardware",
            "user_id": "U123",
            "data": {"site_id": "TCO-TR-01"},
            "missing_fields": [],
            "awaiting_chain_input": True,
            "chain_steps": ["create_site", "update_hardware", "update_implementation"],
            "current_step": 2,
            "total_steps": 3,
            "completed_operations": [{"operation": "create_site", "readback": "", "ticket_id": None}],
            "skipped_operations": [],
            "pending_operations": [{"operation": "update_implementation", "data": {}}],
            "raw_message": "yeni saha ekle",
            "sender_name": "Batu",
            "language": "tr",
        })

        # Mock Claude to capture what message it receives
        mock_result = MagicMock()
        mock_result.operation = "update_hardware"
        mock_result.data = {"device_type": "Gateway", "qty": 5}
        mock_result.missing_fields = []
        mock_result.error = None
        mock_result.warnings = None
        mock_result.language = "tr"
        mock_result.extra_operations = None

        captured_messages = []

        def capture_parse(message, sender_name, thread_context=None):
            captured_messages.append(message)
            return mock_result

        say_mock = MagicMock()
        client_mock = MagicMock()
        client_mock.users_info.return_value = {"user": {"profile": {"display_name": "Batu"}}}

        with patch("app.handlers.common.get_claude") as mock_get_claude, \
             patch("app.handlers.common.get_sheets") as mock_get_sheets:
            mock_claude_inst = MagicMock()
            mock_claude_inst.parse_message = capture_parse
            mock_get_claude.return_value = mock_claude_inst
            mock_get_sheets.return_value = MagicMock()

            process_message(
                text="5 tane gateway var",
                user_id="U123",
                channel="C123",
                thread_ts=thread_ts,
                say=say_mock,
                client=client_mock,
                event_ts="evt-chain-inject",
            )

        thread_store.clear(thread_ts)

        # The message sent to Claude should contain the site_id context
        assert len(captured_messages) == 1
        assert "TCO-TR-01" in captured_messages[0]

    def test_chain_input_preserves_original_user_text(self):
        """Site context prefix should not destroy the user's actual message."""
        from unittest.mock import MagicMock, patch
        from app.handlers.common import process_message, thread_store

        thread_ts = "chain-preserve-ts"
        thread_store.set(thread_ts, {
            "operation": "update_hardware",
            "user_id": "U123",
            "data": {"site_id": "TCO-TR-01"},
            "missing_fields": [],
            "awaiting_chain_input": True,
            "chain_steps": ["create_site", "update_hardware"],
            "current_step": 2,
            "total_steps": 2,
            "completed_operations": [{"operation": "create_site", "readback": "", "ticket_id": None}],
            "skipped_operations": [],
            "pending_operations": [],
            "raw_message": "test",
            "sender_name": "Batu",
            "language": "tr",
        })

        captured_messages = []
        mock_result = MagicMock()
        mock_result.operation = "update_hardware"
        mock_result.data = {"device_type": "Tag", "qty": 32}
        mock_result.missing_fields = []
        mock_result.error = None
        mock_result.warnings = None
        mock_result.language = "tr"
        mock_result.extra_operations = None

        def capture_parse(message, sender_name, thread_context=None):
            captured_messages.append(message)
            return mock_result

        say_mock = MagicMock()
        client_mock = MagicMock()
        client_mock.users_info.return_value = {"user": {"profile": {"display_name": "Batu"}}}

        with patch("app.handlers.common.get_claude") as mock_get_claude, \
             patch("app.handlers.common.get_sheets") as mock_get_sheets:
            mock_claude_inst = MagicMock()
            mock_claude_inst.parse_message = capture_parse
            mock_get_claude.return_value = mock_claude_inst
            mock_get_sheets.return_value = MagicMock()

            process_message(
                text="32 tag 13 anchor 2 gateway",
                user_id="U123",
                channel="C123",
                thread_ts=thread_ts,
                say=say_mock,
                client=client_mock,
                event_ts="evt-chain-preserve",
            )

        thread_store.clear(thread_ts)

        assert len(captured_messages) == 1
        assert "TCO-TR-01" in captured_messages[0]
        assert "32 tag 13 anchor 2 gateway" in captured_messages[0]


class TestBug2EsteNoveResolution:
    """Bug 2: 'este nove' should resolve to EST-TR-01, not EST-BR-09."""

    def test_este_nove_lowercase_resolves_correctly(self):
        """Even with same-prefix sites, exact customer match should win."""
        sites = [
            {"Site ID": "EST-TR-01", "Customer": "Este Nove"},
            {"Site ID": "EST-BR-09", "Customer": "Este Nove Test"},
        ]
        r = SiteResolver(sites)
        results = r.resolve("este nove")
        assert len(results) == 1
        assert results[0]["Site ID"] == "EST-TR-01"

    def test_este_nove_titlecase_resolves_correctly(self):
        sites = [
            {"Site ID": "EST-TR-01", "Customer": "Este Nove"},
            {"Site ID": "EST-BR-09", "Customer": "Este Nove Test"},
        ]
        r = SiteResolver(sites)
        results = r.resolve("Este Nove")
        assert len(results) == 1
        assert results[0]["Site ID"] == "EST-TR-01"

    def test_duplicate_customer_name_returns_all_matches(self):
        """Two sites with identical customer name → return both as ambiguous."""
        sites = [
            {"Site ID": "EST-TR-01", "Customer": "Este Nove"},
            {"Site ID": "EST-BR-09", "Customer": "Este Nove"},
        ]
        r = SiteResolver(sites)
        results = r.resolve("Este Nove")
        # Both match — ambiguous, return both
        assert len(results) == 2
        site_ids = {s["Site ID"] for s in results}
        assert "EST-TR-01" in site_ids
        assert "EST-BR-09" in site_ids

    def test_short_alias_does_not_outmatch_full_customer_name(self):
        """'est' alias should not beat exact customer match for 'este nove'."""
        sites = [
            {"Site ID": "EST-TR-01", "Customer": "Este Nove"},
            {"Site ID": "EST-BR-09", "Customer": "Something Else"},
        ]
        r = SiteResolver(sites)
        results = r.resolve("este nove")
        assert len(results) == 1
        assert results[0]["Site ID"] == "EST-TR-01"


class TestBug3SahaTerm:
    """Bug 3: Turkish-facing text should use 'saha' not 'site'."""

    def test_no_turkish_site_in_user_facing_py_strings(self):
        """No Turkish-inflected 'site' in .py files under app/ (user-facing text)."""
        import re
        from pathlib import Path

        # Turkish suffixes that would indicate "site" is used as a Turkish word
        # e.g. "siteye", "sitesi", "siteyi", "sitede", "siteler", "mevcut bir site"
        pattern = re.compile(
            r'(?:mevcut\s+bir\s+site|bir\s+site[ysd]|site[ysd][ieaı]|siteler|sitesi)',
            re.IGNORECASE,
        )
        app_dir = Path(__file__).parent.parent / "app"
        violations: list[str] = []
        for py_file in app_dir.rglob("*.py"):
            for i, line in enumerate(py_file.read_text().splitlines(), 1):
                if pattern.search(line):
                    violations.append(f"{py_file.name}:{i}: {line.strip()}")
        assert violations == [], f"Turkish 'site' found:\n" + "\n".join(violations)

    def test_system_prompt_has_saha_rule(self):
        """System prompt should instruct Claude to use 'saha' in Turkish."""
        from pathlib import Path
        prompt = (Path(__file__).parent.parent / "app" / "prompts" / "system_prompt.md").read_text()
        assert "saha" in prompt.lower()


class TestBug1ImplKeyMapping:
    """Bug 1 part 4: Implementation data uses column header keys, not snake_case."""

    def test_impl_column_header_keys_not_flagged_as_missing(self):
        """Claude returns 'Internet Provider'/'SSID' — enforce should recognize them."""
        data = {
            "site_id": "TCO-TR-01",
            "Internet Provider": "ERG Controls",
            "SSID": "ERG-Net",
        }
        missing = enforce_must_fields("update_implementation", data, [])
        assert "internet_provider" not in missing
        assert "ssid" not in missing

    def test_impl_snake_case_keys_still_work(self):
        """Backward compat: snake_case keys should still be recognized."""
        data = {
            "site_id": "TCO-TR-01",
            "internet_provider": "ERG Controls",
            "ssid": "ERG-Net",
        }
        missing = enforce_must_fields("update_implementation", data, [])
        assert "internet_provider" not in missing
        assert "ssid" not in missing

    def test_impl_missing_must_field_still_flagged(self):
        """If neither snake_case nor column header key present, flag it."""
        data = {"site_id": "TCO-TR-01", "SSID": "ERG-Net"}
        missing = enforce_must_fields("update_implementation", data, [])
        assert "internet_provider" in missing
        assert "ssid" not in missing

    def test_impl_claude_missing_with_column_header_present(self):
        """Claude reports 'internet_provider' missing but data has 'Internet Provider'."""
        data = {
            "site_id": "TCO-TR-01",
            "Internet Provider": "ERG Controls",
            "SSID": "ERG-Net",
        }
        missing = enforce_must_fields("update_implementation", data, ["internet_provider", "ssid"])
        assert "internet_provider" not in missing
        assert "ssid" not in missing

    def test_impl_facility_type_must_with_column_header_keys(self):
        """Food facility must fields with column header keys should be recognized."""
        data = {
            "site_id": "TCO-TR-01",
            "Internet Provider": "ERG Controls",
            "SSID": "ERG-Net",
            "Clean hygiene time": "20s",
            "HP alert time": "30s",
            "Hand hygiene time": "15s",
            "Hand hygiene interval (dashboard)": "60",
            "Hand hygiene type": "Soap",
        }
        missing = enforce_must_fields("update_implementation", data, [], facility_type="Food")
        assert "internet_provider" not in missing
        assert "ssid" not in missing
        assert "clean_hygiene_time" not in missing
        assert "hand_hygiene_time" not in missing


class TestBug5QuerySiteResolution:
    """Bug 5: Query operations must resolve customer names to Site IDs."""

    def test_query_resolves_customer_name_to_site_id(self):
        """'este nove' in a missing_data query should resolve to EST-TR-01."""
        from unittest.mock import MagicMock, patch
        from app.handlers.common import process_message, thread_store

        thread_ts = "query-resolve-ts"

        mock_result = MagicMock()
        mock_result.operation = "query"
        mock_result.data = {"query_type": "missing_data", "site_id": "este nove"}
        mock_result.missing_fields = []
        mock_result.error = None
        mock_result.warnings = None
        mock_result.language = "tr"
        mock_result.extra_operations = None

        say_mock = MagicMock()
        client_mock = MagicMock()
        client_mock.users_info.return_value = {"user": {"profile": {"display_name": "Batu"}}}

        mock_sites = [
            {"Site ID": "EST-TR-01", "Customer": "Este Nove", "Contract Status": "Active"},
        ]
        mock_sheets = MagicMock()
        mock_sheets.read_sites.return_value = mock_sites
        mock_sheets.read_hardware.return_value = []
        mock_sheets.read_support_log.return_value = []
        mock_sheets.read_all_implementation.return_value = []
        mock_sheets.read_stock.return_value = []

        with patch("app.handlers.common.get_claude") as mock_get_claude, \
             patch("app.handlers.common.get_sheets") as mock_get_sheets:
            mock_claude = MagicMock()
            mock_claude.parse_message.return_value = mock_result
            mock_get_claude.return_value = mock_claude
            mock_get_sheets.return_value = mock_sheets

            process_message(
                text="este nove icin hangi bilgiler eksik",
                user_id="U123",
                channel="C123",
                thread_ts=thread_ts,
                say=say_mock,
                client=client_mock,
                event_ts="evt-query-resolve",
            )

        thread_store.clear(thread_ts)

        # read_hardware should have been called with resolved site_id, not raw name
        hw_call_args = mock_sheets.read_hardware.call_args
        if hw_call_args:
            assert hw_call_args[0][0] == "EST-TR-01" or hw_call_args[1].get("site_id") == "EST-TR-01", \
                f"read_hardware called with wrong site_id: {hw_call_args}"

    def test_query_unknown_site_shows_error(self):
        """Query with unresolvable site name should show error."""
        from unittest.mock import MagicMock, patch
        from app.handlers.common import process_message, thread_store

        thread_ts = "query-unknown-ts"

        mock_result = MagicMock()
        mock_result.operation = "query"
        mock_result.data = {"query_type": "missing_data", "site_id": "nonexistent company"}
        mock_result.missing_fields = []
        mock_result.error = None
        mock_result.warnings = None
        mock_result.language = "tr"
        mock_result.extra_operations = None

        say_mock = MagicMock()
        client_mock = MagicMock()
        client_mock.users_info.return_value = {"user": {"profile": {"display_name": "Batu"}}}

        mock_sites = [
            {"Site ID": "EST-TR-01", "Customer": "Este Nove", "Contract Status": "Active"},
        ]
        mock_sheets = MagicMock()
        mock_sheets.read_sites.return_value = mock_sites

        with patch("app.handlers.common.get_claude") as mock_get_claude, \
             patch("app.handlers.common.get_sheets") as mock_get_sheets:
            mock_claude = MagicMock()
            mock_claude.parse_message.return_value = mock_result
            mock_get_claude.return_value = mock_claude
            mock_get_sheets.return_value = mock_sheets

            process_message(
                text="nonexistent company icin eksik bilgiler",
                user_id="U123",
                channel="C123",
                thread_ts=thread_ts,
                say=say_mock,
                client=client_mock,
                event_ts="evt-query-unknown",
            )

        thread_store.clear(thread_ts)

        # Should show an error message about unknown site
        assert say_mock.called
        # Check that it mentions the site name or shows an error
        all_calls = [str(c) for c in say_mock.call_args_list]
        all_text = " ".join(all_calls)
        assert "bulunamadı" in all_text or "nonexistent" in all_text.lower()

    def test_query_valid_site_id_not_resolved(self):
        """Query with valid Site ID format should not trigger resolution."""
        from unittest.mock import MagicMock, patch
        from app.handlers.common import process_message, thread_store

        thread_ts = "query-valid-ts"

        mock_result = MagicMock()
        mock_result.operation = "query"
        mock_result.data = {"query_type": "missing_data", "site_id": "EST-TR-01"}
        mock_result.missing_fields = []
        mock_result.error = None
        mock_result.warnings = None
        mock_result.language = "tr"
        mock_result.extra_operations = None

        say_mock = MagicMock()
        client_mock = MagicMock()
        client_mock.users_info.return_value = {"user": {"profile": {"display_name": "Batu"}}}

        mock_sheets = MagicMock()
        mock_sheets.read_sites.return_value = [
            {"Site ID": "EST-TR-01", "Customer": "Este Nove", "Contract Status": "Active"},
        ]
        mock_sheets.read_hardware.return_value = []
        mock_sheets.read_support_log.return_value = []
        mock_sheets.read_all_implementation.return_value = []
        mock_sheets.read_stock.return_value = []

        with patch("app.handlers.common.get_claude") as mock_get_claude, \
             patch("app.handlers.common.get_sheets") as mock_get_sheets:
            mock_claude = MagicMock()
            mock_claude.parse_message.return_value = mock_result
            mock_get_claude.return_value = mock_claude
            mock_get_sheets.return_value = mock_sheets

            process_message(
                text="EST-TR-01 eksik bilgiler",
                user_id="U123",
                channel="C123",
                thread_ts=thread_ts,
                say=say_mock,
                client=client_mock,
                event_ts="evt-query-valid",
            )

        thread_store.clear(thread_ts)

        # read_hardware should be called with the original site_id
        hw_call_args = mock_sheets.read_hardware.call_args
        if hw_call_args:
            called_with = hw_call_args[0][0] if hw_call_args[0] else hw_call_args[1].get("site_id")
            assert called_with == "EST-TR-01"


class TestBug6FoodChainFacilityType:
    """Bug 6: Food-specific must fields not shown in chain implementation step."""

    def test_chain_ctx_preserves_facility_type(self):
        """process_message chain_ctx should include facility_type from existing state."""
        from app.utils.formatters import format_chain_input_prompt

        # Direct test: format_chain_input_prompt with facility_type=Food
        blocks = format_chain_input_prompt(3, 3, "update_implementation", facility_type="Food")
        text = blocks[0]["text"]["text"]
        # Should include Food-specific must fields (English attribute names)
        assert "Clean hygiene time" in text
        assert "HP alert time" in text
        assert "Hand hygiene time" in text

    def test_chain_ctx_healthcare_facility_type(self):
        """Healthcare site should show tag_clean_to_red_timeout as must."""
        from app.utils.formatters import format_chain_input_prompt

        blocks = format_chain_input_prompt(3, 3, "update_implementation", facility_type="Healthcare")
        text = blocks[0]["text"]["text"]
        # Friendly name uses English: "Tag clean-to-red timeout değeri kaç saniye?"
        assert "clean-to-red timeout" in text.lower()

    def test_facility_type_propagated_in_chain_state(self):
        """When process_message stores chain_ctx, facility_type should be preserved."""
        from unittest.mock import MagicMock, patch
        from app.handlers.common import process_message, thread_store

        thread_ts = "chain-facility-ts"
        # Simulate: step 2 (hardware) confirmed, moving to step 3 (implementation)
        # User is providing hardware data for a Food site
        thread_store.set(thread_ts, {
            "operation": "update_hardware",
            "user_id": "U123",
            "data": {"site_id": "TCO-TR-01"},
            "missing_fields": [],
            "awaiting_chain_input": True,
            "chain_steps": ["create_site", "update_hardware", "update_implementation"],
            "current_step": 2,
            "total_steps": 3,
            "completed_operations": [{"operation": "create_site", "readback": "", "ticket_id": None}],
            "skipped_operations": [],
            "pending_operations": [{"operation": "update_implementation", "data": {}}],
            "raw_message": "yeni saha ekle",
            "sender_name": "Batu",
            "language": "tr",
            "facility_type": "Food",  # This was stored when create_site was confirmed
        })

        mock_result = MagicMock()
        mock_result.operation = "update_hardware"
        mock_result.data = {"entries": [{"device_type": "Tag", "qty": 10}]}
        mock_result.missing_fields = []
        mock_result.error = None
        mock_result.warnings = None
        mock_result.language = "tr"
        mock_result.extra_operations = None

        say_mock = MagicMock()
        client_mock = MagicMock()
        client_mock.users_info.return_value = {"user": {"profile": {"display_name": "Batu"}}}

        with patch("app.handlers.common.get_claude") as mock_get_claude, \
             patch("app.handlers.common.get_sheets") as mock_get_sheets:
            mock_claude = MagicMock()
            mock_claude.parse_message.return_value = mock_result
            mock_get_claude.return_value = mock_claude
            mock_get_sheets.return_value = MagicMock()

            process_message(
                text="10 tag var",
                user_id="U123",
                channel="C123",
                thread_ts=thread_ts,
                say=say_mock,
                client=client_mock,
                event_ts="evt-chain-facility",
            )

        # Check that the stored state still has facility_type
        stored_state = thread_store.get(thread_ts)
        thread_store.clear(thread_ts)
        assert stored_state is not None
        assert stored_state.get("facility_type") == "Food", \
            f"facility_type lost in chain state: {stored_state.get('facility_type')}"


class TestBug7SsidCapitalization:
    """Bug 7: 'SSID' should display as 'SSID' not 'Ssid' in confirmation cards."""

    def test_ssid_column_header_key_displayed_correctly(self):
        """Confirmation card with key 'SSID' should show label 'SSID'."""
        from app.utils.formatters import format_confirmation_message
        import json

        data = {
            "operation": "update_implementation",
            "site_id": "TCO-TR-01",
            "SSID": "deneme",
            "Internet Provider": "ERG Controls",
        }
        blocks = format_confirmation_message(data)
        text = json.dumps(blocks, ensure_ascii=False)
        assert "Ssid" not in text, f"Found 'Ssid' in confirmation card: {text}"
        assert "SSID" in text

    def test_ssid_snake_case_key_displayed_correctly(self):
        """Confirmation card with key 'ssid' should also show label 'SSID'."""
        from app.utils.formatters import format_confirmation_message
        import json

        data = {
            "operation": "update_implementation",
            "site_id": "TCO-TR-01",
            "ssid": "deneme",
        }
        blocks = format_confirmation_message(data)
        text = json.dumps(blocks, ensure_ascii=False)
        assert "Ssid" not in text
        assert "SSID" in text

    def test_internet_provider_column_header_key_displayed_correctly(self):
        """'Internet Provider' key should not become 'Internet provider'."""
        from app.utils.formatters import format_confirmation_message
        import json

        data = {
            "operation": "update_implementation",
            "site_id": "TCO-TR-01",
            "Internet Provider": "ERG Controls",
        }
        blocks = format_confirmation_message(data)
        text = json.dumps(blocks, ensure_ascii=False)
        assert "Internet Provider" in text

    def test_query_response_uses_field_labels(self):
        """format_query_response generic path should use FIELD_LABELS."""
        from app.utils.formatters import format_query_response
        import json

        data = {"ssid": "test-network", "hw_version": "1.2"}
        blocks = format_query_response("generic", data)
        text = json.dumps(blocks, ensure_ascii=False)
        assert "SSID" in text
        assert "HW Version" in text


class TestBug4FeedbackWording:

    def test_feedback_negative_uses_new_wording(self):
        """The feedback_negative handler should use unified wording."""
        import inspect
        from app.handlers import actions
        source = inspect.getsource(actions.register)
        assert "Nasıl daha iyi yapabilirdim?" in source, \
            "feedback_negative handler should use 'Nasıl daha iyi yapabilirdim?'"

    def test_feedback_negative_not_old_wording(self):
        """Old write-specific wording should not appear."""
        import inspect
        from app.handlers import actions
        source = inspect.getsource(actions.register)
        assert "Ne olmalıydı" not in source, \
            "Old write-specific wording 'Ne olmalıydı' should be removed"


class TestBug8HardwareBulkWriteColumnOffset:
    """Bug 8: Bulk hardware writes must each be a new row in A-G, never past column G."""

    def test_append_hardware_row_has_exactly_7_elements(self):
        """Each append_hardware call should produce a row with exactly 7 values (A-G)."""
        from unittest.mock import MagicMock, patch
        from app.services.sheets import SheetsService, HARDWARE_COLUMNS

        mock_ws = MagicMock()
        svc = object.__new__(SheetsService)
        svc._ws_cache = {"Hardware Inventory": mock_ws}

        svc.append_hardware({"site_id": "TCO-TR-01", "device_type": "Tag", "qty": 10})

        mock_ws.append_row.assert_called_once()
        row = mock_ws.append_row.call_args[0][0]
        assert len(row) == len(HARDWARE_COLUMNS) == 7, \
            f"Row should have exactly 7 elements (A-G), got {len(row)}"

    def test_append_hardware_uses_table_range(self):
        """append_hardware must pass table_range to constrain append to columns A-G."""
        from unittest.mock import MagicMock
        from app.services.sheets import SheetsService

        mock_ws = MagicMock()
        svc = object.__new__(SheetsService)
        svc._ws_cache = {"Hardware Inventory": mock_ws}

        svc.append_hardware({"site_id": "TCO-TR-01", "device_type": "Tag", "qty": 10})

        call_kwargs = mock_ws.append_row.call_args[1]
        assert "table_range" in call_kwargs, \
            "append_row must specify table_range to prevent helper column interference"
        assert call_kwargs["table_range"] == "A1:G1", \
            f"table_range should be 'A1:G1', got '{call_kwargs['table_range']}'"

    def test_bulk_write_3_entries_produces_3_separate_rows(self):
        """Bulk hardware with 3 entries should call append_hardware 3 times."""
        from unittest.mock import MagicMock, patch
        from app.services.sheets import SheetsService

        mock_ws = MagicMock()
        svc = object.__new__(SheetsService)
        svc._ws_cache = {"Hardware Inventory": mock_ws}

        entries = [
            {"device_type": "Tag", "qty": 10},
            {"device_type": "Anchor", "qty": 15},
            {"device_type": "Gateway", "qty": 1},
        ]
        for entry in entries:
            entry["site_id"] = "TCO-TR-01"
            svc.append_hardware(entry)

        assert mock_ws.append_row.call_count == 3, \
            f"Expected 3 append_row calls, got {mock_ws.append_row.call_count}"

        # Each call should have exactly 7 elements and table_range
        for i, call in enumerate(mock_ws.append_row.call_args_list):
            row = call[0][0]
            assert len(row) == 7, f"Entry {i+1} row has {len(row)} elements, expected 7"
            assert call[1].get("table_range") == "A1:G1", \
                f"Entry {i+1} missing table_range='A1:G1'"

    def test_single_entry_write_correct_columns(self):
        """Single hardware entry should write Site ID, Device Type, ..., Notes in A-G."""
        from unittest.mock import MagicMock
        from app.services.sheets import SheetsService

        mock_ws = MagicMock()
        svc = object.__new__(SheetsService)
        svc._ws_cache = {"Hardware Inventory": mock_ws}

        svc.append_hardware({
            "site_id": "TCO-TR-01",
            "device_type": "Gateway",
            "hw_version": "2.0",
            "fw_version": "3.1",
            "qty": 1,
            "notes": "Main gateway",
        })

        row = mock_ws.append_row.call_args[0][0]
        assert row[0] == "TCO-TR-01"   # A: Site ID
        assert row[1] == "Gateway"      # B: Device Type
        assert row[2] == "2.0"          # C: HW Version
        assert row[3] == "3.1"          # D: FW Version
        assert row[4] == 1             # E: Qty
        assert row[6] == "Main gateway" # G: Notes

    def test_all_append_methods_use_table_range(self):
        """All append/create methods should use table_range to prevent column drift."""
        from unittest.mock import MagicMock
        from app.services.sheets import SheetsService

        svc = object.__new__(SheetsService)
        mock_ws = MagicMock()
        svc._ws_cache = {
            "Sites": mock_ws,
            "Hardware Inventory": mock_ws,
            "Support Log": mock_ws,
            "Stock": mock_ws,
            "Audit Log": mock_ws,
        }

        # Test each append method
        svc.create_site({"site_id": "X", "customer": "Test"})
        assert mock_ws.append_row.call_args[1].get("table_range"), \
            "create_site must use table_range"
        mock_ws.reset_mock()

        svc.append_hardware({"site_id": "X", "device_type": "Tag", "qty": 1})
        assert mock_ws.append_row.call_args[1].get("table_range"), \
            "append_hardware must use table_range"
        mock_ws.reset_mock()

        svc.append_support_log({"site_id": "X", "type": "Visit", "status": "Open",
                                "issue_summary": "Test", "responsible": "Batu",
                                "received_date": "2026-02-14"})
        assert mock_ws.append_row.call_args[1].get("table_range"), \
            "append_support_log must use table_range"
        mock_ws.reset_mock()

        svc.append_stock({"location": "Istanbul", "device_type": "Tag", "qty": 5, "condition": "New"})
        assert mock_ws.append_row.call_args[1].get("table_range"), \
            "append_stock must use table_range"


class TestBug9ImplementationDropdowns:
    """Bug 9: Implementation dropdown fields must be validated and shown in prompts."""

    def test_implementation_dropdowns_config_exists(self):
        """IMPLEMENTATION_DROPDOWNS config should define valid options."""
        from app.field_config.field_options import IMPLEMENTATION_DROPDOWNS

        assert "Internet Provider" in IMPLEMENTATION_DROPDOWNS
        assert "Hand hygiene type" in IMPLEMENTATION_DROPDOWNS
        assert "Tag buzzer/vibration" in IMPLEMENTATION_DROPDOWNS

    def test_dropdown_options_have_values(self):
        """Each dropdown should have at least 2 options."""
        from app.field_config.field_options import IMPLEMENTATION_DROPDOWNS

        for field, options in IMPLEMENTATION_DROPDOWNS.items():
            assert len(options) >= 2, f"{field} should have at least 2 options, got {len(options)}"

    def test_missing_fields_message_shows_dropdown_options(self):
        """When a dropdown field is missing, prompt should include 'Seçenekler: ...'"""
        from app.utils.missing_fields import format_missing_fields_message

        msg, _ = format_missing_fields_message(
            ["hand_hygiene_type"], "update_implementation", language="tr"
        )
        assert "Seçenekler:" in msg or "seçenekler:" in msg.lower(), \
            f"Dropdown field prompt should include options, got: {msg}"

    def test_missing_fields_message_non_dropdown_no_options(self):
        """Non-dropdown fields should NOT show 'Seçenekler:'."""
        from app.utils.missing_fields import format_missing_fields_message

        msg, _ = format_missing_fields_message(
            ["ssid"], "update_implementation", language="tr"
        )
        assert "Seçenekler:" not in msg, \
            f"Non-dropdown field should not show options, got: {msg}"

    def test_chain_input_prompt_shows_dropdown_options(self):
        """format_chain_input_prompt should show options for dropdown fields."""
        from app.utils.formatters import format_chain_input_prompt

        blocks = format_chain_input_prompt(3, 3, "update_implementation")
        text = blocks[0]["text"]["text"]
        # internet_provider is a must field with dropdown
        assert "ERG Controls" in text or "Müşteri" in text, \
            f"Chain prompt should show Internet Provider options, got: {text}"

    def test_validate_dropdown_exact_match(self):
        """Exact match for dropdown value should pass."""
        from app.field_config.field_options import validate_impl_dropdown

        result = validate_impl_dropdown("Hand hygiene type", "Tek adımlı (sadece sabun)")
        assert result is not None
        assert result == "Tek adımlı (sadece sabun)"

    def test_validate_dropdown_fuzzy_match(self):
        """Fuzzy match should resolve to correct option."""
        from app.field_config.field_options import validate_impl_dropdown

        result = validate_impl_dropdown("Hand hygiene type", "iki adımlı")
        assert result is not None
        assert "İki adımlı" in result

    def test_validate_dropdown_no_match(self):
        """No match should return None."""
        from app.field_config.field_options import validate_impl_dropdown

        result = validate_impl_dropdown("Hand hygiene type", "üç adımlı yok böyle bişey")
        assert result is None

    def test_validate_dropdown_unknown_field(self):
        """Non-dropdown field should return the value as-is."""
        from app.field_config.field_options import validate_impl_dropdown

        result = validate_impl_dropdown("SSID", "my-network")
        assert result == "my-network"


class TestBug10EnglishAttributeNames:
    """Bug 10: Thingsboard attribute names must stay in English in friendly prompts."""

    def test_clean_hygiene_time_uses_english_name(self):
        """clean_hygiene_time prompt should contain 'Clean hygiene time', not Turkish."""
        from app.field_config.friendly_fields import FRIENDLY_FIELD_MAP

        text = FRIENDLY_FIELD_MAP["clean_hygiene_time"]
        assert "Clean hygiene time" in text, f"Should contain English name, got: {text}"

    def test_hp_alert_time_uses_english_name(self):
        """hp_alert_time prompt should contain 'HP alert time', not Turkish."""
        from app.field_config.friendly_fields import FRIENDLY_FIELD_MAP

        text = FRIENDLY_FIELD_MAP["hp_alert_time"]
        assert "HP alert time" in text, f"Should contain English name, got: {text}"

    def test_hand_hygiene_time_uses_english_name(self):
        """hand_hygiene_time prompt should contain 'Hand hygiene time'."""
        from app.field_config.friendly_fields import FRIENDLY_FIELD_MAP

        text = FRIENDLY_FIELD_MAP["hand_hygiene_time"]
        assert "Hand hygiene time" in text, f"Should contain English name, got: {text}"

    def test_hand_hygiene_interval_uses_english_name(self):
        """hand_hygiene_interval prompt should contain 'Hand hygiene interval'."""
        from app.field_config.friendly_fields import FRIENDLY_FIELD_MAP

        text = FRIENDLY_FIELD_MAP["hand_hygiene_interval"]
        assert "Hand hygiene interval" in text, f"Should contain English name, got: {text}"

    def test_hand_hygiene_type_uses_english_name(self):
        """hand_hygiene_type prompt should contain 'Hand hygiene type'."""
        from app.field_config.friendly_fields import FRIENDLY_FIELD_MAP

        text = FRIENDLY_FIELD_MAP["hand_hygiene_type"]
        assert "Hand hygiene type" in text, f"Should contain English name, got: {text}"

    def test_tag_clean_to_red_uses_english_name(self):
        """tag_clean_to_red_timeout prompt should contain 'Tag clean-to-red timeout'."""
        from app.field_config.friendly_fields import FRIENDLY_FIELD_MAP

        text = FRIENDLY_FIELD_MAP["tag_clean_to_red_timeout"]
        assert "Tag clean-to-red timeout" in text, f"Should contain English name, got: {text}"

    def test_no_turkish_translation_of_attribute_names(self):
        """Friendly fields should not contain Turkish translations of attribute names."""
        from app.field_config.friendly_fields import FRIENDLY_FIELD_MAP

        # These Turkish translations should NOT appear
        turkish_bad = ["hijyen süresi", "hijyeni süresi", "hijyeni aralığı", "hijyeni türü",
                        "uyarı süresi", "temiz→kırmızı"]
        for field in ["clean_hygiene_time", "hp_alert_time", "hand_hygiene_time",
                       "hand_hygiene_interval", "hand_hygiene_type", "tag_clean_to_red_timeout"]:
            text = FRIENDLY_FIELD_MAP[field]
            for bad in turkish_bad:
                assert bad not in text, \
                    f"Field '{field}' should not contain Turkish translation '{bad}', got: {text}"


class TestBug11FieldDescriptions:
    """Bug 11: Implementation fields should have Turkish descriptions for technicians."""

    def test_field_descriptions_config_exists(self):
        """FIELD_DESCRIPTIONS should exist with all implementation fields."""
        from app.field_config.field_descriptions import FIELD_DESCRIPTIONS

        impl_fields = [
            "clean_hygiene_time", "hp_alert_time", "hand_hygiene_time",
            "hand_hygiene_interval", "hand_hygiene_type", "tag_clean_to_red_timeout",
            "handwash_time", "entry_time", "gateway_placement",
            "charging_dock_placement", "dispenser_anchor_placement",
            "dispenser_anchor_power_type", "tag_buzzer_vibration",
            "internet_provider", "ssid", "password",
        ]
        for field in impl_fields:
            assert field in FIELD_DESCRIPTIONS, \
                f"FIELD_DESCRIPTIONS missing '{field}'"

    def test_descriptions_are_in_turkish(self):
        """Descriptions should be in Turkish (contain Turkish characters)."""
        from app.field_config.field_descriptions import FIELD_DESCRIPTIONS

        # At least some descriptions should have Turkish chars
        all_text = " ".join(FIELD_DESCRIPTIONS.values())
        assert any(c in all_text for c in "çğıöşüÇĞİÖŞÜ"), \
            "Descriptions should be in Turkish"

    def test_missing_fields_message_includes_description(self):
        """Implementation field prompts should include description."""
        from app.utils.missing_fields import format_missing_fields_message

        msg, _ = format_missing_fields_message(
            ["clean_hygiene_time"], "update_implementation", language="tr"
        )
        # Should include the description text (Turkish explanation)
        assert "badge" in msg.lower() or "kırmızı" in msg.lower() or "HP" in msg, \
            f"Missing field prompt should include description, got: {msg}"

    def test_chain_input_prompt_includes_description(self):
        """format_chain_input_prompt should show description for impl fields."""
        from app.utils.formatters import format_chain_input_prompt

        blocks = format_chain_input_prompt(3, 3, "update_implementation", facility_type="Food")
        text = blocks[0]["text"]["text"]
        # Clean hygiene time description mentions badge and kırmızı
        assert "badge" in text.lower() or "kırmızı" in text.lower(), \
            f"Chain prompt should include field description, got: {text}"

    def test_non_implementation_fields_no_description(self):
        """Sites, hardware, support log fields should NOT get descriptions."""
        from app.utils.missing_fields import format_missing_fields_message

        msg, _ = format_missing_fields_message(
            ["customer"], "create_site", language="tr"
        )
        # Sites field should just have friendly question, no long description
        assert len(msg) < 200, \
            f"Non-implementation field should not have long description, got: {msg}"

    def test_dropdown_field_shows_description_and_options(self):
        """Dropdown impl field should show: English name + description + options."""
        from app.utils.missing_fields import format_missing_fields_message

        msg, _ = format_missing_fields_message(
            ["hand_hygiene_type"], "update_implementation", language="tr"
        )
        # Should have English name, description, AND options
        assert "Hand hygiene type" in msg, f"Should have English name, got: {msg}"
        assert "Seçenekler:" in msg, f"Should have dropdown options, got: {msg}"
        assert "hijyen" in msg.lower() or "sabun" in msg.lower(), \
            f"Should have Turkish description, got: {msg}"
