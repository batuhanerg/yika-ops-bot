"""Entry point — Slack Bolt app initialization and route registration."""

from __future__ import annotations

import logging
import os
import threading

from dotenv import load_dotenv
from flask import Flask, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

from app.handlers import actions, mentions, messages
from app.routes.cron import cron_bp
from app.utils.formatters import format_help_text
from app.version import (
    __version__,
    RELEASE_NOTES,
    format_deploy_message,
    get_release_notes_for_current_version,
)

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


def create_flask_app() -> Flask:
    """Create a Flask app that wraps Bolt and adds cron routes."""
    bolt_app = create_app()
    handler = SlackRequestHandler(bolt_app)

    flask_app = Flask(__name__)

    # Health check for Cloud Run
    @flask_app.route("/health", methods=["GET"])
    @flask_app.route("/", methods=["GET"])
    def health():
        return "ok", 200

    # Slack events — all Bolt traffic goes through root path
    @flask_app.route("/slack/events", methods=["POST"])
    @flask_app.route("/", methods=["POST"])
    def slack_events():
        return handler.handle(request)

    # Cron routes
    flask_app.register_blueprint(cron_bp)

    return flask_app


def _announce_version(bolt_app: App) -> None:
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

        # Build the announcement message — prefer CHANGELOG RELEASE_NOTES
        changelog_notes = get_release_notes_for_current_version()
        message = format_deploy_message(
            __version__,
            changelog_notes,
            fallback_bullets=RELEASE_NOTES,
        )

        bolt_app.client.chat_postMessage(channel=channel, text=message)

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
    """Run the app with Flask HTTP server (for Cloud Run / ngrok)."""
    flask_app = create_flask_app()

    # Announce version in background (don't block startup)
    # Access the Bolt app from the Flask context isn't needed for announce —
    # it uses its own Slack client via Bolt.
    bolt_app = create_app()
    threading.Thread(target=_announce_version, args=(bolt_app,), daemon=True).start()

    port = int(os.environ.get("PORT", "8080"))
    logger.info("Starting Mustafa v%s on port %d (Flask)", __version__, port)
    flask_app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
