"""Tests for the feedback loop feature (Item 1, Session 4).

After each confirmed write, the bot sends a follow-up with 👍/👎 buttons.
👍 → log positive feedback silently
👎 → ask "Ne olmalıydı?" → store user response
All feedback stored in "Feedback" tab in the Google Sheet.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.utils.formatters import format_feedback_buttons
from app.services.sheets import FEEDBACK_COLUMNS


class TestFeedbackButtonFormatting:
    """Test the feedback follow-up message format."""

    def test_feedback_message_contains_question(self):
        blocks = format_feedback_buttons()
        text = _blocks_to_text(blocks)
        assert "Doğru kaydedildi mi?" in text

    def test_feedback_message_has_thumbs_up_button(self):
        blocks = format_feedback_buttons()
        actions = _find_actions_block(blocks)
        assert actions is not None
        action_ids = [e["action_id"] for e in actions["elements"]]
        assert "feedback_positive" in action_ids

    def test_feedback_message_has_thumbs_down_button(self):
        blocks = format_feedback_buttons()
        actions = _find_actions_block(blocks)
        assert actions is not None
        action_ids = [e["action_id"] for e in actions["elements"]]
        assert "feedback_negative" in action_ids

    def test_feedback_buttons_have_correct_emoji(self):
        blocks = format_feedback_buttons()
        actions = _find_actions_block(blocks)
        btn_texts = [e["text"]["text"] for e in actions["elements"]]
        assert any("👍" in t for t in btn_texts)
        assert any("👎" in t for t in btn_texts)


class TestFeedbackTabColumns:
    """Test that the Feedback tab schema is correctly defined."""

    def test_feedback_columns_defined(self):
        assert "Timestamp" in FEEDBACK_COLUMNS
        assert "User" in FEEDBACK_COLUMNS
        assert "Operation" in FEEDBACK_COLUMNS
        assert "Site ID" in FEEDBACK_COLUMNS
        assert "Rating" in FEEDBACK_COLUMNS
        assert "Expected Behavior" in FEEDBACK_COLUMNS
        assert "Original Message" in FEEDBACK_COLUMNS

    def test_feedback_columns_has_ticket_id(self):
        assert "Ticket ID" in FEEDBACK_COLUMNS


class TestFeedbackSheetWrite:
    """Test writing feedback to the Feedback tab."""

    @pytest.fixture
    def mock_sheets_with_feedback(self):
        mock_gc = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_gc.open_by_key.return_value = mock_spreadsheet

        feedback_ws = MagicMock()
        feedback_ws.title = "Feedback"

        def _worksheet(name):
            if name == "Feedback":
                return feedback_ws
            raise Exception(f"Unknown worksheet: {name}")

        mock_spreadsheet.worksheet.side_effect = _worksheet

        with patch("app.services.sheets.SheetsService._connect"):
            from app.services.sheets import SheetsService
            service = SheetsService.__new__(SheetsService)
            service.spreadsheet = mock_spreadsheet
            service._ws_cache = {}
            yield service, feedback_ws

    def test_append_positive_feedback(self, mock_sheets_with_feedback):
        service, ws = mock_sheets_with_feedback
        service.append_feedback(
            user="Batu",
            operation="log_support",
            site_id="MIG-TR-01",
            ticket_id="SUP-003",
            rating="positive",
            expected_behavior="",
            original_message="bugün gittim...",
        )
        ws.append_row.assert_called_once()
        row = ws.append_row.call_args[0][0]
        assert row[1] == "Batu"
        assert row[2] == "log_support"
        assert row[3] == "MIG-TR-01"
        assert row[4] == "SUP-003"
        assert row[5] == "positive"
        assert row[6] == ""  # No expected behavior for positive
        assert row[7] == "bugün gittim..."

    def test_append_negative_feedback(self, mock_sheets_with_feedback):
        service, ws = mock_sheets_with_feedback
        service.append_feedback(
            user="Mehmet",
            operation="update_hardware",
            site_id="ASM-TR-01",
            ticket_id="",
            rating="negative",
            expected_behavior="Tag sayısı 32 olmalıydı, 23 yazılmış",
            original_message="ASM'ye tag ekledik",
        )
        ws.append_row.assert_called_once()
        row = ws.append_row.call_args[0][0]
        assert row[1] == "Mehmet"
        assert row[5] == "negative"
        assert "32 olmalıydı" in row[6]


class TestFeedbackAfterQuery:
    """Item 3: Feedback buttons should appear after query responses too."""

    def test_format_feedback_buttons_default_question(self):
        """Default question is write-oriented."""
        blocks = format_feedback_buttons()
        text = _blocks_to_text(blocks)
        assert "Doğru kaydedildi mi?" in text

    def test_format_feedback_buttons_query_question(self):
        """Query context uses a different question."""
        blocks = format_feedback_buttons(context="query")
        text = _blocks_to_text(blocks)
        assert "Faydalı oldu mu?" in text

    def test_query_sends_feedback_buttons(self):
        """After a query response, feedback buttons should be sent."""
        from app.handlers.common import _handle_query, thread_store

        say = MagicMock()
        _handle_query(
            {"query_type": "stock"},
            thread_ts="T_Q_001",
            say=say,
            user_id="U123",
            language="tr",
        )
        # At least one call should include feedback buttons
        all_calls = say.call_args_list
        feedback_call = None
        for call in all_calls:
            blocks = call.kwargs.get("blocks") or (call.args[0] if call.args else None)
            if blocks and isinstance(blocks, list):
                for block in blocks:
                    if block.get("type") == "actions":
                        elements = block.get("elements", [])
                        action_ids = [e.get("action_id") for e in elements]
                        if "feedback_positive" in action_ids:
                            feedback_call = call
                            break
        assert feedback_call is not None, "No feedback buttons sent after query"
        thread_store.clear("T_Q_001")

    def test_query_feedback_state_has_pending(self):
        """After query + feedback, thread state should have feedback_pending."""
        from app.handlers.common import _handle_query, thread_store

        say = MagicMock()
        _handle_query(
            {"query_type": "stock"},
            thread_ts="T_Q_002",
            say=say,
            user_id="U123",
            language="tr",
        )
        state = thread_store.get("T_Q_002")
        assert state is not None
        assert state.get("feedback_pending") is True
        thread_store.clear("T_Q_002")

    def test_query_feedback_state_has_operation(self):
        """Query feedback state should record operation as 'query'."""
        from app.handlers.common import _handle_query, thread_store

        say = MagicMock()
        _handle_query(
            {"query_type": "stock"},
            thread_ts="T_Q_003",
            say=say,
            user_id="U123",
            language="tr",
        )
        state = thread_store.get("T_Q_003")
        assert state is not None
        assert state.get("operation") == "query"
        thread_store.clear("T_Q_003")


class TestFeedbackAfterCancel:
    """Feedback buttons should appear after cancel/skip ends an interaction."""

    def test_single_cancel_sends_feedback(self):
        """After cancelling a single operation, feedback buttons should be sent."""
        from app.handlers.common import thread_store

        thread_store.set("ts_cancel_001", {
            "operation": "log_support",
            "user_id": "U_CANCEL",
            "data": {"site_id": "MIG-TR-01"},
            "raw_message": "test",
            "sender_name": "Batu",
            "language": "tr",
        })

        say = MagicMock()
        body = {
            "message": {"thread_ts": "ts_cancel_001"},
            "user": {"id": "U_CANCEL"},
            "channel": {"id": "C001"},
        }

        # Simulate cancel action
        from app.handlers.actions import register
        from unittest.mock import MagicMock as MM
        app_mock = MM()
        handlers = {}

        def capture_action(action_id):
            def decorator(fn):
                handlers[action_id] = fn
                return fn
            return decorator

        app_mock.action = capture_action
        register(app_mock)

        handlers["cancel_action"](lambda: None, body, say)

        # Find feedback buttons in say calls
        feedback_found = False
        for call in say.call_args_list:
            blocks = call.kwargs.get("blocks")
            if blocks and isinstance(blocks, list):
                for block in blocks:
                    if block.get("type") == "actions":
                        action_ids = [e.get("action_id") for e in block.get("elements", [])]
                        if "feedback_positive" in action_ids:
                            feedback_found = True
        assert feedback_found, "No feedback buttons sent after cancel"
        thread_store.clear("ts_cancel_001")

    def test_chain_all_skipped_sends_feedback(self):
        """After skipping all chain steps, feedback buttons should be sent."""
        from app.handlers.common import thread_store

        thread_store.set("ts_cancel_002", {
            "operation": "update_hardware",
            "user_id": "U_CANCEL",
            "data": {"site_id": "MIG-TR-01"},
            "raw_message": "test",
            "sender_name": "Batu",
            "language": "tr",
            "chain_steps": ["create_site", "update_hardware"],
            "pending_operations": [],
            "completed_operations": [],
            "skipped_operations": ["create_site"],
            "current_step": 2,
            "total_steps": 2,
        })

        say = MagicMock()
        body = {
            "message": {"thread_ts": "ts_cancel_002"},
            "user": {"id": "U_CANCEL"},
            "channel": {"id": "C001"},
        }

        from app.handlers.actions import register
        from unittest.mock import MagicMock as MM
        app_mock = MM()
        handlers = {}

        def capture_action(action_id):
            def decorator(fn):
                handlers[action_id] = fn
                return fn
            return decorator

        app_mock.action = capture_action
        register(app_mock)

        handlers["cancel_action"](lambda: None, body, say)

        feedback_found = False
        for call in say.call_args_list:
            blocks = call.kwargs.get("blocks")
            if blocks and isinstance(blocks, list):
                for block in blocks:
                    if block.get("type") == "actions":
                        action_ids = [e.get("action_id") for e in block.get("elements", [])]
                        if "feedback_positive" in action_ids:
                            feedback_found = True
        assert feedback_found, "No feedback buttons sent after all-skipped chain"
        thread_store.clear("ts_cancel_002")

    def test_cancel_feedback_state_stored(self):
        """After cancel, thread state should have feedback_pending."""
        from app.handlers.common import thread_store

        thread_store.set("ts_cancel_003", {
            "operation": "log_support",
            "user_id": "U_CANCEL",
            "data": {"site_id": "MIG-TR-01"},
            "raw_message": "test",
            "sender_name": "Batu",
            "language": "tr",
        })

        say = MagicMock()
        body = {
            "message": {"thread_ts": "ts_cancel_003"},
            "user": {"id": "U_CANCEL"},
            "channel": {"id": "C001"},
        }

        from app.handlers.actions import register
        from unittest.mock import MagicMock as MM
        app_mock = MM()
        handlers = {}

        def capture_action(action_id):
            def decorator(fn):
                handlers[action_id] = fn
                return fn
            return decorator

        app_mock.action = capture_action
        register(app_mock)

        handlers["cancel_action"](lambda: None, body, say)

        state = thread_store.get("ts_cancel_003")
        assert state is not None
        assert state.get("feedback_pending") is True
        thread_store.clear("ts_cancel_003")


class TestFeedbackThreadState:
    """Test that feedback state is properly stored in thread store."""

    def test_feedback_pending_state_stored(self):
        from app.handlers.common import thread_store

        # After a write + feedback buttons shown, store feedback context
        thread_store.set("ts_fb_001", {
            "feedback_pending": True,
            "operation": "log_support",
            "user_id": "U123",
            "data": {"site_id": "MIG-TR-01"},
            "ticket_id": "SUP-003",
            "raw_message": "bugün gittim...",
            "sender_name": "Batu",
        })

        state = thread_store.get("ts_fb_001")
        assert state is not None
        assert state["feedback_pending"] is True

        thread_store.clear("ts_fb_001")

    def test_negative_feedback_awaiting_response(self):
        from app.handlers.common import thread_store

        # After 👎 clicked, store state awaiting user explanation
        thread_store.set("ts_fb_002", {
            "feedback_awaiting_response": True,
            "operation": "log_support",
            "user_id": "U123",
            "data": {"site_id": "MIG-TR-01"},
            "ticket_id": "SUP-003",
            "raw_message": "bugün gittim...",
            "sender_name": "Batu",
        })

        state = thread_store.get("ts_fb_002")
        assert state is not None
        assert state["feedback_awaiting_response"] is True

        thread_store.clear("ts_fb_002")


# --- Helpers ---

def _blocks_to_text(blocks: list[dict]) -> str:
    parts = []
    for block in blocks:
        if "text" in block:
            t = block["text"]
            if isinstance(t, dict):
                parts.append(t.get("text", ""))
            else:
                parts.append(str(t))
        for field in block.get("fields", []):
            if isinstance(field, dict):
                parts.append(field.get("text", ""))
    return "\n".join(parts)


def _find_actions_block(blocks: list[dict]) -> dict | None:
    for block in blocks:
        if block.get("type") == "actions":
            return block
    return None
