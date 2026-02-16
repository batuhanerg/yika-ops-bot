"""Tests for report thread reply handling and feedback (Item 3, Session 7).

TDD: tests written BEFORE implementation changes.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.handlers.common import process_message, thread_store


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_thread_store():
    """Clear thread store before each test."""
    thread_store._threads.clear()
    yield
    thread_store._threads.clear()


@pytest.fixture
def report_thread_state():
    """State stored when a weekly report is posted."""
    return {
        "report_thread": True,
        "report_type": "weekly",
        "user_id": "system",
        "feedback_pending": True,
    }


@pytest.fixture
def aging_thread_state():
    """State stored when a daily aging alert is posted."""
    return {
        "report_thread": True,
        "report_type": "aging",
        "user_id": "system",
        "feedback_pending": True,
    }


# ===========================================================================
# Thread Reply Tests
# ===========================================================================


class TestReportThreadReplies:
    """Replies to report threads are processed as normal operations."""

    @patch("app.handlers.common.get_claude")
    @patch("app.handlers.common.get_sheets")
    def test_reply_to_report_thread_processed(
        self, mock_get_sheets, mock_get_claude, report_thread_state,
    ):
        """A reply to a report thread is processed as a standalone operation."""
        # Set up report thread state
        thread_ts = "1234567890.123456"
        thread_store.set(thread_ts, report_thread_state)

        # Mock Claude to return a parsed result
        mock_claude = MagicMock()
        from app.models.operations import ParseResult
        mock_claude.parse_message.return_value = ParseResult(
            operation="update_implementation",
            data={"site_id": "EST-TR-01", "internet_provider": "ERG Controls", "ssid": "deneme"},
            missing_fields=[],
            language="tr",
        )
        mock_get_claude.return_value = mock_claude

        # Mock sheets
        mock_sheets = MagicMock()
        mock_sheets.read_sites.return_value = [
            {"Site ID": "EST-TR-01", "Customer": "Test", "City": "Istanbul",
             "Country": "TR", "Facility Type": "Food", "Contract Status": "Active"},
        ]
        mock_get_sheets.return_value = mock_sheets

        say = MagicMock()
        client = MagicMock()
        client.users_info.return_value = {"user": {"profile": {"display_name": "Batu"}}}

        # Process a reply to the report thread
        process_message(
            text="EST-TR-01 internet provider ERG Controls, SSID deneme",
            user_id="U123",
            channel="C_TECHOPS",
            thread_ts=thread_ts,
            say=say,
            client=client,
            event_ts="1234567891.000001",
        )

        # Claude should have been called to parse the message
        mock_claude.parse_message.assert_called_once()
        # A confirmation should have been shown (say was called)
        assert say.call_count >= 1

    def test_report_state_allows_thread_reply_routing(self, report_thread_state):
        """Thread store has state for report, so message handler routes it."""
        thread_ts = "1234567890.123456"
        thread_store.set(thread_ts, report_thread_state)

        state = thread_store.get(thread_ts)
        assert state is not None
        assert state.get("report_thread") is True


# ===========================================================================
# Feedback Tests
# ===========================================================================


class TestReportFeedback:
    """Feedback buttons on reports work correctly."""

    def test_positive_feedback_replies_in_thread(self, report_thread_state):
        """👍 on report → thank you reply in thread."""
        from app.handlers.actions import register
        from slack_bolt import App

        thread_ts = "1234567890.123456"
        thread_store.set(thread_ts, report_thread_state)

        # Build a minimal Bolt app with action handlers
        app = MagicMock(spec=App)
        handlers = {}

        def mock_action(action_id):
            def decorator(func):
                handlers[action_id] = func
                return func
            return decorator

        app.action = mock_action
        register(app)

        say = MagicMock()
        client = MagicMock()
        body = {
            "message": {"ts": thread_ts},
            "user": {"id": "U123"},
            "channel": {"id": "C_TECHOPS"},
        }

        with patch("app.handlers.actions.get_sheets") as mock_get_sheets:
            mock_sheets = MagicMock()
            mock_get_sheets.return_value = mock_sheets

            # Simulate clicking 👍
            handlers["feedback_positive"](
                ack=MagicMock(), body=body, say=say, client=client,
            )

            # Should reply with thank you
            say.assert_called()
            reply_text = say.call_args[1].get("text", "") if say.call_args[1] else say.call_args[0][0] if say.call_args[0] else ""
            # Check any call contains the thank you message
            found = False
            for call in say.call_args_list:
                text = call[1].get("text", "") if call[1] else ""
                if "Teşekkürler" in text:
                    found = True
                    break
            assert found, f"Expected 'Teşekkürler' in say calls: {say.call_args_list}"

    def test_positive_feedback_logged_with_report_type(self, report_thread_state):
        """👍 on report → logged to Feedback with operation 'report'."""
        from app.handlers.actions import register
        from slack_bolt import App

        thread_ts = "1234567890.123456"
        thread_store.set(thread_ts, report_thread_state)

        app = MagicMock(spec=App)
        handlers = {}

        def mock_action(action_id):
            def decorator(func):
                handlers[action_id] = func
                return func
            return decorator

        app.action = mock_action
        register(app)

        say = MagicMock()
        client = MagicMock()
        body = {
            "message": {"ts": thread_ts},
            "user": {"id": "U123"},
            "channel": {"id": "C_TECHOPS"},
        }

        with patch("app.handlers.actions.get_sheets") as mock_get_sheets:
            mock_sheets = MagicMock()
            mock_get_sheets.return_value = mock_sheets

            handlers["feedback_positive"](
                ack=MagicMock(), body=body, say=say, client=client,
            )

            # Should log to feedback with operation="report"
            mock_sheets.append_feedback.assert_called_once()
            call_kwargs = mock_sheets.append_feedback.call_args[1]
            assert call_kwargs["operation"] == "report"

    def test_negative_feedback_asks_followup(self, report_thread_state):
        """👎 on report → ask 'Nasıl daha iyi yapabilirdim?'."""
        from app.handlers.actions import register
        from slack_bolt import App

        thread_ts = "1234567890.123456"
        thread_store.set(thread_ts, report_thread_state)

        app = MagicMock(spec=App)
        handlers = {}

        def mock_action(action_id):
            def decorator(func):
                handlers[action_id] = func
                return func
            return decorator

        app.action = mock_action
        register(app)

        say = MagicMock()
        client = MagicMock()
        body = {
            "message": {"ts": thread_ts},
            "user": {"id": "U123"},
            "channel": {"id": "C_TECHOPS"},
        }

        handlers["feedback_negative"](
            ack=MagicMock(), body=body, say=say, client=client,
        )

        # Should ask for follow-up
        found = False
        for call in say.call_args_list:
            text = call[1].get("text", "") if call[1] else ""
            if "Nasıl daha iyi yapabilirdim" in text:
                found = True
                break
        assert found, f"Expected follow-up question in say calls: {say.call_args_list}"

        # Thread state should be updated to await response
        state = thread_store.get(thread_ts)
        assert state is not None
        assert state.get("feedback_awaiting_response") is True

    def test_negative_feedback_text_captured_as_report(self, report_thread_state):
        """After 👎 + follow-up text → logged with operation='report', not ''."""
        from app.handlers.messages import register as register_messages
        from slack_bolt import App

        thread_ts = "1234567890.123456"
        # Simulate the state after 👎 was clicked (feedback_awaiting_response=True)
        thread_store.set(thread_ts, {
            **report_thread_state,
            "feedback_pending": False,
            "feedback_awaiting_response": True,
        })

        app = MagicMock(spec=App)
        handlers = {}

        def mock_event(event_type):
            def decorator(func):
                handlers[event_type] = func
                return func
            return decorator

        app.event = mock_event
        register_messages(app)

        say = MagicMock()
        client = MagicMock()
        event = {
            "text": "Rapor daha detaylı olabilir",
            "user": "U123",
            "channel": "C_TECHOPS",
            "channel_type": "channel",
            "thread_ts": thread_ts,
            "ts": "1234567891.000001",
        }

        with patch("app.handlers.messages.get_sheets") as mock_get_sheets:
            mock_sheets = MagicMock()
            mock_get_sheets.return_value = mock_sheets

            handlers["message"](event=event, say=say, client=client)

            mock_sheets.append_feedback.assert_called_once()
            call_kwargs = mock_sheets.append_feedback.call_args[1]
            assert call_kwargs["operation"] == "report"
            assert call_kwargs["expected_behavior"] == "Rapor daha detaylı olabilir"
            assert call_kwargs["rating"] == "negative"
