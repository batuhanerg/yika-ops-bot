"""Integration tests for Claude message parsing.

These tests call the real Claude API (Haiku) and verify structured JSON output.
Requires ANTHROPIC_API_KEY environment variable.
"""

import os
from datetime import date, timedelta

import pytest

from app.services.claude import ClaudeService

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)


@pytest.fixture(scope="module")
def claude_service() -> ClaudeService:
    return ClaudeService()


class TestTurkishSupportLog:
    """Scenario 1: Turkish support log — resolved visit."""

    def test_resolved_visit(self, claude_service: ClaudeService):
        result = claude_service.parse_message(
            message="bugün ASM'ye gittim, 2 tag değiştirdim T12 ve T18. Üretim hatası, kartlar değiştirildi. Gökhan gitti.",
            sender_name="Batu",
        )
        assert result.operation == "log_support"
        assert result.data["site_id"] == "ASM-TR-01"
        assert result.data["type"] == "Visit"
        assert result.data["status"] == "Resolved"
        assert result.data["root_cause"] == "HW Fault (Production)"
        assert result.data["technician"] == "Gökhan"
        assert result.data.get("received_date") == str(date.today())


class TestMissingFields:
    """Scenario 2: Support log with missing fields."""

    def test_missing_fields_detected(self, claude_service: ClaudeService):
        result = claude_service.parse_message(
            message="Arzu hanım aradı, bazı kartların verisi az gözüküyormuş",
            sender_name="Batu",
        )
        assert result.operation == "log_support"
        assert len(result.missing_fields) > 0
        # Should be missing at least: site_id, received_date, status, technician, root_cause
        missing_set = set(result.missing_fields)
        assert "received_date" in missing_set or "site_id" in missing_set


class TestFalseAlarm:
    """Scenario 3: False alarm → User Error root cause."""

    def test_false_alarm_user_error(self, claude_service: ClaudeService):
        result = claude_service.parse_message(
            message="dün Migros'tan Ahmet bey aradı gateway offline gözüküyor dedi, kontrol ettim sorun yoktu, veri gecikmesiymiş",
            sender_name="Batu",
        )
        assert result.operation == "log_support"
        assert result.data["site_id"] == "MIG-TR-01"
        assert result.data["root_cause"] == "User Error"
        assert result.data["status"] == "Resolved"
        yesterday = str(date.today() - timedelta(days=1))
        assert result.data.get("received_date") == yesterday


class TestEnglishSupport:
    """Scenario 4: English support log."""

    def test_english_message(self, claude_service: ClaudeService):
        result = claude_service.parse_message(
            message="Visited McDonald's Cairo today, replaced 3 anchors. Production defect. Gokhan handled it.",
            sender_name="Batu",
        )
        assert result.operation == "log_support"
        assert result.data["site_id"] == "MCD-EG-01"
        assert result.data["type"] == "Visit"
        assert result.data["status"] == "Resolved"
        assert result.data["root_cause"] == "HW Fault (Production)"
        assert result.data["technician"] == "Gökhan"


class TestFirstPerson:
    """Scenario 5: First person 'ben gittim' → technician = sender."""

    def test_first_person_maps_to_sender(self, claude_service: ClaudeService):
        result = claude_service.parse_message(
            message="Ben bugün ASM'ye gittim, firmware güncelledim",
            sender_name="Batu",
        )
        assert result.operation == "log_support"
        assert result.data["technician"] == "Batu"


class TestCreateSite:
    """Scenario 6: Create site → suggested Site ID."""

    def test_create_site_suggested_id(self, claude_service: ClaudeService):
        result = claude_service.parse_message(
            message="Yeni müşteri: Anadolu Sağlık Merkezi, Gebze Kocaeli, sağlık tesisi, 1 Mart'ta kurulum yaptık, aktif",
            sender_name="Batu",
        )
        assert result.operation == "create_site"
        # Should suggest a Site ID following XXX-CC-NN pattern
        suggested_id = result.data.get("site_id", "")
        assert "-TR-" in suggested_id
        assert result.data["facility_type"] == "Healthcare"


class TestQuery:
    """Scenario 7: Query → correct query_type."""

    def test_site_summary_query(self, claude_service: ClaudeService):
        result = claude_service.parse_message(
            message="ASM'nin durumu ne?",
            sender_name="Batu",
        )
        assert result.operation == "query"
        assert result.data.get("query_type") in ("site_summary", "site_status")
        assert result.data["site_id"] == "ASM-TR-01"


class TestBulkHardware:
    """Scenario 13: Bulk hardware with sub-types → multiple entries."""

    def test_bulk_hardware_parsed(self, claude_service: ClaudeService):
        result = claude_service.parse_message(
            message="ASM'de 32 tag, 13 yatak anchoru, 20 dezenfektan anchoru, 4 sabun anchoru, 1 gateway, 4 şarj istasyonu var",
            sender_name="Batu",
        )
        assert result.operation == "update_hardware"
        entries = result.data.get("entries", [])
        assert len(entries) == 6

        device_types = [e["device_type"] for e in entries]
        assert "Tag" in device_types
        assert "Gateway" in device_types
        assert "Charging Dock" in device_types
        assert device_types.count("Anchor") == 3


class TestFutureDate:
    """Scenario 10: Future date → rejected."""

    def test_future_date_rejected(self, claude_service: ClaudeService):
        result = claude_service.parse_message(
            message="Yarın ASM'ye gideceğim, bunu logla",
            sender_name="Batu",
        )
        # Should either refuse or flag the future date
        assert result.error is not None or result.data.get("_future_date_warning") is True


class TestOldDate:
    """Date > 90 days ago → warning flag."""

    def test_old_date_warning(self, claude_service: ClaudeService):
        old_date = date.today() - timedelta(days=100)
        result = claude_service.parse_message(
            message=f"ASM'ye {old_date.strftime('%d/%m/%Y')} tarihinde gittim, tag değiştirdim, üretim hatası",
            sender_name="Batu",
        )
        assert result.operation == "log_support"
        # The service should flag old dates
        assert result.warnings is not None and len(result.warnings) > 0
