"""Entry point — Slack Bolt app initialization and route registration."""

from __future__ import annotations

import logging
import os
import threading

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from app.handlers import actions, mentions, messages
from app.utils.formatters import format_help_text
from app.version import __version__, RELEASE_NOTES

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> App:
    """Create and configure the Slack Bolt app."""
    app = App(
        token=os.environ["SLACK_BOT_TOKEN"],
        signing_secret=os.environ["SLACK_SIGNING_SECRET"],
    )

    # Register handlers
    mentions.register(app)
    messages.register(app)
    actions.register(app)

    # /mustafa yardım slash command
    @app.command("/mustafa")
    def handle_slash_command(ack, command, say) -> None:
        ack()
        text = command.get("text", "").strip().lower()
        if text in ("yardım", "yardim", "help", ""):
            say(blocks=format_help_text(), channel=command["channel_id"])
        else:
            say(
                text="Bilinmeyen komut. `/mustafa yardım` yazarak kullanım kılavuzunu görebilirsiniz.",
                channel=command["channel_id"],
            )

    logger.info("Mustafa bot v%s initialized", __version__)
    return app


def _announce_version(app: App) -> None:
    """Post a version announcement if this version hasn't been announced yet."""
    channel = os.environ.get("SLACK_ANNOUNCE_CHANNEL", "")
    if not channel:
        logger.info("SLACK_ANNOUNCE_CHANNEL not set, skipping version announcement")
        return

    try:
        # Check if we already announced this version via Audit Log
        from app.handlers.common import get_sheets
        sheets = get_sheets()
        ws = sheets._ws("Audit Log")
        all_values = ws.get_all_values()
        for row in all_values[1:]:
            if len(row) >= 6 and row[2] == "DEPLOY" and f"v{__version__}" in row[5]:
                logger.info("Version v%s already announced, skipping", __version__)
                return

        # Build the announcement message
        notes = "\n".join(f"• {note}" for note in RELEASE_NOTES)
        message = f"Yeni versiyona geçtim: *v{__version__}* 🚀\n\n{notes}"

        app.client.chat_postMessage(channel=channel, text=message)

        # Log the deploy to Audit Log
        sheets.append_audit_log(
            user="system",
            operation="DEPLOY",
            target_tab="—",
            site_id="",
            summary=f"Deployed v{__version__}",
            raw_message="",
        )
        logger.info("Announced v%s to %s", __version__, channel)

    except Exception:
        logger.exception("Failed to announce version")


def main() -> None:
    """Run the app with HTTP server (for Cloud Run / ngrok)."""
    app = create_app()

    # Announce version in background (don't block startup)
    threading.Thread(target=_announce_version, args=(app,), daemon=True).start()

    port = int(os.environ.get("PORT", "8080"))
    logger.info("Starting Mustafa v%s on port %d", __version__, port)
    app.start(port=port)


if __name__ == "__main__":
    main()
