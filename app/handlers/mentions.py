"""@mustafa mention handler in channels."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from app.handlers.common import process_message

if TYPE_CHECKING:
    from slack_bolt import App

logger = logging.getLogger(__name__)


def register(app: App) -> None:
    """Register the app_mention event handler."""

    @app.event("app_mention")
    def handle_mention(event: dict, say, client) -> None:
        text = event.get("text", "")
        # Strip the @mention tag
        text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
        user_id = event.get("user", "")
        channel = event.get("channel", "")
        thread_ts = event.get("thread_ts") or event.get("ts", "")

        event_ts = event.get("ts", "")
        logger.info("Mention from %s in %s: %s", user_id, channel, text[:80])
        process_message(
            text=text,
            user_id=user_id,
            channel=channel,
            thread_ts=thread_ts,
            say=say,
            client=client,
            event_ts=event_ts,
        )
