"""Message handler — DMs and thread replies with active state."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.handlers.common import get_sheets, process_message, thread_store

if TYPE_CHECKING:
    from slack_bolt import App

logger = logging.getLogger(__name__)


def register(app: App) -> None:
    """Register the message event handler."""

    @app.event("message")
    def handle_message(event: dict, say, client) -> None:
        # Skip bot messages and subtypes (joins, edits, etc.)
        if event.get("bot_id") or event.get("subtype"):
            return

        text = event.get("text", "")
        user_id = event.get("user", "")
        channel = event.get("channel", "")
        channel_type = event.get("channel_type", "")
        thread_ts = event.get("thread_ts") or event.get("ts", "")

        event_ts = event.get("ts", "")

        # Check for feedback response (after 👎 was clicked)
        if event.get("thread_ts"):
            state = thread_store.get(thread_ts)
            if state and state.get("feedback_awaiting_response"):
                logger.info("Feedback response from %s: %s", user_id, text[:80])
                try:
                    sheets = get_sheets()
                    sheets.append_feedback(
                        user=state.get("sender_name", "Unknown"),
                        operation=state.get("operation", ""),
                        site_id=state.get("data", {}).get("site_id", ""),
                        ticket_id=state.get("ticket_id", ""),
                        rating="negative",
                        expected_behavior=text,
                        original_message=state.get("raw_message", ""),
                    )
                    say(text="Teşekkürler, geri bildiriminiz kaydedildi.", thread_ts=thread_ts)
                except Exception:
                    logger.exception("Feedback write error")
                    say(text="Geri bildirim kaydedilemedi, lütfen tekrar deneyin.", thread_ts=thread_ts)
                thread_store.clear(thread_ts)
                return

        # DMs: always process
        if channel_type == "im":
            logger.info("DM from %s: %s", user_id, text[:80])
            process_message(
                text=text,
                user_id=user_id,
                channel=channel,
                thread_ts=thread_ts,
                say=say,
                client=client,
                event_ts=event_ts,
            )
            return

        # Channel thread replies: only process if there's active thread state
        # (this handles follow-ups without @mustafa in an existing conversation)
        if event.get("thread_ts"):
            state = thread_store.get(thread_ts)
            if state:
                logger.info("Thread reply from %s: %s", user_id, text[:80])
                process_message(
                    text=text,
                    user_id=user_id,
                    channel=channel,
                    thread_ts=thread_ts,
                    say=say,
                    client=client,
                    event_ts=event_ts,
                )
