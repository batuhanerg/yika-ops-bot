"""HTTP endpoints for Cloud Scheduler cron jobs.

POST /cron/weekly-report  — weekly data quality report
POST /cron/daily-aging    — daily aging ticket alert
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from flask import Blueprint, jsonify, request

from app.handlers.common import get_sheets, thread_store
from app.services.scheduled_reports import (
    generate_daily_aging_alert,
    generate_weekly_report,
)

logger = logging.getLogger(__name__)

cron_bp = Blueprint("cron", __name__, url_prefix="/cron")

# ---------------------------------------------------------------------------
# Slack client accessor (lazy — avoids import-time env var requirement)
# ---------------------------------------------------------------------------

_slack_client = None


def _get_slack_client():
    """Get the Slack WebClient instance."""
    global _slack_client
    if _slack_client is None:
        from slack_sdk import WebClient
        _slack_client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    return _slack_client


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _verify_cron_auth() -> bool:
    """Verify the request comes from Cloud Scheduler."""
    secret = os.environ.get("CRON_SECRET", "")
    if not secret:
        logger.warning("CRON_SECRET not configured — rejecting cron request")
        return False
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {secret}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@cron_bp.route("/weekly-report", methods=["POST"])
def weekly_report():
    """Generate and post the weekly data quality report."""
    if not _verify_cron_auth():
        return jsonify({"error": "unauthorized"}), 401

    try:
        sheets = get_sheets()
        sites = sheets.read_sites()
        hardware = sheets.read_hardware()
        support = sheets.read_support_log()
        implementation = sheets.read_all_implementation()
        stock = sheets.read_stock()

        # Read previous snapshot for resolution tracking
        prev_snapshot = None
        prev_json = sheets.read_latest_audit_by_operation("WEEKLY_REPORT_SNAPSHOT")
        if prev_json:
            try:
                prev_snapshot = json.loads(prev_json)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Could not parse previous snapshot")

        blocks, fallback = generate_weekly_report(
            sites=sites,
            hardware=hardware,
            support=support,
            implementation=implementation,
            stock=stock,
            prev_snapshot=prev_snapshot,
        )

        channel = os.environ.get("SLACK_CHANNEL_ID", "")
        client = _get_slack_client()
        result = client.chat_postMessage(
            channel=channel,
            blocks=blocks,
            text=fallback,
        )

        # Store thread_ts so replies are handled by Mustafa
        msg_ts = result["ts"]
        thread_store.set(msg_ts, {
            "report_thread": True,
            "report_type": "weekly",
            "user_id": "system",
            "feedback_pending": True,
        })

        # Audit log
        sheets.append_audit_log(
            user="system",
            operation="SCHEDULED_REPORT",
            target_tab="—",
            site_id="",
            summary=fallback[:200],
            raw_message="",
        )

        # Store current issue snapshot for next week's resolution tracking
        from app.services.data_quality import find_missing_data
        current_issues = find_missing_data(
            sites=sites, hardware=hardware, support=support,
            implementation=implementation, stock=stock,
        )
        snapshot = [
            {"site_id": i["site_id"], "tab": i.get("tab", ""), "field": i.get("field", ""), "severity": i.get("severity", "")}
            for i in current_issues
            if i.get("severity") in ("must", "important") and i.get("field") != "Aging"
        ]
        sheets.append_audit_log(
            user="system",
            operation="WEEKLY_REPORT_SNAPSHOT",
            target_tab="—",
            site_id="",
            summary=json.dumps(snapshot, ensure_ascii=False),
            raw_message="",
        )

        logger.info("Weekly report posted to %s (ts=%s)", channel, msg_ts)
        return jsonify({"ok": True, "ts": msg_ts}), 200

    except Exception:
        logger.exception("Failed to generate/post weekly report")
        return jsonify({"error": "internal"}), 500


@cron_bp.route("/daily-aging", methods=["POST"])
def daily_aging():
    """Generate and post the daily aging alert (if any)."""
    if not _verify_cron_auth():
        return jsonify({"error": "unauthorized"}), 401

    try:
        sheets = get_sheets()
        support = sheets.read_support_log()

        result = generate_daily_aging_alert(support=support)
        if result is None:
            logger.info("No aging tickets — skipping daily alert")
            return jsonify({"ok": True, "skipped": True}), 200

        blocks, fallback = result

        channel = os.environ.get("SLACK_CHANNEL_ID", "")
        client = _get_slack_client()
        msg = client.chat_postMessage(
            channel=channel,
            blocks=blocks,
            text=fallback,
        )

        msg_ts = msg["ts"]
        thread_store.set(msg_ts, {
            "report_thread": True,
            "report_type": "aging",
            "user_id": "system",
            "feedback_pending": True,
        })

        sheets.append_audit_log(
            user="system",
            operation="SCHEDULED_AGING",
            target_tab="Support Log",
            site_id="",
            summary=fallback[:200],
            raw_message="",
        )

        logger.info("Daily aging alert posted to %s (ts=%s)", channel, msg_ts)
        return jsonify({"ok": True, "ts": msg_ts}), 200

    except Exception:
        logger.exception("Failed to generate/post daily aging alert")
        return jsonify({"error": "internal"}), 500
