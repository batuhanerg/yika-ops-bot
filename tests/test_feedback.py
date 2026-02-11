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
