"""Tests for create_site normalization, chain roadmap, step indicators, and summaries."""

import pytest
from unittest.mock import MagicMock, patch

from app.handlers.common import _normalize_create_site_data
from app.utils.formatters import (
    build_chain_roadmap,
    build_chain_final_summary,
    format_confirmation_message,
    CHAIN_LABELS,
)


class TestNormalizeCreateSiteData:
    def test_flattens_contacts_array(self):
        data = {
            "site_id": "ASM-TR-01",
            "customer": "Anadolu Sağlık",
            "contacts": [
                {"name": "Arzu Çakmak", "phone": "0535 250 16 83", "email": ""},
                {"name": "İpek Karaman", "phone": "0543 920 26 76", "email": ""},
            ],
        }
        _normalize_create_site_data(data)
        assert data["supervisor_1"] == "Arzu Çakmak"
        assert data["phone_1"] == "0535 250 16 83"
        assert data["supervisor_2"] == "İpek Karaman"
        assert data["phone_2"] == "0543 920 26 76"
        assert "contacts" not in data

    def test_maps_dashboard_url_to_dashboard_link(self):
        data = {
            "site_id": "ASM-TR-01",
            "customer": "Test",
            "dashboard_url": "https://example.com",
        }
        _normalize_create_site_data(data)
        assert data["dashboard_link"] == "https://example.com"
        assert "dashboard_url" not in data

    def test_normalizes_country_code(self):
        data = {"site_id": "ASM-TR-01", "customer": "Test", "country": "TR"}
        _normalize_create_site_data(data)
        assert data["country"] == "Turkey"

    def test_normalizes_eg_country_code(self):
        data = {"site_id": "MCD-EG-01", "customer": "Test", "country": "EG"}
        _normalize_create_site_data(data)
        assert data["country"] == "Egypt"

    def test_preserves_full_country_name(self):
        data = {"site_id": "ASM-TR-01", "customer": "Test", "country": "Turkey"}
        _normalize_create_site_data(data)
        assert data["country"] == "Turkey"

    def test_extracts_hardware_from_data(self):
        data = {
            "site_id": "ASM-TR-01",
            "customer": "Test",
            "country": "Turkey",
            "hardware": {
                "entries": [
                    {"device_type": "Tag", "qty": 32},
                    {"device_type": "Anchor", "qty": 13},
                ]
            },
        }
        extras = _normalize_create_site_data(data)
        assert extras is not None
        hw_ops = [e for e in extras if e["operation"] == "update_hardware"]
        assert len(hw_ops) == 1
        assert len(hw_ops[0]["data"]["entries"]) == 2
        assert "hardware" not in data
        # Implementation is always included in chain
        impl_ops = [e for e in extras if e["operation"] == "update_implementation"]
        assert len(impl_ops) == 1

    def test_extracts_implementation_from_data(self):
        data = {
            "site_id": "ASM-TR-01",
            "customer": "Test",
            "country": "Turkey",
            "implementation": {
                "Internet connection": "Customer WiFi",
                "Handwash time": "30 seconds",
            },
        }
        extras = _normalize_create_site_data(data)
        assert extras is not None
        impl_ops = [e for e in extras if e["operation"] == "update_implementation"]
        assert len(impl_ops) == 1
        assert impl_ops[0]["data"]["Internet connection"] == "Customer WiFi"
        assert "implementation" not in data
        # Hardware is always included in chain
        hw_ops = [e for e in extras if e["operation"] == "update_hardware"]
        assert len(hw_ops) == 1

    def test_extracts_support_log_from_data(self):
        data = {
            "site_id": "ASM-TR-01",
            "customer": "Test",
            "country": "Turkey",
            "last_visit_date": "2025-02-03",
            "last_visit_notes": "Battery optimization",
        }
        extras = _normalize_create_site_data(data)
        assert extras is not None
        support_ops = [e for e in extras if e["operation"] == "log_support"]
        assert len(support_ops) == 1
        assert support_ops[0]["data"]["received_date"] == "2025-02-03"
        assert support_ops[0]["data"]["issue_summary"] == "Battery optimization"
        assert "last_visit_date" not in data
        assert "last_visit_notes" not in data
        # Hardware and implementation always included
        assert any(e["operation"] == "update_hardware" for e in extras)
        assert any(e["operation"] == "update_implementation" for e in extras)

    def test_extracts_all_extras_ordered(self):
        data = {
            "site_id": "ASM-TR-01",
            "customer": "Test",
            "country": "Turkey",
            "hardware": {"entries": [{"device_type": "Tag", "qty": 10}]},
            "implementation": {"Handwash time": "30s"},
            "last_visit_date": "2025-02-03",
        }
        extras = _normalize_create_site_data(data)
        assert extras is not None
        # All three explicitly extracted, no duplicates added
        ops = [e["operation"] for e in extras]
        assert ops == ["update_hardware", "update_implementation", "log_support"]

    def test_strips_non_site_keys(self):
        data = {
            "site_id": "ASM-TR-01",
            "customer": "Test",
            "country": "Turkey",
            "location_detail": "YBÜ, Gebze",
        }
        _normalize_create_site_data(data)
        assert "location_detail" not in data
        assert "site_id" in data
        assert "customer" in data

    def test_always_includes_hw_and_impl_when_no_extras(self):
        data = {
            "site_id": "ASM-TR-01",
            "customer": "Test",
            "country": "Turkey",
        }
        extras = _normalize_create_site_data(data)
        assert extras is not None
        ops = [e["operation"] for e in extras]
        assert "update_hardware" in ops
        assert "update_implementation" in ops
        # Empty data for auto-added steps
        hw = next(e for e in extras if e["operation"] == "update_hardware")
        assert hw["data"] == {}
        impl = next(e for e in extras if e["operation"] == "update_implementation")
        assert impl["data"] == {}


class TestChainRoadmap:
    def test_roadmap_all_four_steps(self):
        steps = ["create_site", "update_hardware", "update_implementation", "log_support"]
        roadmap = build_chain_roadmap(steps)
        assert "Sırayla" in roadmap
        assert "1️⃣" in roadmap
        assert "2️⃣" in roadmap
        assert "3️⃣" in roadmap
        assert "4️⃣" in roadmap
        assert "Site" in roadmap
        assert "Donanım" in roadmap
        assert "Ayarlar" in roadmap
        assert "Destek" in roadmap
        assert "onaylayabilir" in roadmap

    def test_roadmap_two_steps(self):
        steps = ["create_site", "update_hardware"]
        roadmap = build_chain_roadmap(steps)
        assert "1️⃣" in roadmap
        assert "2️⃣" in roadmap
        assert "3️⃣" not in roadmap


class TestStepIndicator:
    def test_confirmation_with_step_info(self):
        data = {"operation": "create_site", "site_id": "ASM-TR-01", "customer": "Test"}
        blocks = format_confirmation_message(data, step_info=(1, 4))
        header = blocks[0]["text"]["text"]
        assert "Adım 1/4" in header
        assert "Yeni Site" in header

    def test_confirmation_without_step_info(self):
        data = {"operation": "log_support", "site_id": "ASM-TR-01"}
        blocks = format_confirmation_message(data)
        header = blocks[0]["text"]["text"]
        assert "Adım" not in header
        assert "Destek Kaydı" in header

    def test_step_indicator_mid_chain(self):
        data = {"operation": "update_implementation", "site_id": "ASM-TR-01"}
        blocks = format_confirmation_message(data, step_info=(3, 4))
        header = blocks[0]["text"]["text"]
        assert "Adım 3/4" in header
        assert "Ayar Güncelleme" in header


class TestChainFinalSummary:
    def test_all_completed(self):
        steps = ["create_site", "update_hardware", "update_implementation", "log_support"]
        completed = {"create_site", "update_hardware", "update_implementation", "log_support"}
        summary = build_chain_final_summary("ASM-TR-01", steps, completed, set())
        assert "ASM-TR-01" in summary
        assert "tamamlandı" in summary
        assert "site ✅" in summary
        assert "donanım ✅" in summary
        assert "ayarlar ✅" in summary
        assert "destek kaydı ✅" in summary

    def test_some_skipped(self):
        steps = ["create_site", "update_hardware", "update_implementation", "log_support"]
        completed = {"create_site", "log_support"}
        skipped = {"update_hardware", "update_implementation"}
        summary = build_chain_final_summary("ASM-TR-01", steps, completed, skipped)
        assert "site ✅" in summary
        assert "donanım ⏭️" in summary
        assert "ayarlar ⏭️" in summary
        assert "destek kaydı ✅" in summary

    def test_empty_site_id(self):
        steps = ["create_site", "update_hardware"]
        completed = {"create_site", "update_hardware"}
        summary = build_chain_final_summary("", steps, completed, set())
        assert "Tamamlandı" in summary


class TestListSerialization:
    """Test that list values in support log data are serialized to strings."""

    def test_devices_affected_list_serialized(self):
        from app.services.sheets import SUPPORT_LOG_COLUMNS, _SUPPORT_KEY_MAP

        data = {
            "ticket_id": "SUP-001",
            "site_id": "ASM-TR-01",
            "devices_affected": ["Tag", "Anchor"],
        }
        row = []
        for col in SUPPORT_LOG_COLUMNS:
            key = next((k for k, v in _SUPPORT_KEY_MAP.items() if v == col), None)
            val = data.get(key, "") if key else ""
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            row.append(val)

        da_idx = SUPPORT_LOG_COLUMNS.index("Devices Affected")
        assert row[da_idx] == "Tag, Anchor"
        assert isinstance(row[da_idx], str)
