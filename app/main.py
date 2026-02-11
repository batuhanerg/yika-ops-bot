"""Entry point — Slack Bolt app initialization and route registration."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from app.handlers import actions, mentions, messages
from app.utils.formatters import format_help_text

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

    logger.info("Mustafa bot initialized")
    return app


def main() -> None:
    """Run the app with HTTP server (for Cloud Run / ngrok)."""
    app = create_app()
    port = int(os.environ.get("PORT", "8080"))
    logger.info("Starting Mustafa on port %d", port)
    app.start(port=port)


if __name__ == "__main__":
    main()
