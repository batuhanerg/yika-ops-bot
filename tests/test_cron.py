"""Tests for cron HTTP endpoints (Item 2, Session 7).

TDD: tests written BEFORE implementation.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def cron_secret(monkeypatch):
    """Set up the CRON_SECRET env var."""
    monkeypatch.setenv("CRON_SECRET", "test-secret-123")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C_TECHOPS")
    return "test-secret-123"


@pytest.fixture
def mock_sheets():
    """Mock SheetsService with sample data."""
    sheets = MagicMock()
    sheets.read_sites.return_value = [
        {
            "Site ID": "ASM-TR-01", "Customer": "Anadolu", "City": "Gebze",
            "Country": "TR", "Facility Type": "Healthcare",
            "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
            "Address": "Gebze Mah.", "Go-live Date": "2024-01-01",
            "Dashboard Link": "http://dash", "Whatsapp Group": "https://wa.me/grp",
        },
    ]
    sheets.read_hardware.return_value = [
        {
            "Site ID": "ASM-TR-01", "Device Type": "Tag", "Qty": 20,
            "HW Version": "1.0", "FW Version": "2.4",
            "Last Verified": (date.today() - timedelta(days=5)).isoformat(),
        },
    ]
    sheets.read_support_log.return_value = []
    sheets.read_all_implementation.return_value = [
        {
            "Site ID": "ASM-TR-01", "Internet Provider": "ERG Controls",
            "SSID": "Net", "Password": "pass",
            "Gateway placement": "Office",
            "Charging dock placement": "Office",
            "Dispenser anchor placement": "Washroom",
            "Handwash time": "20", "Tag buzzer/vibration": "On",
            "Entry time": "5", "Dispenser anchor power type": "USB",
            "Tag clean-to-red timeout": "30",
            "Last Verified": (date.today() - timedelta(days=5)).isoformat(),
        },
    ]
    sheets.read_stock.return_value = []
    return sheets


@pytest.fixture
def mock_sheets_with_aging():
    """Mock SheetsService with aging tickets."""
    sheets = MagicMock()
    old_date = (date.today() - timedelta(days=5)).isoformat()
    sheets.read_sites.return_value = [
        {
            "Site ID": "ASM-TR-01", "Customer": "Anadolu", "City": "Gebze",
            "Country": "TR", "Facility Type": "Healthcare",
            "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
        },
    ]
    sheets.read_hardware.return_value = []
    sheets.read_support_log.return_value = [
        {
            "Site ID": "ASM-TR-01", "Ticket ID": "SUP-001",
            "Status": "Open", "Received Date": old_date,
            "Issue Summary": "Gateway offline", "Devices Affected": "",
        },
    ]
    sheets.read_all_implementation.return_value = []
    sheets.read_stock.return_value = []
    return sheets


@pytest.fixture
def flask_client(cron_secret, mock_sheets):
    """Flask test client with mocked dependencies."""
    with patch("app.routes.cron.get_sheets", return_value=mock_sheets), \
         patch("app.routes.cron._get_slack_client") as mock_slack:
        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {"ts": "1234567890.123456"}
        mock_slack.return_value = mock_client

        from app.routes.cron import cron_bp
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(cron_bp)
        yield app.test_client()


@pytest.fixture
def flask_client_with_aging(cron_secret, mock_sheets_with_aging):
    """Flask test client with aging ticket data."""
    with patch("app.routes.cron.get_sheets", return_value=mock_sheets_with_aging), \
         patch("app.routes.cron._get_slack_client") as mock_slack:
        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {"ts": "1234567890.123456"}
        mock_slack.return_value = mock_client

        from app.routes.cron import cron_bp
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(cron_bp)
        yield app.test_client()


# ===========================================================================
# Auth Tests
# ===========================================================================


class TestCronAuth:
    """Both endpoints reject requests without valid auth."""

    def test_weekly_rejects_no_auth(self, flask_client):
        resp = flask_client.post("/cron/weekly-report")
        assert resp.status_code == 401

    def test_daily_rejects_no_auth(self, flask_client):
        resp = flask_client.post("/cron/daily-aging")
        assert resp.status_code == 401

    def test_weekly_rejects_wrong_secret(self, flask_client):
        resp = flask_client.post(
            "/cron/weekly-report",
            headers={"Authorization": "Bearer wrong-secret"},
        )
        assert resp.status_code == 401

    def test_daily_rejects_wrong_secret(self, flask_client):
        resp = flask_client.post(
            "/cron/daily-aging",
            headers={"Authorization": "Bearer wrong-secret"},
        )
        assert resp.status_code == 401

    def test_weekly_accepts_valid_secret(self, flask_client):
        resp = flask_client.post(
            "/cron/weekly-report",
            headers={"Authorization": "Bearer test-secret-123"},
        )
        assert resp.status_code == 200

    def test_daily_accepts_valid_secret(self, flask_client):
        resp = flask_client.post(
            "/cron/daily-aging",
            headers={"Authorization": "Bearer test-secret-123"},
        )
        assert resp.status_code == 200


# ===========================================================================
# Weekly Report Endpoint Tests
# ===========================================================================


class TestWeeklyReportEndpoint:
    """POST /cron/weekly-report calls generate and posts to Slack."""

    def test_calls_generate_and_posts_to_slack(self, cron_secret, mock_sheets):
        with patch("app.routes.cron.get_sheets", return_value=mock_sheets), \
             patch("app.routes.cron._get_slack_client") as mock_slack:
            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = {"ts": "1234567890.123456"}
            mock_slack.return_value = mock_client

            from app.routes.cron import cron_bp
            from flask import Flask
            app = Flask(__name__)
            app.register_blueprint(cron_bp)
            client = app.test_client()

            resp = client.post(
                "/cron/weekly-report",
                headers={"Authorization": "Bearer test-secret-123"},
            )
            assert resp.status_code == 200
            mock_client.chat_postMessage.assert_called_once()
            call_kwargs = mock_client.chat_postMessage.call_args[1]
            assert call_kwargs["channel"] == "C_TECHOPS"
            assert "blocks" in call_kwargs
            assert "text" in call_kwargs

    def test_stores_thread_ts(self, cron_secret, mock_sheets):
        with patch("app.routes.cron.get_sheets", return_value=mock_sheets), \
             patch("app.routes.cron._get_slack_client") as mock_slack, \
             patch("app.routes.cron.thread_store") as mock_thread_store:
            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = {"ts": "1234567890.123456"}
            mock_slack.return_value = mock_client

            from app.routes.cron import cron_bp
            from flask import Flask
            app = Flask(__name__)
            app.register_blueprint(cron_bp)
            client = app.test_client()

            resp = client.post(
                "/cron/weekly-report",
                headers={"Authorization": "Bearer test-secret-123"},
            )
            assert resp.status_code == 200
            # thread_store.set should be called with the posted message's ts
            mock_thread_store.set.assert_called_once()
            call_args = mock_thread_store.set.call_args
            assert call_args[0][0] == "1234567890.123456"  # thread_ts
            state = call_args[0][1]
            assert state.get("report_thread") is True

    def test_logs_to_audit(self, cron_secret, mock_sheets):
        with patch("app.routes.cron.get_sheets", return_value=mock_sheets), \
             patch("app.routes.cron._get_slack_client") as mock_slack:
            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = {"ts": "1234567890.123456"}
            mock_slack.return_value = mock_client

            from app.routes.cron import cron_bp
            from flask import Flask
            app = Flask(__name__)
            app.register_blueprint(cron_bp)
            client = app.test_client()

            resp = client.post(
                "/cron/weekly-report",
                headers={"Authorization": "Bearer test-secret-123"},
            )
            assert resp.status_code == 200
            # Two audit calls: SCHEDULED_REPORT + WEEKLY_REPORT_SNAPSHOT
            assert mock_sheets.append_audit_log.call_count == 2
            operations = [c[1]["operation"] for c in mock_sheets.append_audit_log.call_args_list]
            assert "SCHEDULED_REPORT" in operations


# ===========================================================================
# Daily Aging Endpoint Tests
# ===========================================================================


class TestDailyAgingEndpoint:
    """POST /cron/daily-aging posts when aging tickets exist, skips otherwise."""

    def test_skips_posting_when_no_aging(self, flask_client, cron_secret, mock_sheets):
        """No aging tickets → 200 OK, no Slack post."""
        with patch("app.routes.cron.get_sheets", return_value=mock_sheets), \
             patch("app.routes.cron._get_slack_client") as mock_slack:
            mock_client = MagicMock()
            mock_slack.return_value = mock_client

            from app.routes.cron import cron_bp
            from flask import Flask
            app = Flask(__name__)
            app.register_blueprint(cron_bp)
            client = app.test_client()

            resp = client.post(
                "/cron/daily-aging",
                headers={"Authorization": "Bearer test-secret-123"},
            )
            assert resp.status_code == 200
            mock_client.chat_postMessage.assert_not_called()

    def test_posts_when_aging_tickets_exist(self, cron_secret, mock_sheets_with_aging):
        with patch("app.routes.cron.get_sheets", return_value=mock_sheets_with_aging), \
             patch("app.routes.cron._get_slack_client") as mock_slack:
            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = {"ts": "9999999.999"}
            mock_slack.return_value = mock_client

            from app.routes.cron import cron_bp
            from flask import Flask
            app = Flask(__name__)
            app.register_blueprint(cron_bp)
            client = app.test_client()

            resp = client.post(
                "/cron/daily-aging",
                headers={"Authorization": "Bearer test-secret-123"},
            )
            assert resp.status_code == 200
            mock_client.chat_postMessage.assert_called_once()
            call_kwargs = mock_client.chat_postMessage.call_args[1]
            assert call_kwargs["channel"] == "C_TECHOPS"

    def test_logs_to_audit_when_posted(self, cron_secret, mock_sheets_with_aging):
        with patch("app.routes.cron.get_sheets", return_value=mock_sheets_with_aging), \
             patch("app.routes.cron._get_slack_client") as mock_slack:
            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = {"ts": "9999999.999"}
            mock_slack.return_value = mock_client

            from app.routes.cron import cron_bp
            from flask import Flask
            app = Flask(__name__)
            app.register_blueprint(cron_bp)
            client = app.test_client()

            resp = client.post(
                "/cron/daily-aging",
                headers={"Authorization": "Bearer test-secret-123"},
            )
            assert resp.status_code == 200
            mock_sheets_with_aging.append_audit_log.assert_called_once()
            call_kwargs = mock_sheets_with_aging.append_audit_log.call_args[1]
            assert call_kwargs["operation"] == "SCHEDULED_AGING"

    def test_no_audit_when_no_aging(self, cron_secret, mock_sheets):
        """No aging tickets → no audit log entry."""
        with patch("app.routes.cron.get_sheets", return_value=mock_sheets), \
             patch("app.routes.cron._get_slack_client") as mock_slack:
            mock_client = MagicMock()
            mock_slack.return_value = mock_client

            from app.routes.cron import cron_bp
            from flask import Flask
            app = Flask(__name__)
            app.register_blueprint(cron_bp)
            client = app.test_client()

            resp = client.post(
                "/cron/daily-aging",
                headers={"Authorization": "Bearer test-secret-123"},
            )
            assert resp.status_code == 200
            mock_sheets.append_audit_log.assert_not_called()


# ===========================================================================
# Flask Handler Tests
# ===========================================================================


class TestFlaskSlackHandler:
    """Verify handler.handle(request) is called with the Flask request object."""

    def test_slack_events_passes_request_to_handler(self, cron_secret):
        """The /slack/events route must call handler.handle(request), not handler.handle()."""
        import inspect
        from app.main import create_flask_app

        with patch("app.main.create_app") as mock_create_app:
            mock_bolt = MagicMock()
            mock_create_app.return_value = mock_bolt

            with patch("app.main.SlackRequestHandler") as mock_handler_cls:
                mock_handler = MagicMock()
                mock_handler.handle.return_value = ("ok", 200)
                mock_handler_cls.return_value = mock_handler

                flask_app = create_flask_app()
                client = flask_app.test_client()

                resp = client.post(
                    "/slack/events",
                    data=b'{"type":"url_verification","challenge":"test"}',
                    content_type="application/json",
                )

                # handler.handle must be called with 1 positional arg (the request)
                mock_handler.handle.assert_called_once()
                args = mock_handler.handle.call_args[0]
                assert len(args) == 1, (
                    f"handler.handle() called with {len(args)} positional args, "
                    f"expected 1 (the Flask request object)"
                )
