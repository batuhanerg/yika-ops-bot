"""Environment configuration and constants."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def get_anthropic_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")
    return key


def get_slack_bot_token() -> str:
    return os.environ.get("SLACK_BOT_TOKEN", "")


def get_slack_signing_secret() -> str:
    return os.environ.get("SLACK_SIGNING_SECRET", "")


def get_google_sheet_id() -> str:
    return os.environ.get("GOOGLE_SHEET_ID", "")


def get_google_service_account_json() -> str:
    return os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
