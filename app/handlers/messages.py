"""Message handler — DMs and thread replies with active state."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.handlers.common import process_message, thread_store

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
