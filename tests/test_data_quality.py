"""Tests for data quality queries — missing_data and stale_data.

Rewritten for Session 5: uses FIELD_REQUIREMENTS, severity levels,
context-awareness, and conditional importance.
"""

import json
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app.services.data_quality import find_missing_data, find_stale_data
from app.utils.formatters import format_data_quality_response


class TestMissingDataSites:
    """Test missing data detection on Sites tab."""

    def test_must_field_flagged_with_must_severity(self):
        """Missing must field (e.g., no City) → severity='must'."""
        sites = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros", "City": "",
             "Country": "Turkey", "Facility Type": "Food",
             "Contract Status": "Active", "Supervisor 1": "Ahmet", "Phone 1": "123"},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[], site_id="MIG-TR-01")
        city_issues = [r for r in result if r["field"] == "City"]
        assert len(city_issues) == 1
        assert city_issues[0]["severity"] == "must"

    def test_important_field_flagged_with_important_severity(self):
        """Missing important field (e.g., Address) → severity='important'."""
        sites = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros", "City": "Istanbul",
             "Country": "Turkey", "Facility Type": "Food",
             "Contract Status": "Active", "Supervisor 1": "Ahmet", "Phone 1": "123",
             "Address": "", "Go-live Date": "2021-03-15", "Dashboard Link": "http://x",
             "Whatsapp Group": ""},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[], site_id="MIG-TR-01")
        addr_issues = [r for r in result if r["field"] == "Address"]
        assert len(addr_issues) == 1
        assert addr_issues[0]["severity"] == "important"

    def test_optional_field_not_flagged(self):
        """Optional fields (e.g., Email 1, Notes) are never flagged."""
        sites = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros", "City": "Istanbul",
             "Country": "Turkey", "Facility Type": "Food",
             "Contract Status": "Active", "Supervisor 1": "Ahmet", "Phone 1": "123",
             "Email 1": "", "Notes": ""},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[], site_id="MIG-TR-01")
        fields = [r["field"] for r in result if r["tab"] == "Sites"]
        assert "Email 1" not in fields
        assert "Notes" not in fields

    def test_no_issues_when_all_must_and_important_present(self):
        sites = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros", "City": "Istanbul",
             "Country": "Turkey", "Facility Type": "Food",
             "Contract Status": "Active", "Supervisor 1": "Ahmet", "Phone 1": "123",
             "Address": "Kadıköy", "Go-live Date": "2021-03-15",
             "Dashboard Link": "http://x", "Whatsapp Group": "https://wa.me/grp"},
        ]
        hardware = [
            {"Site ID": "MIG-TR-01", "Device Type": "Tag", "Qty": 20,
             "FW Version": "2.4.1", "HW Version": "1.0"},
        ]
        support = [
            {"Site ID": "MIG-TR-01", "Ticket ID": "SUP-001", "Status": "Resolved",
             "Root Cause": "FW Bug", "Resolution": "Fixed", "Resolved Date": "2025-01-10",
             "Devices Affected": "Tags"},
        ]
        implementation = [{"Site ID": "MIG-TR-01", "Internet Provider": "ERG Controls",
                          "SSID": "Net", "Password": "pass123",
                          "Gateway placement": "Office",
                          "Charging dock placement": "Office",
                          "Dispenser anchor placement": "Washroom",
                          "Handwash time": "20", "Tag buzzer/vibration": "On",
                          "Entry time": "5", "Dispenser anchor power type": "USB",
                          "Clean hygiene time": "20", "HP alert time": "15",
                          "Hand hygiene time": "20", "Hand hygiene interval (dashboard)": "30",
                          "Hand hygiene type": "Standard",
                          "Last Verified": "2025-01-01"}]
        result = find_missing_data(sites=sites, hardware=hardware, support=support,
                                   site_id="MIG-TR-01", implementation=implementation)
        assert len(result) == 0

    def test_all_sites_scan(self):
        """When no site_id given, scan all sites."""
        sites = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros", "City": "",
             "Country": "Turkey", "Facility Type": "Food",
             "Contract Status": "Active", "Supervisor 1": "Ahmet", "Phone 1": "123"},
            {"Site ID": "MCD-EG-01", "Customer": "McDonald's", "City": "Cairo",
             "Country": "Egypt", "Facility Type": "Food",
             "Contract Status": "Active", "Supervisor 1": "", "Phone 1": ""},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[], site_id=None)
        site_ids_with_issues = {r["site_id"] for r in result}
        assert "MIG-TR-01" in site_ids_with_issues
        assert "MCD-EG-01" in site_ids_with_issues


class TestMissingDataContextAwareness:
    """Test context-awareness: Awaiting Installation skips certain tabs."""

    def test_awaiting_installation_skips_hardware(self):
        """Sites with 'Awaiting Installation' should not flag missing hardware."""
        sites = [
            {"Site ID": "NEW-TR-01", "Customer": "NewCo", "City": "Ankara",
             "Country": "Turkey", "Facility Type": "Food",
             "Contract Status": "Awaiting Installation",
             "Supervisor 1": "Ali", "Phone 1": "555"},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[], site_id="NEW-TR-01")
        hw_issues = [r for r in result if r["tab"] == "Hardware Inventory"]
        assert len(hw_issues) == 0

    def test_awaiting_installation_skips_implementation(self):
        sites = [
            {"Site ID": "NEW-TR-01", "Customer": "NewCo", "City": "Ankara",
             "Country": "Turkey", "Facility Type": "Food",
             "Contract Status": "Awaiting Installation",
             "Supervisor 1": "Ali", "Phone 1": "555"},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[],
                                   site_id="NEW-TR-01", implementation=[])
        impl_issues = [r for r in result if r["tab"] == "Implementation Details"]
        assert len(impl_issues) == 0

    def test_awaiting_installation_skips_support(self):
        sites = [
            {"Site ID": "NEW-TR-01", "Customer": "NewCo", "City": "Ankara",
             "Country": "Turkey", "Facility Type": "Food",
             "Contract Status": "Awaiting Installation",
             "Supervisor 1": "Ali", "Phone 1": "555"},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[], site_id="NEW-TR-01")
        sup_issues = [r for r in result if r["tab"] == "Support Log"]
        assert len(sup_issues) == 0

    def test_active_site_flags_missing_hardware(self):
        """Active sites SHOULD flag missing hardware records."""
        sites = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros", "City": "Istanbul",
             "Country": "Turkey", "Facility Type": "Food",
             "Contract Status": "Active",
             "Supervisor 1": "Ahmet", "Phone 1": "123"},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[], site_id="MIG-TR-01")
        hw_issues = [r for r in result if r["tab"] == "Hardware Inventory"]
        assert len(hw_issues) >= 1


class TestMissingDataImplementationFacilityType:
    """Test facility-type conditional must fields for Implementation Details."""

    def test_food_site_missing_clean_hygiene_time(self):
        """Food site missing clean_hygiene_time → 🔴 must."""
        sites = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros", "City": "Istanbul",
             "Country": "Turkey", "Facility Type": "Food",
             "Contract Status": "Active", "Supervisor 1": "Ahmet", "Phone 1": "123"},
        ]
        impl = [
            {"Site ID": "MIG-TR-01", "Internet Provider": "ERG Controls", "SSID": "Net",
             "Clean hygiene time": "", "Last Verified": "2025-01-01"},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[],
                                   site_id="MIG-TR-01", implementation=impl)
        ch_issues = [r for r in result if r["field"] == "Clean hygiene time"]
        assert len(ch_issues) == 1
        assert ch_issues[0]["severity"] == "must"

    def test_food_site_tag_clean_to_red_not_flagged(self):
        """Food site missing tag_clean_to_red_timeout → NOT flagged (Healthcare-only)."""
        sites = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros", "City": "Istanbul",
             "Country": "Turkey", "Facility Type": "Food",
             "Contract Status": "Active", "Supervisor 1": "Ahmet", "Phone 1": "123"},
        ]
        impl = [
            {"Site ID": "MIG-TR-01", "Internet Provider": "ERG Controls", "SSID": "Net",
             "Tag clean-to-red timeout": "", "Last Verified": "2025-01-01"},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[],
                                   site_id="MIG-TR-01", implementation=impl)
        tcr_issues = [r for r in result if r["field"] == "Tag clean-to-red timeout"]
        assert len(tcr_issues) == 0

    def test_healthcare_site_missing_tag_clean_to_red(self):
        """Healthcare site missing tag_clean_to_red_timeout → 🔴 must."""
        sites = [
            {"Site ID": "ASM-TR-01", "Customer": "Anadolu", "City": "Gebze",
             "Country": "Turkey", "Facility Type": "Healthcare",
             "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555"},
        ]
        impl = [
            {"Site ID": "ASM-TR-01", "Internet Provider": "ERG Controls", "SSID": "Net",
             "Tag clean-to-red timeout": "", "Last Verified": "2025-01-01"},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[],
                                   site_id="ASM-TR-01", implementation=impl)
        tcr_issues = [r for r in result if r["field"] == "Tag clean-to-red timeout"]
        assert len(tcr_issues) == 1
        assert tcr_issues[0]["severity"] == "must"

    def test_healthcare_site_clean_hygiene_not_flagged(self):
        """Healthcare site missing clean_hygiene_time → NOT flagged (Food-only)."""
        sites = [
            {"Site ID": "ASM-TR-01", "Customer": "Anadolu", "City": "Gebze",
             "Country": "Turkey", "Facility Type": "Healthcare",
             "Contract Status": "Active", "Supervisor 1": "Ali", "Phone 1": "555"},
        ]
        impl = [
            {"Site ID": "ASM-TR-01", "Internet Provider": "ERG Controls", "SSID": "Net",
             "Clean hygiene time": "", "Last Verified": "2025-01-01"},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[],
                                   site_id="ASM-TR-01", implementation=impl)
        ch_issues = [r for r in result if r["field"] == "Clean hygiene time"]
        assert len(ch_issues) == 0

    def test_any_site_missing_gateway_placement_is_important(self):
        """Any site missing gateway_placement → 🟡 important."""
        sites = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros", "City": "Istanbul",
             "Country": "Turkey", "Facility Type": "Food",
             "Contract Status": "Active", "Supervisor 1": "Ahmet", "Phone 1": "123"},
        ]
        impl = [
            {"Site ID": "MIG-TR-01", "Internet Provider": "ERG Controls", "SSID": "Net",
             "Gateway placement": "", "Last Verified": "2025-01-01"},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[],
                                   site_id="MIG-TR-01", implementation=impl)
        gw_issues = [r for r in result if r["field"] == "Gateway placement"]
        assert len(gw_issues) == 1
        assert gw_issues[0]["severity"] == "important"

    def test_impl_must_fields_flagged(self):
        """Missing Internet Provider → 🔴 must."""
        sites = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros", "City": "Istanbul",
             "Country": "Turkey", "Facility Type": "Food",
             "Contract Status": "Active", "Supervisor 1": "Ahmet", "Phone 1": "123"},
        ]
        impl = [
            {"Site ID": "MIG-TR-01", "Internet Provider": "", "SSID": "Net",
             "Last Verified": "2025-01-01"},
        ]
        result = find_missing_data(sites=sites, hardware=[], support=[],
                                   site_id="MIG-TR-01", implementation=impl)
        ip_issues = [r for r in result if r["field"] == "Internet Provider"]
        assert len(ip_issues) == 1
        assert ip_issues[0]["severity"] == "must"


class TestMissingDataConditionalImportance:
    """Test conditional importance rules."""

    def test_fw_version_flagged_for_tag(self):
        """FW Version is important for Tag devices."""
        hardware = [
            {"Site ID": "MIG-TR-01", "Device Type": "Tag", "Qty": 20,
             "FW Version": "", "HW Version": "1.0"},
        ]
        result = find_missing_data(sites=[], hardware=hardware, support=[], site_id="MIG-TR-01")
        fw_issues = [r for r in result if r["field"] == "FW Version"]
        assert len(fw_issues) == 1

    def test_fw_version_not_flagged_for_charging_dock(self):
        """FW Version is NOT important for Charging Dock."""
        hardware = [
            {"Site ID": "MIG-TR-01", "Device Type": "Charging Dock", "Qty": 2,
             "FW Version": "", "HW Version": ""},
        ]
        result = find_missing_data(sites=[], hardware=hardware, support=[], site_id="MIG-TR-01")
        fw_issues = [r for r in result if r["field"] == "FW Version"]
        assert len(fw_issues) == 0

    def test_fw_version_not_flagged_for_other(self):
        """FW Version is NOT important for 'Other' device type."""
        hardware = [
            {"Site ID": "MIG-TR-01", "Device Type": "Other", "Qty": 1,
             "FW Version": "", "HW Version": ""},
        ]
        result = find_missing_data(sites=[], hardware=hardware, support=[], site_id="MIG-TR-01")
        fw_issues = [r for r in result if r["field"] in ("FW Version", "HW Version")]
        assert len(fw_issues) == 0

    def test_root_cause_flagged_when_status_resolved(self):
        """Root cause is must when status is not Open."""
        support = [
            {"Site ID": "MIG-TR-01", "Ticket ID": "SUP-001",
             "Status": "Resolved", "Root Cause": "", "Resolution": "Fixed"},
        ]
        result = find_missing_data(sites=[], hardware=[], support=support, site_id="MIG-TR-01")
        rc_issues = [r for r in result if r["field"] == "Root Cause"]
        assert len(rc_issues) == 1
        assert rc_issues[0]["severity"] == "must"

    def test_root_cause_not_flagged_when_status_open(self):
        """Root cause is NOT flagged when status is Open."""
        support = [
            {"Site ID": "MIG-TR-01", "Ticket ID": "SUP-001",
             "Status": "Open", "Root Cause": "", "Resolution": ""},
        ]
        result = find_missing_data(sites=[], hardware=[], support=support, site_id="MIG-TR-01")
        rc_issues = [r for r in result if r["field"] == "Root Cause"]
        assert len(rc_issues) == 0

    def test_resolution_flagged_when_resolved(self):
        """Resolution is must when status is Resolved."""
        support = [
            {"Site ID": "MIG-TR-01", "Ticket ID": "SUP-002",
             "Status": "Resolved", "Root Cause": "FW Bug", "Resolution": ""},
        ]
        result = find_missing_data(sites=[], hardware=[], support=support, site_id="MIG-TR-01")
        fields = [r["field"] for r in result if r["tab"] == "Support Log"]
        assert "Resolution" in fields
        res_issues = [r for r in result if r["field"] == "Resolution"]
        assert res_issues[0]["severity"] == "must"

    def test_pending_root_cause_still_flagged(self):
        """Root cause 'Pending' is flagged for non-Open statuses with must severity."""
        support = [
            {"Site ID": "MIG-TR-01", "Ticket ID": "SUP-001",
             "Status": "Follow-up (ERG)", "Root Cause": "Pending", "Resolution": ""},
        ]
        result = find_missing_data(sites=[], hardware=[], support=support, site_id="MIG-TR-01")
        rc_issues = [r for r in result if r["field"] == "Root Cause"]
        assert len(rc_issues) == 1
        assert "Pending" in rc_issues[0]["detail"]
        assert rc_issues[0]["severity"] == "must"


class TestStaleData:
    """Test stale data detection (Last Verified > threshold)."""

    def test_stale_hardware(self):
        old_date = (date.today() - timedelta(days=45)).isoformat()
        hardware = [
            {"Site ID": "MIG-TR-01", "Device Type": "Tag", "Qty": 20, "Last Verified": old_date},
        ]
        result = find_stale_data(hardware=hardware, implementation=[], site_id="MIG-TR-01", threshold_days=30)
        assert len(result) == 1
        assert result[0]["tab"] == "Hardware Inventory"
        assert result[0]["site_id"] == "MIG-TR-01"

    def test_fresh_hardware_not_stale(self):
        fresh_date = (date.today() - timedelta(days=5)).isoformat()
        hardware = [
            {"Site ID": "MIG-TR-01", "Device Type": "Tag", "Qty": 20, "Last Verified": fresh_date},
        ]
        result = find_stale_data(hardware=hardware, implementation=[], site_id="MIG-TR-01", threshold_days=30)
        assert len(result) == 0

    def test_missing_last_verified_is_stale(self):
        hardware = [
            {"Site ID": "MIG-TR-01", "Device Type": "Gateway", "Qty": 1, "Last Verified": ""},
        ]
        result = find_stale_data(hardware=hardware, implementation=[], site_id="MIG-TR-01", threshold_days=30)
        assert len(result) == 1

    def test_stale_implementation(self):
        old_date = (date.today() - timedelta(days=60)).isoformat()
        implementation = [
            {"Site ID": "MIG-TR-01", "Last Verified": old_date},
        ]
        result = find_stale_data(hardware=[], implementation=implementation, site_id="MIG-TR-01", threshold_days=30)
        assert len(result) == 1
        assert result[0]["tab"] == "Implementation Details"

    def test_custom_threshold(self):
        old_date = (date.today() - timedelta(days=45)).isoformat()
        hardware = [
            {"Site ID": "MIG-TR-01", "Device Type": "Tag", "Qty": 20, "Last Verified": old_date},
        ]
        result = find_stale_data(hardware=hardware, implementation=[], site_id="MIG-TR-01", threshold_days=60)
        assert len(result) == 0

    def test_all_sites_stale_scan(self):
        old_date = (date.today() - timedelta(days=45)).isoformat()
        hardware = [
            {"Site ID": "MIG-TR-01", "Device Type": "Tag", "Qty": 20, "Last Verified": old_date},
            {"Site ID": "MCD-EG-01", "Device Type": "Tag", "Qty": 15, "Last Verified": ""},
        ]
        result = find_stale_data(hardware=hardware, implementation=[], site_id=None, threshold_days=30)
        site_ids = {r["site_id"] for r in result}
        assert "MIG-TR-01" in site_ids
        assert "MCD-EG-01" in site_ids


class TestDataQualityFormatter:
    """Test Slack Block Kit formatting for data quality responses."""

    def test_missing_data_with_issues(self):
        issues = [
            {"site_id": "MIG-TR-01", "tab": "Sites", "field": "City",
             "detail": "City boş", "severity": "must"},
            {"site_id": "MIG-TR-01", "tab": "Hardware Inventory", "field": "FW Version",
             "detail": "Tag: FW Version boş", "severity": "important"},
        ]
        blocks = format_data_quality_response("missing_data", issues, site_id="MIG-TR-01")
        text = json.dumps(blocks, ensure_ascii=False)
        assert "Eksik Veri Raporu" in text
        assert "MIG-TR-01" in text
        assert "🔴" in text
        assert "🟡" in text

    def test_stale_data_with_issues(self):
        issues = [
            {"site_id": "MIG-TR-01", "tab": "Hardware Inventory", "detail": "Tag: 45 gün önce doğrulanmış"},
        ]
        blocks = format_data_quality_response("stale_data", issues, site_id="MIG-TR-01")
        text = json.dumps(blocks)
        assert "Eski Veri Raporu" in text
        assert "1 sorun" in text

    def test_no_issues_shows_success(self):
        blocks = format_data_quality_response("missing_data", [], site_id="MIG-TR-01")
        text = json.dumps(blocks, ensure_ascii=False)
        assert "Sorun bulunamadı" in text

    def test_all_sites_scope_in_title(self):
        blocks = format_data_quality_response("missing_data", [], site_id=None)
        text = json.dumps(blocks, ensure_ascii=False)
        assert "Tüm sahalar" in text


class TestMissingDataStock:
    """Test missing data detection on Stock tab."""

    def test_stock_must_field_flagged(self):
        """Missing must field (e.g., no Condition) → severity='must'."""
        stock = [
            {"Location": "Istanbul Office", "Device Type": "Tag", "Qty": 50,
             "Condition": "", "HW Version": "1.0", "FW Version": "2.4.1",
             "Reserved For": "", "Notes": "", "Last Verified": "2025-01-01"},
        ]
        result = find_missing_data(sites=[], hardware=[], support=[],
                                   site_id=None, stock=stock)
        cond_issues = [r for r in result if r["tab"] == "Stock" and r["field"] == "Condition"]
        assert len(cond_issues) == 1
        assert cond_issues[0]["severity"] == "must"

    def test_stock_important_field_flagged(self):
        """Missing important field (FW Version) → severity='important'."""
        stock = [
            {"Location": "Istanbul Office", "Device Type": "Tag", "Qty": 50,
             "Condition": "New", "HW Version": "", "FW Version": "",
             "Reserved For": "", "Notes": "", "Last Verified": "2025-01-01"},
        ]
        result = find_missing_data(sites=[], hardware=[], support=[],
                                   site_id=None, stock=stock)
        fw_issues = [r for r in result if r["tab"] == "Stock" and r["field"] == "FW Version"]
        assert len(fw_issues) == 1
        assert fw_issues[0]["severity"] == "important"

    def test_stock_optional_not_flagged(self):
        """Optional fields (Reserved For, Notes) are never flagged."""
        stock = [
            {"Location": "Istanbul Office", "Device Type": "Tag", "Qty": 50,
             "Condition": "New", "HW Version": "1.0", "FW Version": "2.4.1",
             "Reserved For": "", "Notes": "", "Last Verified": "2025-01-01"},
        ]
        result = find_missing_data(sites=[], hardware=[], support=[],
                                   site_id=None, stock=stock)
        stock_issues = [r for r in result if r["tab"] == "Stock"]
        fields = [r["field"] for r in stock_issues]
        assert "Reserved For" not in fields
        assert "Notes" not in fields


class TestOpenTicketAging:
    """Test open ticket aging check (>3 days)."""

    def test_old_open_ticket_flagged(self):
        """Open ticket older than 3 days → flagged."""
        old_date = (date.today() - timedelta(days=5)).isoformat()
        support = [
            {"Site ID": "MIG-TR-01", "Ticket ID": "SUP-001",
             "Status": "Open", "Received Date": old_date,
             "Root Cause": "", "Resolution": ""},
        ]
        result = find_missing_data(sites=[], hardware=[], support=support, site_id="MIG-TR-01")
        aging_issues = [r for r in result if r.get("field") == "Aging"]
        assert len(aging_issues) == 1
        assert "5" in aging_issues[0]["detail"]

    def test_recent_open_ticket_not_flagged(self):
        """Open ticket within 3 days → not flagged for aging."""
        recent_date = (date.today() - timedelta(days=1)).isoformat()
        support = [
            {"Site ID": "MIG-TR-01", "Ticket ID": "SUP-001",
             "Status": "Open", "Received Date": recent_date,
             "Root Cause": "", "Resolution": ""},
        ]
        result = find_missing_data(sites=[], hardware=[], support=support, site_id="MIG-TR-01")
        aging_issues = [r for r in result if r.get("field") == "Aging"]
        assert len(aging_issues) == 0

    def test_resolved_ticket_not_flagged_for_aging(self):
        """Resolved tickets are never flagged for aging regardless of age."""
        old_date = (date.today() - timedelta(days=30)).isoformat()
        support = [
            {"Site ID": "MIG-TR-01", "Ticket ID": "SUP-001",
             "Status": "Resolved", "Received Date": old_date,
             "Root Cause": "FW Bug", "Resolution": "Fixed",
             "Resolved Date": old_date},
        ]
        result = find_missing_data(sites=[], hardware=[], support=support, site_id="MIG-TR-01")
        aging_issues = [r for r in result if r.get("field") == "Aging"]
        assert len(aging_issues) == 0

    def test_followup_ticket_flagged_for_aging(self):
        """Follow-up tickets >3 days old are flagged."""
        old_date = (date.today() - timedelta(days=5)).isoformat()
        support = [
            {"Site ID": "MIG-TR-01", "Ticket ID": "SUP-001",
             "Status": "Follow-up (ERG)", "Received Date": old_date,
             "Root Cause": "FW Bug", "Resolution": ""},
        ]
        result = find_missing_data(sites=[], hardware=[], support=support, site_id="MIG-TR-01")
        aging_issues = [r for r in result if r.get("field") == "Aging"]
        assert len(aging_issues) == 1


class TestStaleDataStock:
    """Test stale data detection for Stock tab."""

    def test_stale_stock(self):
        old_date = (date.today() - timedelta(days=45)).isoformat()
        stock = [
            {"Location": "Istanbul Office", "Device Type": "Tag", "Qty": 50,
             "Last Verified": old_date},
        ]
        result = find_stale_data(hardware=[], implementation=[], site_id=None,
                                 threshold_days=30, stock=stock)
        stock_issues = [r for r in result if r["tab"] == "Stock"]
        assert len(stock_issues) == 1

    def test_fresh_stock_not_stale(self):
        fresh_date = (date.today() - timedelta(days=5)).isoformat()
        stock = [
            {"Location": "Istanbul Office", "Device Type": "Tag", "Qty": 50,
             "Last Verified": fresh_date},
        ]
        result = find_stale_data(hardware=[], implementation=[], site_id=None,
                                 threshold_days=30, stock=stock)
        stock_issues = [r for r in result if r["tab"] == "Stock"]
        assert len(stock_issues) == 0

    def test_missing_last_verified_stock_is_stale(self):
        stock = [
            {"Location": "Istanbul Office", "Device Type": "Tag", "Qty": 50,
             "Last Verified": ""},
        ]
        result = find_stale_data(hardware=[], implementation=[], site_id=None,
                                 threshold_days=30, stock=stock)
        stock_issues = [r for r in result if r["tab"] == "Stock"]
        assert len(stock_issues) == 1


class TestDataQualityQueryWiring:
    """Test that _handle_query correctly routes missing_data and stale_data."""

    @patch("app.handlers.common.get_sheets")
    def test_missing_data_query_calls_sheets(self, mock_get_sheets):
        from app.handlers.common import _handle_query

        mock_sheets = MagicMock()
        mock_sheets.read_sites.return_value = [
            {"Site ID": "MIG-TR-01", "Customer": "Migros", "City": "",
             "Country": "Turkey", "Contract Status": "Active",
             "Supervisor 1": "Ahmet", "Phone 1": "123"},
        ]
        mock_sheets.read_hardware.return_value = []
        mock_sheets.read_support_log.return_value = []
        mock_sheets.read_all_implementation.return_value = []
        mock_get_sheets.return_value = mock_sheets

        say = MagicMock()
        _handle_query(
            {"query_type": "missing_data", "site_id": "MIG-TR-01"},
            thread_ts="T001",
            say=say,
        )
        # First call is query result, second is feedback buttons
        assert say.call_count >= 1
        blocks = say.call_args_list[0][1]["blocks"]
        text = json.dumps(blocks)
        assert "Eksik Veri Raporu" in text

    @patch("app.handlers.common.get_sheets")
    def test_stale_data_query_calls_sheets(self, mock_get_sheets):
        from app.handlers.common import _handle_query

        old_date = (date.today() - timedelta(days=45)).isoformat()
        mock_sheets = MagicMock()
        mock_sheets.read_hardware.return_value = [
            {"Site ID": "MIG-TR-01", "Device Type": "Tag", "Qty": 20, "Last Verified": old_date},
        ]
        mock_sheets.read_all_implementation.return_value = []
        mock_get_sheets.return_value = mock_sheets

        say = MagicMock()
        _handle_query(
            {"query_type": "stale_data", "site_id": "MIG-TR-01"},
            thread_ts="T001",
            say=say,
        )
        # First call is query result, second is feedback buttons
        assert say.call_count >= 1
        blocks = say.call_args_list[0][1]["blocks"]
        text = json.dumps(blocks)
        assert "Eski Veri Raporu" in text
