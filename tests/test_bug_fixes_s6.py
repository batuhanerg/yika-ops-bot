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
        # Should include Food-specific must fields
        assert "Clean hygiene" in text or "clean hygiene" in text.lower()
        assert "HP uyarı" in text or "hp_alert" in text.lower()
        assert "El hijyeni" in text or "hand_hygiene" in text.lower()

    def test_chain_ctx_healthcare_facility_type(self):
        """Healthcare site should show tag_clean_to_red_timeout as must."""
        from app.utils.formatters import format_chain_input_prompt

        blocks = format_chain_input_prompt(3, 3, "update_implementation", facility_type="Healthcare")
        text = blocks[0]["text"]["text"]
        # Friendly name is "Tag temiz→kırmızı zaman aşımı kaç saniye?"
        assert "temiz" in text.lower() or "tag_clean_to_red_timeout" in text

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
