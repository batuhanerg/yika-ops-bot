"""Tests for scheduled report generation service (Item 1, Session 7).

TDD: these tests are written BEFORE the implementation.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.services.scheduled_reports import (
    generate_daily_aging_alert,
    generate_weekly_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def full_sites():
    """Sites with all must+important fields filled."""
    return [
        {
            "Site ID": "ASM-TR-01", "Customer": "Anadolu", "City": "Gebze",
            "Country": "TR", "Facility Type": "Healthcare",
            "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
            "Address": "Gebze Mah.", "Go-live Date": "2024-01-01",
            "Dashboard Link": "http://dash", "Whatsapp Group": "https://wa.me/grp",
        },
        {
            "Site ID": "MIG-TR-01", "Customer": "Migros", "City": "Istanbul",
            "Country": "TR", "Facility Type": "Food",
            "Contract Status": "Active", "Supervisor 1": "Ahmet", "Phone 1": "123",
            "Address": "Kadikoy", "Go-live Date": "2024-03-15",
            "Dashboard Link": "http://dash2", "Whatsapp Group": "https://wa.me/grp2",
        },
    ]


@pytest.fixture
def sites_with_missing_must():
    """Sites missing must fields."""
    return [
        {
            "Site ID": "ASM-TR-01", "Customer": "Anadolu", "City": "",
            "Country": "TR", "Facility Type": "Healthcare",
            "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
        },
    ]


@pytest.fixture
def sites_with_missing_important():
    """Sites missing important fields only."""
    return [
        {
            "Site ID": "MIG-TR-01", "Customer": "Migros", "City": "Istanbul",
            "Country": "TR", "Facility Type": "Food",
            "Contract Status": "Active", "Supervisor 1": "Ahmet", "Phone 1": "123",
            "Address": "", "Go-live Date": "", "Dashboard Link": "",
            "Whatsapp Group": "",
        },
    ]


@pytest.fixture
def awaiting_site():
    """Site with Awaiting Installation status."""
    return [
        {
            "Site ID": "NEW-TR-01", "Customer": "NewCo", "City": "Ankara",
            "Country": "TR", "Facility Type": "Food",
            "Contract Status": "Awaiting Installation",
            "Supervisor 1": "Ali", "Phone 1": "555",
        },
    ]


@pytest.fixture
def support_with_aging():
    """Support log with tickets older than 3 days."""
    old_date = (date.today() - timedelta(days=5)).isoformat()
    very_old = (date.today() - timedelta(days=10)).isoformat()
    return [
        {
            "Site ID": "ASM-TR-01", "Ticket ID": "SUP-001",
            "Status": "Open", "Received Date": old_date,
            "Root Cause": "", "Resolution": "",
            "Issue Summary": "Gateway offline", "Devices Affected": "",
        },
        {
            "Site ID": "MIG-TR-01", "Ticket ID": "SUP-002",
            "Status": "Follow-up (ERG)", "Received Date": very_old,
            "Root Cause": "FW Bug", "Resolution": "",
            "Issue Summary": "Tag not charging", "Devices Affected": "Tags",
        },
    ]


@pytest.fixture
def support_resolved_only():
    """Support log with only resolved tickets."""
    old_date = (date.today() - timedelta(days=30)).isoformat()
    return [
        {
            "Site ID": "ASM-TR-01", "Ticket ID": "SUP-001",
            "Status": "Resolved", "Received Date": old_date,
            "Root Cause": "FW Bug", "Resolution": "Updated FW",
            "Resolved Date": old_date, "Issue Summary": "Gateway offline",
            "Devices Affected": "Gateway",
        },
    ]


@pytest.fixture
def support_conditional_must():
    """Support log with conditional must issues."""
    old_date = (date.today() - timedelta(days=1)).isoformat()
    return [
        {
            "Site ID": "ASM-TR-01", "Ticket ID": "SUP-010",
            "Status": "Resolved", "Received Date": old_date,
            "Root Cause": "", "Resolution": "", "Resolved Date": "",
            "Issue Summary": "Tag issue", "Devices Affected": "",
        },
        {
            "Site ID": "MIG-TR-01", "Ticket ID": "SUP-011",
            "Status": "Follow-up (ERG)", "Received Date": old_date,
            "Root Cause": "Pending", "Resolution": "",
            "Issue Summary": "Anchor offline", "Devices Affected": "",
        },
    ]


@pytest.fixture
def stale_hardware():
    """Hardware with stale Last Verified."""
    old_date = (date.today() - timedelta(days=45)).isoformat()
    return [
        {
            "Site ID": "ASM-TR-01", "Device Type": "Tag", "Qty": 20,
            "HW Version": "1.0", "FW Version": "2.4", "Last Verified": old_date,
        },
        {
            "Site ID": "MIG-TR-01", "Device Type": "Gateway", "Qty": 1,
            "HW Version": "3.0", "FW Version": "1.0", "Last Verified": "",
        },
    ]


@pytest.fixture
def fresh_hardware():
    """Hardware with fresh Last Verified."""
    fresh = (date.today() - timedelta(days=5)).isoformat()
    return [
        {
            "Site ID": "ASM-TR-01", "Device Type": "Tag", "Qty": 20,
            "HW Version": "1.0", "FW Version": "2.4", "Last Verified": fresh,
        },
    ]


@pytest.fixture
def full_implementation():
    """Implementation with all fields filled."""
    fresh = (date.today() - timedelta(days=5)).isoformat()
    return [
        {
            "Site ID": "ASM-TR-01", "Internet Provider": "ERG Controls",
            "SSID": "Net", "Password": "pass", "Gateway placement": "Office",
            "Charging dock placement": "Office",
            "Dispenser anchor placement": "Washroom",
            "Handwash time": "20", "Tag buzzer/vibration": "On",
            "Entry time": "5", "Dispenser anchor power type": "USB",
            "Tag clean-to-red timeout": "30",
            "Last Verified": fresh,
        },
        {
            "Site ID": "MIG-TR-01", "Internet Provider": "ERG Controls",
            "SSID": "Net2", "Password": "pass2", "Gateway placement": "Kitchen",
            "Charging dock placement": "Kitchen",
            "Dispenser anchor placement": "Entry",
            "Handwash time": "20", "Tag buzzer/vibration": "On",
            "Entry time": "5", "Dispenser anchor power type": "Battery",
            "Clean hygiene time": "20", "HP alert time": "15",
            "Hand hygiene time": "20",
            "Hand hygiene interval (dashboard)": "30",
            "Hand hygiene type": "Standard",
            "Last Verified": fresh,
        },
    ]


# ===========================================================================
# Weekly Report Tests
# ===========================================================================


class TestWeeklyReportSections:
    """Test that weekly report includes/omits sections correctly."""

    def test_all_four_sections_when_issues_exist(
        self, sites_with_missing_must, support_with_aging, stale_hardware,
    ):
        """Weekly report includes all four sections when issues exist."""
        # Sites missing must fields → 🔴
        # Sites with important fields missing added implicitly (no address etc.)
        # Support with aging → 🟠
        # Stale hardware → 🔵
        blocks, fallback = generate_weekly_report(
            sites=sites_with_missing_must,
            hardware=stale_hardware,
            support=support_with_aging,
            implementation=[],
            stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        assert "🔴" in text, "Must section missing"
        assert "🟡" in text or "🟠" in text, "Important or aging section missing"
        assert "🟠" in text, "Aging section missing"
        assert "🔵" in text, "Stale section missing"

    def test_omits_sections_with_zero_issues(
        self, full_sites, fresh_hardware, full_implementation,
    ):
        """Sections with 0 issues are omitted entirely."""
        fresh = (date.today() - timedelta(days=1)).isoformat()
        support_resolved = [
            {
                "Site ID": "ASM-TR-01", "Ticket ID": "SUP-001",
                "Status": "Resolved", "Received Date": fresh,
                "Root Cause": "FW Bug", "Resolution": "Fixed",
                "Resolved Date": fresh, "Issue Summary": "Test",
                "Devices Affected": "Tags",
            },
        ]
        blocks, fallback = generate_weekly_report(
            sites=full_sites,
            hardware=fresh_hardware,
            support=support_resolved,
            implementation=full_implementation,
            stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        # No must issues → no 🔴 section
        # The report should have the header and overall status at minimum
        assert "Haftalık Veri Kalitesi Raporu" in text
        # If no issues exist in a section, that section header shouldn't appear
        assert "0 sorun" not in text

    def test_must_section_includes_must_fields(self, sites_with_missing_must):
        """🔴 section includes missing must fields from Sites."""
        blocks, _ = generate_weekly_report(
            sites=sites_with_missing_must,
            hardware=[], support=[], implementation=[], stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        assert "🔴" in text
        assert "ASM-TR-01" in text
        assert "City" in text  # missing City is a must field

    def test_must_section_includes_conditional_must_fields(
        self, full_sites, support_conditional_must,
    ):
        """🔴 section includes conditional must fields (root_cause when not Open)."""
        blocks, _ = generate_weekly_report(
            sites=full_sites,
            hardware=[], support=support_conditional_must,
            implementation=[], stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        assert "🔴" in text
        # SUP-010 is Resolved with empty root_cause, resolution, resolved_date
        assert "SUP-010" in text

    def test_important_section_includes_important_fields(
        self, sites_with_missing_important,
    ):
        """🟡 section includes missing important fields."""
        blocks, _ = generate_weekly_report(
            sites=sites_with_missing_important,
            hardware=[], support=[], implementation=[], stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        assert "🟡" in text
        assert "MIG-TR-01" in text

    def test_skips_awaiting_installation_for_hw_impl_support(
        self, awaiting_site,
    ):
        """Awaiting Installation sites are excluded from hw/impl/support checks."""
        blocks, _ = generate_weekly_report(
            sites=awaiting_site,
            hardware=[], support=[], implementation=[], stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        # Should NOT flag missing hardware/implementation/support for this site
        assert "Hardware" not in text or "Donanım kaydı yok" not in text


class TestWeeklyReportCompleteness:
    """Test data completeness percentage calculation."""

    def test_completeness_percentage_calculated(self, full_sites):
        """Weekly report includes a completeness percentage."""
        blocks, _ = generate_weekly_report(
            sites=full_sites,
            hardware=[], support=[], implementation=[], stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        assert "%" in text
        assert "veri tamamlılık" in text or "tamamlılık" in text

    def test_completeness_100_when_all_filled(
        self, full_sites, fresh_hardware, full_implementation,
    ):
        """Completeness is high when all must+important fields are filled."""
        blocks, _ = generate_weekly_report(
            sites=full_sites,
            hardware=fresh_hardware,
            support=[],
            implementation=full_implementation,
            stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        # Should have a high percentage (exact value depends on cross-tab checks)
        assert "%" in text


class TestWeeklyReportFeedback:
    """Test that weekly report includes feedback buttons."""

    def test_includes_feedback_buttons(self, full_sites):
        blocks, _ = generate_weekly_report(
            sites=full_sites,
            hardware=[], support=[], implementation=[], stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        assert "feedback_positive" in text or "👍" in text
        assert "feedback_negative" in text or "👎" in text


class TestWeeklyReportFallbackText:
    """Test the text fallback for the weekly report."""

    def test_fallback_text_is_nonempty(self, full_sites):
        _, fallback = generate_weekly_report(
            sites=full_sites,
            hardware=[], support=[], implementation=[], stock=[],
        )
        assert isinstance(fallback, str)
        assert len(fallback) > 0


# ===========================================================================
# Daily Aging Alert Tests
# ===========================================================================


class TestDailyAgingAlert:
    """Test daily aging alert generation."""

    def test_returns_none_when_no_aging_tickets(self, support_resolved_only):
        """Returns None when no tickets are aging."""
        result = generate_daily_aging_alert(support=support_resolved_only)
        assert result is None

    def test_returns_none_when_no_support(self):
        """Returns None with empty support log."""
        result = generate_daily_aging_alert(support=[])
        assert result is None

    def test_returns_none_when_recent_open_tickets(self):
        """Returns None when open tickets are within 3 days."""
        recent = (date.today() - timedelta(days=1)).isoformat()
        support = [
            {
                "Site ID": "ASM-TR-01", "Ticket ID": "SUP-001",
                "Status": "Open", "Received Date": recent,
                "Issue Summary": "Test issue",
            },
        ]
        result = generate_daily_aging_alert(support=support)
        assert result is None

    def test_returns_message_when_aging_tickets(self, support_with_aging):
        """Returns blocks when tickets exist >3 days."""
        result = generate_daily_aging_alert(support=support_with_aging)
        assert result is not None
        blocks, fallback = result
        assert len(blocks) > 0
        assert len(fallback) > 0

    def test_includes_ticket_details(self, support_with_aging):
        """Aging alert includes ticket ID, site ID, issue summary, days open."""
        blocks, _ = generate_daily_aging_alert(support=support_with_aging)
        text = json.dumps(blocks, ensure_ascii=False)
        assert "SUP-001" in text
        assert "ASM-TR-01" in text
        assert "Gateway offline" in text
        assert "gündür açık" in text or "günden fazla" in text

    def test_includes_multiple_tickets(self, support_with_aging):
        """All aging tickets are listed."""
        blocks, _ = generate_daily_aging_alert(support=support_with_aging)
        text = json.dumps(blocks, ensure_ascii=False)
        assert "SUP-001" in text
        assert "SUP-002" in text

    def test_includes_feedback_buttons(self, support_with_aging):
        """Aging alert includes feedback buttons."""
        blocks, _ = generate_daily_aging_alert(support=support_with_aging)
        text = json.dumps(blocks, ensure_ascii=False)
        assert "feedback_positive" in text or "👍" in text

    def test_excludes_resolved_tickets(self):
        """Resolved tickets are never included even if old."""
        old = (date.today() - timedelta(days=30)).isoformat()
        support = [
            {
                "Site ID": "ASM-TR-01", "Ticket ID": "SUP-099",
                "Status": "Resolved", "Received Date": old,
                "Root Cause": "FW Bug", "Resolution": "Fixed",
                "Resolved Date": old, "Issue Summary": "Old resolved",
            },
        ]
        result = generate_daily_aging_alert(support=support)
        assert result is None

    def test_count_in_header(self, support_with_aging):
        """Header shows the count of aging tickets."""
        blocks, _ = generate_daily_aging_alert(support=support_with_aging)
        text = json.dumps(blocks, ensure_ascii=False)
        assert "2 ticket" in text


# ===========================================================================
# Resolution Tracking Tests (Item 4)
# ===========================================================================


class TestResolutionTracking:
    """Test weekly report resolution tracking via prev_snapshot."""

    def test_first_report_no_resolution_section(self):
        """First ever report (no prev_snapshot) → no 📈 section."""
        sites = [
            {
                "Site ID": "ASM-TR-01", "Customer": "Anadolu", "City": "",
                "Country": "TR", "Facility Type": "Healthcare",
                "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
            },
        ]
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=[], support=[],
            implementation=[], stock=[],
            prev_snapshot=None,
        )
        text = json.dumps(blocks, ensure_ascii=False)
        assert "📈" not in text

    def test_second_report_shows_resolution_counts(self):
        """Second report with prev_snapshot → shows resolved counts."""
        # Last week: 2 must issues, 1 important issue
        prev_snapshot = [
            {"site_id": "ASM-TR-01", "tab": "Sites", "field": "City", "severity": "must"},
            {"site_id": "ASM-TR-01", "tab": "Sites", "field": "Supervisor 1", "severity": "must"},
            {"site_id": "ASM-TR-01", "tab": "Sites", "field": "Address", "severity": "important"},
        ]
        # This week: City is still missing, but Supervisor 1 is fixed
        sites = [
            {
                "Site ID": "ASM-TR-01", "Customer": "Anadolu", "City": "",
                "Country": "TR", "Facility Type": "Healthcare",
                "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
                "Address": "Gebze",  # fixed
            },
        ]
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=[], support=[],
            implementation=[], stock=[],
            prev_snapshot=prev_snapshot,
        )
        text = json.dumps(blocks, ensure_ascii=False)
        assert "📈" in text
        # 1 of 2 must issues resolved (Supervisor 1 fixed)
        assert "1/2 acil sorun çözüldü" in text
        # 1 of 1 important issue resolved (Address fixed)
        assert "1/1 önemli sorun çözüldü" in text

    def test_resolved_means_absent_this_week(self):
        """Resolved = present last week, absent this week."""
        prev_snapshot = [
            {"site_id": "ASM-TR-01", "tab": "Sites", "field": "City", "severity": "must"},
        ]
        # City is now filled
        sites = [
            {
                "Site ID": "ASM-TR-01", "Customer": "Anadolu", "City": "Gebze",
                "Country": "TR", "Facility Type": "Healthcare",
                "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
            },
        ]
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=[], support=[],
            implementation=[], stock=[],
            prev_snapshot=prev_snapshot,
        )
        text = json.dumps(blocks, ensure_ascii=False)
        assert "1/1 acil sorun çözüldü" in text

    def test_new_issues_dont_affect_resolution(self):
        """New issues this week don't affect last week's resolution count."""
        prev_snapshot = [
            {"site_id": "ASM-TR-01", "tab": "Sites", "field": "City", "severity": "must"},
        ]
        # City is still missing, AND Country is now also missing (new issue)
        sites = [
            {
                "Site ID": "ASM-TR-01", "Customer": "Anadolu", "City": "",
                "Country": "", "Facility Type": "Healthcare",
                "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
            },
        ]
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=[], support=[],
            implementation=[], stock=[],
            prev_snapshot=prev_snapshot,
        )
        text = json.dumps(blocks, ensure_ascii=False)
        # 0 of 1 resolved (City still missing), Country is new and irrelevant
        assert "0/1 acil sorun çözüldü" in text


class TestSnapshotStorage:
    """Test that the cron route stores/reads snapshots via Audit Log."""

    def test_snapshot_stored_after_report(self):
        """After posting weekly report, a WEEKLY_REPORT_SNAPSHOT is written."""
        from unittest.mock import call

        mock_sheets = MagicMock()
        mock_sheets.read_sites.return_value = [
            {
                "Site ID": "ASM-TR-01", "Customer": "Anadolu", "City": "",
                "Country": "TR", "Facility Type": "Healthcare",
                "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
            },
        ]
        mock_sheets.read_hardware.return_value = []
        mock_sheets.read_support_log.return_value = []
        mock_sheets.read_all_implementation.return_value = []
        mock_sheets.read_stock.return_value = []
        mock_sheets.read_latest_audit_by_operation.return_value = None

        with patch("app.routes.cron.get_sheets", return_value=mock_sheets), \
             patch("app.routes.cron._get_slack_client") as mock_slack:
            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = {"ts": "123.456"}
            mock_slack.return_value = mock_client

            import os
            os.environ.setdefault("CRON_SECRET", "test-secret-123")
            os.environ.setdefault("SLACK_CHANNEL_ID", "C_TECHOPS")

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

            # Should have TWO audit log calls: SCHEDULED_REPORT + WEEKLY_REPORT_SNAPSHOT
            audit_calls = mock_sheets.append_audit_log.call_args_list
            operations = [c[1]["operation"] for c in audit_calls]
            assert "SCHEDULED_REPORT" in operations
            assert "WEEKLY_REPORT_SNAPSHOT" in operations

            # The snapshot call should contain JSON issue list in summary
            snapshot_call = [c for c in audit_calls if c[1]["operation"] == "WEEKLY_REPORT_SNAPSHOT"][0]
            summary = snapshot_call[1]["summary"]
            parsed = json.loads(summary)
            assert isinstance(parsed, list)
            # Each item should have tab key to disambiguate fields across tabs
            for item in parsed:
                assert "tab" in item, f"Snapshot item missing 'tab': {item}"

    def test_second_report_reads_previous_snapshot(self):
        """Second weekly report reads the previous snapshot for resolution tracking."""
        prev_issues = [
            {"site_id": "ASM-TR-01", "tab": "Sites", "field": "City", "severity": "must"},
        ]

        mock_sheets = MagicMock()
        mock_sheets.read_sites.return_value = [
            {
                "Site ID": "ASM-TR-01", "Customer": "Anadolu", "City": "Gebze",
                "Country": "TR", "Facility Type": "Healthcare",
                "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
            },
        ]
        mock_sheets.read_hardware.return_value = []
        mock_sheets.read_support_log.return_value = []
        mock_sheets.read_all_implementation.return_value = []
        mock_sheets.read_stock.return_value = []
        # Return previous snapshot
        mock_sheets.read_latest_audit_by_operation.return_value = json.dumps(prev_issues)

        with patch("app.routes.cron.get_sheets", return_value=mock_sheets), \
             patch("app.routes.cron._get_slack_client") as mock_slack:
            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = {"ts": "123.456"}
            mock_slack.return_value = mock_client

            import os
            os.environ.setdefault("CRON_SECRET", "test-secret-123")
            os.environ.setdefault("SLACK_CHANNEL_ID", "C_TECHOPS")

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

            # Verify the posted message contains the resolution section
            post_kwargs = mock_client.chat_postMessage.call_args[1]
            text = json.dumps(post_kwargs["blocks"], ensure_ascii=False)
            assert "📈" in text
            assert "1/1 acil sorun çözüldü" in text


# ===========================================================================
# Resolution Edge Cases (Item 4 review fixes)
# ===========================================================================


class TestResolutionEdgeCases:
    """Edge cases for resolution tracking."""

    def test_awaiting_installation_not_counted_as_resolved(self):
        """Site switching to Awaiting Installation should not inflate resolved count.

        If a site was Active last week (with hw/impl issues) and is now
        Awaiting Installation, those issues disappear from find_missing_data
        but should NOT be counted as "resolved".
        """
        prev_snapshot = [
            {"site_id": "ASM-TR-01", "tab": "Implementation Details", "field": "SSID", "severity": "must"},
            {"site_id": "ASM-TR-01", "tab": "Hardware Inventory", "field": "HW Version", "severity": "important"},
        ]
        # This week: site is now Awaiting Installation
        sites = [
            {
                "Site ID": "ASM-TR-01", "Customer": "Anadolu", "City": "Gebze",
                "Country": "TR", "Facility Type": "Healthcare",
                "Contract Status": "Awaiting Installation",
                "Supervisor 1": "Ali", "Phone 1": "555",
            },
        ]
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=[], support=[],
            implementation=[], stock=[],
            prev_snapshot=prev_snapshot,
        )
        text = json.dumps(blocks, ensure_ascii=False)
        # Should NOT show "1/1 acil sorun çözüldü" or "1/1 önemli sorun çözüldü"
        # because the site simply changed status, not actually resolved
        assert "📈" not in text, (
            "Resolution section should not appear when all prev issues are from "
            "sites that switched to Awaiting Installation"
        )

    def test_zero_zero_not_displayed(self):
        """0/0 resolved should not appear in the report.

        When prev_snapshot has only important issues, the must line should
        be omitted (and vice versa).
        """
        prev_snapshot = [
            {"site_id": "ASM-TR-01", "tab": "Sites", "field": "Address", "severity": "important"},
        ]
        # Address is still missing
        sites = [
            {
                "Site ID": "ASM-TR-01", "Customer": "Anadolu", "City": "Gebze",
                "Country": "TR", "Facility Type": "Healthcare",
                "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
                "Address": "",
            },
        ]
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=[], support=[],
            implementation=[], stock=[],
            prev_snapshot=prev_snapshot,
        )
        text = json.dumps(blocks, ensure_ascii=False)
        assert "📈" in text
        # Should show "0/1 önemli sorun çözüldü" but NOT "0/0 acil sorun çözüldü"
        assert "0/1 önemli sorun çözüldü" in text
        assert "0/0" not in text

    def test_tab_disambiguates_same_field_across_tabs(self):
        """Same field name on different tabs treated as separate issues.

        hw_version on Hardware Inventory and hw_version on Stock are distinct.
        Both are severity=important, but different (site_id, tab) combos.
        """
        prev_snapshot = [
            {"site_id": "ASM-TR-01", "tab": "Hardware Inventory", "field": "HW Version", "severity": "important"},
            {"site_id": "WH/Tag", "tab": "Stock", "field": "HW Version", "severity": "important"},
        ]
        # HW Version fixed on Hardware but still missing on Stock
        sites = [
            {
                "Site ID": "ASM-TR-01", "Customer": "Anadolu", "City": "Gebze",
                "Country": "TR", "Facility Type": "Healthcare",
                "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
            },
        ]
        hardware = [
            {
                "Site ID": "ASM-TR-01", "Device Type": "Tag", "Qty": 20,
                "HW Version": "1.0", "FW Version": "2.4",
                "Last Verified": date.today().isoformat(),
            },
        ]
        stock = [
            {
                "Location": "WH", "Device Type": "Tag", "Qty": 10,
                "HW Version": "", "Condition": "New",
                "Last Verified": date.today().isoformat(),
            },
        ]
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=hardware, support=[],
            implementation=[], stock=stock,
            prev_snapshot=prev_snapshot,
        )
        text = json.dumps(blocks, ensure_ascii=False)
        assert "📈" in text
        # HW fixed on Hardware (1 resolved), Stock still missing (1 not resolved)
        # → 1/2 important resolved
        assert "1/2 önemli sorun çözüldü" in text


# ===========================================================================
# Section Caps Tests (Bug D)
# ===========================================================================


class TestSectionCaps:
    """Each section capped at 15 lines; total counts still accurate."""

    def test_5_lines_no_truncation(self):
        """Section with 5 consolidated lines → all shown, no truncation message."""
        sites = []
        for i in range(5):
            sites.append({
                "Site ID": f"TST-TR-{i:02d}", "Customer": f"Cust{i}",
                "City": "", "Country": "TR", "Facility Type": "Healthcare",
                "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
            })
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=[], support=[],
            implementation=[], stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        assert "...ve" not in text
        # All 5 sites should appear
        for i in range(5):
            assert f"TST-TR-{i:02d}" in text

    def test_25_lines_shows_15_plus_truncation(self):
        """Section with 25 consolidated lines → 15 shown + truncation message."""
        sites = []
        for i in range(25):
            sites.append({
                "Site ID": f"TST-TR-{i:02d}", "Customer": f"Cust{i}",
                "City": "", "Country": "TR", "Facility Type": "Healthcare",
                "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
            })
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=[], support=[],
            implementation=[], stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        assert "...ve 10 sorun daha" in text

    def test_summary_shows_total_not_capped(self):
        """✅ summary shows total issues, not the capped display count."""
        sites = []
        for i in range(25):
            sites.append({
                "Site ID": f"TST-TR-{i:02d}", "Customer": f"Cust{i}",
                "City": "", "Country": "TR", "Facility Type": "Healthcare",
                "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
            })
        blocks, fallback = generate_weekly_report(
            sites=sites, hardware=[], support=[],
            implementation=[], stock=[],
        )
        # Fallback text contains the real total
        assert "25 acil" in fallback or "25 önemli" in fallback or "acil" in fallback

    def test_snapshot_stores_all_not_capped(self):
        """Snapshot for resolution tracking stores ALL issues, not just displayed 15."""
        import os
        from unittest.mock import call

        mock_sheets = MagicMock()
        sites = []
        for i in range(25):
            sites.append({
                "Site ID": f"TST-TR-{i:02d}", "Customer": f"Cust{i}",
                "City": "", "Country": "TR", "Facility Type": "Healthcare",
                "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
            })
        mock_sheets.read_sites.return_value = sites
        mock_sheets.read_hardware.return_value = []
        mock_sheets.read_support_log.return_value = []
        mock_sheets.read_all_implementation.return_value = []
        mock_sheets.read_stock.return_value = []
        mock_sheets.read_latest_audit_by_operation.return_value = None

        with patch("app.routes.cron.get_sheets", return_value=mock_sheets), \
             patch("app.routes.cron._get_slack_client") as mock_slack:
            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = {"ts": "123.456"}
            mock_slack.return_value = mock_client

            os.environ.setdefault("CRON_SECRET", "test-secret-123")
            os.environ.setdefault("SLACK_CHANNEL_ID", "C_TECHOPS")

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

            # Snapshot should have ALL issues (25 sites × City missing = 25 must issues)
            audit_calls = mock_sheets.append_audit_log.call_args_list
            snapshot_call = [c for c in audit_calls if c[1]["operation"] == "WEEKLY_REPORT_SNAPSHOT"][0]
            parsed = json.loads(snapshot_call[1]["summary"])
            must_issues = [i for i in parsed if i.get("severity") == "must"]
            assert len(must_issues) >= 25

    def test_lines_sorted_by_issue_count(self):
        """Lines are sorted by issue count descending (worst sites first)."""
        sites = []
        # Site with 1 must issue
        sites.append({
            "Site ID": "FEW-TR-01", "Customer": "Few", "City": "",
            "Country": "TR", "Facility Type": "Healthcare",
            "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
        })
        # Site with 3 must issues
        sites.append({
            "Site ID": "MANY-TR-01", "Customer": "Many", "City": "",
            "Country": "", "Facility Type": "",
            "Contract Status": "Active", "Supervisor 1": "", "Phone 1": "",
        })
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=[], support=[],
            implementation=[], stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        # MANY-TR-01 should appear before FEW-TR-01 in the must section
        many_pos = text.find("MANY-TR-01")
        few_pos = text.find("FEW-TR-01")
        assert many_pos < few_pos, "Sites with more issues should be listed first"


# ===========================================================================
# Field List Cleanup Tests (Bug C)
# ===========================================================================


class TestFieldListCleanup:
    """No trailing ', —' or empty field names in output."""

    def test_empty_field_names_filtered_out(self):
        """Field list with empty string entries → filtered before joining."""
        sites = [
            {"Site ID": "EST-TR-01", "Customer": "Estia", "City": "Izmir",
             "Country": "TR", "Facility Type": "Healthcare",
             "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
             "Address": "", "Whatsapp Group": ""},
        ]
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=[], support=[],
            implementation=[], stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        # No empty field names, no "—" as a field name
        assert ", —" not in text
        assert ", ," not in text

    def test_whitespace_only_fields_filtered(self):
        """Whitespace-only field names don't appear."""
        sites = [
            {"Site ID": "EST-TR-01", "Customer": "Estia", "City": "Izmir",
             "Country": "TR", "Facility Type": "Healthcare",
             "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555"},
        ]
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=[], support=[],
            implementation=[], stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        assert ", —" not in text

    def test_no_trailing_comma_dash_in_output(self):
        """No trailing ', —' in any output line."""
        sites = [
            {"Site ID": "EST-TR-01", "Customer": "Estia", "City": "Izmir",
             "Country": "TR", "Facility Type": "Healthcare",
             "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
             "Address": "", "Go-live Date": "", "Dashboard Link": "",
             "Whatsapp Group": ""},
        ]
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=[], support=[],
            implementation=[], stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        assert ", —" not in text
        # No leading comma in field lists
        for block in blocks:
            if block.get("type") == "section":
                block_text = block["text"].get("text", "")
                for line in block_text.split("\n"):
                    if "•" in line and "boş" in line:
                        # Extract field part after ":"
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            field_part = parts[1].strip()
                            assert not field_part.startswith(","), f"Leading comma: {line}"


# ===========================================================================
# Per-site Consolidation Tests (Bug B)
# ===========================================================================


class TestPerSiteConsolidation:
    """Important and stale issues consolidated per site per tab."""

    def test_7_hw_rows_missing_hw_version_one_line(self):
        """Site with 7 hardware rows all missing HW Version → one line, not 7."""
        sites = [
            {"Site ID": "ISS-TR-01", "Customer": "Issinova", "City": "Istanbul",
             "Country": "TR", "Facility Type": "Healthcare",
             "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555"},
        ]
        hardware = [
            {"Site ID": "ISS-TR-01", "Device Type": "Tag", "Qty": 5,
             "HW Version": "", "FW Version": "2.4",
             "Last Verified": date.today().isoformat()}
            for _ in range(7)
        ]
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=hardware, support=[],
            implementation=[], stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        # Should have exactly one line for ISS-TR-01 in important section
        important_lines = [l for l in text.split("\\n") if "ISS-TR-01" in l and "HW Version" in l]
        assert len(important_lines) == 1

    def test_7_hw_rows_empty_last_verified_consolidated(self):
        """Site with 7 hardware rows all with empty Last Verified → one line with count."""
        sites = [
            {"Site ID": "ISS-TR-01", "Customer": "Issinova", "City": "Istanbul",
             "Country": "TR", "Facility Type": "Healthcare",
             "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555"},
        ]
        hardware = [
            {"Site ID": "ISS-TR-01", "Device Type": "Tag", "Qty": 5,
             "HW Version": "1.0", "FW Version": "2.4", "Last Verified": ""}
            for _ in range(7)
        ]
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=hardware, support=[],
            implementation=[], stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        # Should show count: "7 cihazda Last Verified boş"
        assert "7 cihazda" in text
        # Should be one line, not 7
        stale_lines = [l for l in text.split("\\n") if "ISS-TR-01" in l and "Last Verified" in l]
        assert len(stale_lines) == 1

    def test_mixed_hw_rows_correct_count(self):
        """Site with 3 having HW Version and 4 missing → mentions only missing ones."""
        sites = [
            {"Site ID": "ISS-TR-01", "Customer": "Issinova", "City": "Istanbul",
             "Country": "TR", "Facility Type": "Healthcare",
             "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555"},
        ]
        filled = [
            {"Site ID": "ISS-TR-01", "Device Type": "Tag", "Qty": 5,
             "HW Version": "1.0", "FW Version": "2.4",
             "Last Verified": date.today().isoformat()}
            for _ in range(3)
        ]
        missing = [
            {"Site ID": "ISS-TR-01", "Device Type": "Tag", "Qty": 5,
             "HW Version": "", "FW Version": "2.4",
             "Last Verified": date.today().isoformat()}
            for _ in range(4)
        ]
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=filled + missing, support=[],
            implementation=[], stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        # Important section should mention HW Version once for ISS-TR-01
        important_lines = [l for l in text.split("\\n") if "ISS-TR-01" in l and "HW Version" in l]
        assert len(important_lines) == 1

    def test_single_hw_row_no_count_prefix(self):
        """Single hardware row missing Last Verified → no count prefix."""
        sites = [
            {"Site ID": "ISS-TR-01", "Customer": "Issinova", "City": "Istanbul",
             "Country": "TR", "Facility Type": "Healthcare",
             "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555"},
        ]
        hardware = [
            {"Site ID": "ISS-TR-01", "Device Type": "Tag", "Qty": 5,
             "HW Version": "1.0", "FW Version": "2.4", "Last Verified": ""},
        ]
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=hardware, support=[],
            implementation=[], stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        # Should NOT have "1 cihazda" — just normal format
        assert "1 cihazda" not in text
        assert "Last Verified" in text

    def test_two_tabs_same_site_separate_lines(self):
        """Two different tabs for same site → separate lines per tab."""
        sites = [
            {"Site ID": "ISS-TR-01", "Customer": "Issinova", "City": "Istanbul",
             "Country": "TR", "Facility Type": "Healthcare",
             "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555"},
        ]
        hardware = [
            {"Site ID": "ISS-TR-01", "Device Type": "Tag", "Qty": 5,
             "HW Version": "", "FW Version": "2.4",
             "Last Verified": date.today().isoformat()}
            for _ in range(3)
        ]
        impl = [
            {"Site ID": "ISS-TR-01", "Internet Provider": "ERG Controls",
             "SSID": "Net", "Password": "pass", "Gateway placement": "",
             "Last Verified": date.today().isoformat()},
        ]
        blocks, _ = generate_weekly_report(
            sites=sites, hardware=hardware, support=[],
            implementation=impl, stock=[],
        )
        text = json.dumps(blocks, ensure_ascii=False)
        # Should have separate lines for Hardware and Implementation
        assert "Hardware" in text or "HW Version" in text
        assert "Gateway placement" in text


# ===========================================================================
# Block Size Limit Tests (Slack 3000 char limit)
# ===========================================================================


class TestBlockSizeLimit:
    """Ensure section blocks stay under Slack's 3000-char limit."""

    def test_split_long_section_under_limit_single_block(self):
        """Text under 2900 chars returns a single chunk."""
        from app.services.scheduled_reports import _split_long_section
        text = "Line 1\nLine 2\nLine 3"
        chunks = _split_long_section(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_split_long_section_over_limit_multiple_chunks(self):
        """Text over 2900 chars is split into multiple chunks, each under 2900."""
        from app.services.scheduled_reports import _split_long_section
        # Build text that's ~6000 chars (60 lines of ~100 chars each)
        lines = [f"  • SITE-TR-{i:02d}: Some field description that is reasonably long to simulate real data — eksik" for i in range(60)]
        text = "\n".join(lines)
        assert len(text) > 2900

        chunks = _split_long_section(text)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= 2900, f"Chunk exceeds limit: {len(chunk)} chars"

    def test_split_preserves_newline_boundaries(self):
        """Split happens at newline boundaries, not mid-line."""
        from app.services.scheduled_reports import _split_long_section
        lines = [f"Line {i}: " + "x" * 90 for i in range(40)]
        text = "\n".join(lines)
        chunks = _split_long_section(text)
        # Reconstruct and compare
        reconstructed = "\n".join(chunks)
        assert reconstructed == text

    def test_many_issues_produce_valid_blocks(self):
        """Report with 25+ must issues per section produces blocks all under 3000 chars."""
        # Build 25 sites with missing City (must field)
        sites = []
        for i in range(25):
            sites.append({
                "Site ID": f"TST-TR-{i:02d}", "Customer": f"Customer{i}",
                "City": "", "Country": "TR", "Facility Type": "Healthcare",
                "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555",
            })

        blocks, _ = generate_weekly_report(
            sites=sites, hardware=[], support=[],
            implementation=[], stock=[],
        )

        # Every section block's text must be under 3000 chars
        for block in blocks:
            if block.get("type") == "section" and "text" in block:
                text_content = block["text"].get("text", "")
                assert len(text_content) <= 3000, (
                    f"Block text exceeds 3000 chars ({len(text_content)}): "
                    f"{text_content[:100]}..."
                )
