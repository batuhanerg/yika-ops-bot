"""Tests for Bug 12: Feedback button UX — replace buttons with static text after click.

After a user clicks 👍 or 👎, the original message's actions block should be replaced
with a static context block showing what was selected, using client.chat_update().
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from app.handlers.common import thread_store
from app.utils.formatters import format_feedback_buttons


# ---------------------------------------------------------------------------
# Helper: register action handlers and return them as a dict
# ---------------------------------------------------------------------------

def _register_handlers():
    """Register action handlers on a mock app and return handler dict."""
    from app.handlers.actions import register

    app_mock = MagicMock()
    handlers = {}

    def capture_action(action_id):
        def decorator(fn):
            handlers[action_id] = fn
            return fn
        return decorator

    app_mock.action = capture_action
    register(app_mock)
    return handlers


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _cleanup_threads():
    """Ensure thread store is clean before and after each test."""
    yield
    for key in ["ts_fb_update_001", "ts_fb_update_002", "ts_fb_update_003",
                "ts_fb_update_004", "ts_fb_update_005", "ts_fb_update_006",
                "ts_fb_update_007", "ts_fb_update_008", "ts_fb_update_009",
                "ts_fb_update_010", "ts_fb_update_011", "ts_fb_update_012"]:
        thread_store.clear(key)


def _make_feedback_body(thread_ts: str, message_ts: str, blocks: list[dict]) -> dict:
    """Build a Slack action body for feedback button click."""
    return {
        "message": {
            "ts": message_ts,
            "thread_ts": thread_ts,
            "blocks": blocks,
        },
        "user": {"id": "U_TEST"},
        "channel": {"id": "C_TEST"},
    }


def _set_feedback_state(thread_ts: str, **overrides) -> None:
    """Set up a standard feedback-pending thread state."""
    state = {
        "feedback_pending": True,
        "operation": "log_support",
        "user_id": "U_TEST",
        "data": {"site_id": "MIG-TR-01"},
        "ticket_id": "SUP-003",
        "raw_message": "bugün gittim...",
        "sender_name": "Batu",
        "language": "tr",
    }
    state.update(overrides)
    thread_store.set(thread_ts, state)


# ===========================================================================
# Core: button replacement on 👍 / 👎
# ===========================================================================


class TestFeedbackButtonReplacement:
    """After clicking 👍 or 👎, the original message buttons should be replaced with static text."""

    def test_positive_click_replaces_buttons_with_static_text(self):
        """👍 click calls client.chat_update with buttons replaced by static text."""
        handlers = _register_handlers()
        _set_feedback_state("ts_fb_update_001")

        original_blocks = format_feedback_buttons()
        body = _make_feedback_body("ts_fb_update_001", "msg_ts_001", original_blocks)
        say = MagicMock()
        client = MagicMock()

        with patch("app.handlers.actions.get_sheets") as mock_sheets:
            mock_sheets.return_value = MagicMock()
            handlers["feedback_positive"](lambda: None, body, say, client)

        client.chat_update.assert_called_once()
        call_kwargs = client.chat_update.call_args[1]
        assert call_kwargs["channel"] == "C_TEST"
        assert call_kwargs["ts"] == "msg_ts_001"

        updated_blocks = call_kwargs["blocks"]
        # No actions block should remain
        action_blocks = [b for b in updated_blocks if b.get("type") == "actions"]
        assert len(action_blocks) == 0, "Actions block should be removed after click"

        # Should contain the static feedback text
        all_text = _extract_all_text(updated_blocks)
        assert "👍" in all_text
        assert "Evet" in all_text

    def test_negative_click_replaces_buttons_with_static_text(self):
        """👎 click calls client.chat_update with buttons replaced by static text."""
        handlers = _register_handlers()
        _set_feedback_state("ts_fb_update_002")

        original_blocks = format_feedback_buttons()
        body = _make_feedback_body("ts_fb_update_002", "msg_ts_002", original_blocks)
        say = MagicMock()
        client = MagicMock()

        handlers["feedback_negative"](lambda: None, body, say, client)

        client.chat_update.assert_called_once()
        call_kwargs = client.chat_update.call_args[1]
        assert call_kwargs["channel"] == "C_TEST"
        assert call_kwargs["ts"] == "msg_ts_002"

        updated_blocks = call_kwargs["blocks"]
        action_blocks = [b for b in updated_blocks if b.get("type") == "actions"]
        assert len(action_blocks) == 0, "Actions block should be removed after click"

        all_text = _extract_all_text(updated_blocks)
        assert "👎" in all_text
        assert "Hayır" in all_text

    def test_original_content_blocks_preserved(self):
        """Non-actions blocks from the original message are kept intact."""
        handlers = _register_handlers()
        _set_feedback_state("ts_fb_update_003")

        # Build blocks with a section block (question) + actions block (buttons)
        original_blocks = format_feedback_buttons()
        assert len(original_blocks) == 2  # section + actions
        body = _make_feedback_body("ts_fb_update_003", "msg_ts_003", original_blocks)
        say = MagicMock()
        client = MagicMock()

        with patch("app.handlers.actions.get_sheets") as mock_sheets:
            mock_sheets.return_value = MagicMock()
            handlers["feedback_positive"](lambda: None, body, say, client)

        updated_blocks = client.chat_update.call_args[1]["blocks"]
        # The original section block (question text) should still be there
        section_blocks = [b for b in updated_blocks if b.get("type") == "section"]
        assert len(section_blocks) >= 1
        # Check the question is preserved
        question_text = section_blocks[0]["text"]["text"]
        assert "Doğru kaydedildi mi?" in question_text

    def test_no_actions_block_remains_after_update(self):
        """No interactive actions block should remain in the updated message."""
        handlers = _register_handlers()
        _set_feedback_state("ts_fb_update_004")

        original_blocks = format_feedback_buttons()
        body = _make_feedback_body("ts_fb_update_004", "msg_ts_004", original_blocks)
        say = MagicMock()
        client = MagicMock()

        with patch("app.handlers.actions.get_sheets") as mock_sheets:
            mock_sheets.return_value = MagicMock()
            handlers["feedback_positive"](lambda: None, body, say, client)

        updated_blocks = client.chat_update.call_args[1]["blocks"]
        for block in updated_blocks:
            assert block.get("type") != "actions", \
                f"Found leftover actions block: {block}"


class TestFeedbackButtonUpdateFailure:
    """chat_update failure should not crash the feedback response flow."""

    def test_chat_update_failure_does_not_raise(self):
        """If chat_update fails, feedback response is still sent and no exception raised."""
        handlers = _register_handlers()
        _set_feedback_state("ts_fb_update_005")

        original_blocks = format_feedback_buttons()
        body = _make_feedback_body("ts_fb_update_005", "msg_ts_005", original_blocks)
        say = MagicMock()
        client = MagicMock()
        client.chat_update.side_effect = Exception("Slack API error: message_not_found")

        with patch("app.handlers.actions.get_sheets") as mock_sheets:
            mock_sheets.return_value = MagicMock()
            # Should not raise
            handlers["feedback_positive"](lambda: None, body, say, client)

        # The say() response should still have been called
        assert say.called, "Feedback response should still be sent even if chat_update fails"

    def test_chat_update_failure_logged(self, caplog):
        """chat_update failure is logged at error/warning level."""
        handlers = _register_handlers()
        _set_feedback_state("ts_fb_update_006")

        original_blocks = format_feedback_buttons()
        body = _make_feedback_body("ts_fb_update_006", "msg_ts_006", original_blocks)
        say = MagicMock()
        client = MagicMock()
        client.chat_update.side_effect = Exception("Slack API error")

        with patch("app.handlers.actions.get_sheets") as mock_sheets:
            mock_sheets.return_value = MagicMock()
            with caplog.at_level(logging.WARNING, logger="app.handlers.actions"):
                handlers["feedback_positive"](lambda: None, body, say, client)

        assert any("chat_update" in r.message.lower() or "button" in r.message.lower()
                    for r in caplog.records), \
            f"Expected a log about chat_update failure, got: {[r.message for r in caplog.records]}"

    def test_negative_chat_update_failure_still_sends_response(self):
        """If chat_update fails on 👎 click, the follow-up question is still sent."""
        handlers = _register_handlers()
        _set_feedback_state("ts_fb_update_007")

        original_blocks = format_feedback_buttons()
        body = _make_feedback_body("ts_fb_update_007", "msg_ts_007", original_blocks)
        say = MagicMock()
        client = MagicMock()
        client.chat_update.side_effect = Exception("Slack API error")

        handlers["feedback_negative"](lambda: None, body, say, client)

        # "Nasıl daha iyi yapabilirdim?" should still be sent
        say_texts = [str(c) for c in say.call_args_list]
        assert any("Nasıl daha iyi yapabilirdim" in t for t in say_texts), \
            "Negative feedback follow-up should still be sent"


# ===========================================================================
# Regression: existing feedback flows still work
# ===========================================================================


class TestFeedbackRegressions:
    """Verify existing feedback flows still work after adding button replacement."""

    def test_positive_feedback_still_sends_thank_you(self):
        """👍 still sends thank-you response (existing behavior preserved)."""
        handlers = _register_handlers()
        _set_feedback_state("ts_fb_update_008")

        original_blocks = format_feedback_buttons()
        body = _make_feedback_body("ts_fb_update_008", "msg_ts_008", original_blocks)
        say = MagicMock()
        client = MagicMock()

        with patch("app.handlers.actions.get_sheets") as mock_sheets:
            mock_sheets.return_value = MagicMock()
            handlers["feedback_positive"](lambda: None, body, say, client)

        say_texts = " ".join(str(c) for c in say.call_args_list)
        assert "Teşekkürler" in say_texts

    def test_negative_feedback_still_asks_follow_up(self):
        """👎 still asks 'Nasıl daha iyi yapabilirdim?' (existing behavior preserved)."""
        handlers = _register_handlers()
        _set_feedback_state("ts_fb_update_009")

        original_blocks = format_feedback_buttons()
        body = _make_feedback_body("ts_fb_update_009", "msg_ts_009", original_blocks)
        say = MagicMock()
        client = MagicMock()

        handlers["feedback_negative"](lambda: None, body, say, client)

        say_texts = " ".join(str(c) for c in say.call_args_list)
        assert "Nasıl daha iyi yapabilirdim" in say_texts

    def test_format_feedback_buttons_unchanged(self):
        """format_feedback_buttons() output is unchanged — no modifications to button creation."""
        blocks = format_feedback_buttons()
        assert len(blocks) == 2
        assert blocks[0]["type"] == "section"
        assert blocks[1]["type"] == "actions"
        assert len(blocks[1]["elements"]) == 2
        assert blocks[1]["elements"][0]["action_id"] == "feedback_positive"
        assert blocks[1]["elements"][1]["action_id"] == "feedback_negative"

    def test_report_thread_positive_still_works(self):
        """Report thread feedback still works with button replacement."""
        handlers = _register_handlers()
        _set_feedback_state("ts_fb_update_010", report_thread=True, operation="report")

        original_blocks = format_feedback_buttons(context="report")
        body = _make_feedback_body("ts_fb_update_010", "msg_ts_010", original_blocks)
        say = MagicMock()
        client = MagicMock()

        with patch("app.handlers.actions.get_sheets") as mock_sheets:
            mock_sheets.return_value = MagicMock()
            handlers["feedback_positive"](lambda: None, body, say, client)

        # Should update buttons
        client.chat_update.assert_called_once()
        # Should send thank-you
        say_texts = " ".join(str(c) for c in say.call_args_list)
        assert "Teşekkürler" in say_texts

    def test_feedback_buttons_appended_after_query(self):
        """Feedback buttons are still present after query responses (not affected by this change)."""
        blocks = format_feedback_buttons(context="query")
        actions = [b for b in blocks if b.get("type") == "actions"]
        assert len(actions) == 1
        action_ids = [e["action_id"] for e in actions[0]["elements"]]
        assert "feedback_positive" in action_ids
        assert "feedback_negative" in action_ids

    def test_feedback_context_write_question_unchanged(self):
        """Write context question unchanged."""
        blocks = format_feedback_buttons(context="write")
        assert blocks[0]["text"]["text"] == "Doğru kaydedildi mi?"

    def test_feedback_context_query_question_unchanged(self):
        """Query context question unchanged."""
        blocks = format_feedback_buttons(context="query")
        assert blocks[0]["text"]["text"] == "Faydalı oldu mu?"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_all_text(blocks: list[dict]) -> str:
    """Extract all text content from blocks for assertion."""
    parts = []
    for block in blocks:
        if "text" in block:
            t = block["text"]
            if isinstance(t, dict):
                parts.append(t.get("text", ""))
            else:
                parts.append(str(t))
        for elem in block.get("elements", []):
            if isinstance(elem, dict) and "text" in elem:
                parts.append(elem["text"] if isinstance(elem["text"], str) else elem["text"].get("text", ""))
    return " ".join(parts)
