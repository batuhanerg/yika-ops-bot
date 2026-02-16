"""Tests for hardware upsert — update existing rows instead of blind append.

Problem A: "ASM'ye 5 tag ekledim" should update the existing ASM-TR-01 Tag row
(Qty 32 → 37) instead of creating a duplicate row.

Problem B (v1.8.6): Version-aware matching — different HW versions should be
separate rows. "ASM'ye 3 tag ekledim, 3.6.2 sürüm" should NOT update the
existing 3.6.1 row but create a new 3.6.2 row.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.handlers.common import thread_store
from app.services.sheets import SheetsService


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_HW_HEADERS = ["Site ID", "Device Type", "HW Version", "FW Version", "Qty", "Last Verified", "Notes"]

_SAMPLE_HW_ROWS = [
    _HW_HEADERS,
    ["ASM-TR-01", "Tag", "3.0", "2.1", "32", "2025-01-15", ""],
    ["ASM-TR-01", "Anchor", "1.0", "1.2", "10", "2025-01-15", "floor anchors"],
    ["MNG-EG-01", "Tag", "2.0", "", "15", "2025-02-01", ""],
]


def _make_sheets_service(all_values=None):
    """Create a SheetsService with mocked worksheet data."""
    if all_values is None:
        all_values = list(_SAMPLE_HW_ROWS)
    with patch("app.services.sheets.SheetsService._connect"):
        svc = SheetsService.__new__(SheetsService)
        ws = MagicMock()
        ws.get_all_values.return_value = all_values
        svc.spreadsheet = MagicMock()
        svc._ws_cache = {"Hardware Inventory": ws}
        return svc, ws


# ===========================================================================
# SheetsService.find_hardware_row
# ===========================================================================


class TestFindHardwareRow:
    """Test looking up existing hardware rows by Site ID + Device Type."""

    def test_finds_existing_row(self):
        svc, _ = _make_sheets_service()
        result = svc.find_hardware_row("ASM-TR-01", "Tag")
        assert result is not None
        row_idx, row_data = result
        assert row_idx == 2
        assert row_data["Qty"] == "32"
        assert row_data["HW Version"] == "3.0"
        assert row_data["FW Version"] == "2.1"

    def test_case_insensitive_device_type(self):
        """'tag' matches 'Tag' in the sheet."""
        svc, _ = _make_sheets_service()
        result = svc.find_hardware_row("ASM-TR-01", "tag")
        assert result is not None
        assert result[0] == 2

    def test_not_found_device_type(self):
        svc, _ = _make_sheets_service()
        result = svc.find_hardware_row("ASM-TR-01", "Gateway")
        assert result is None

    def test_not_found_site_id(self):
        svc, _ = _make_sheets_service()
        result = svc.find_hardware_row("XXX-YY-99", "Tag")
        assert result is None

    def test_empty_sheet(self):
        svc, _ = _make_sheets_service([_HW_HEADERS])
        result = svc.find_hardware_row("ASM-TR-01", "Tag")
        assert result is None


# ===========================================================================
# SheetsService.update_hardware_row
# ===========================================================================


class TestUpdateHardwareRow:
    """Test in-place updates to hardware rows."""

    def test_updates_qty_and_last_verified(self):
        svc, ws = _make_sheets_service()
        svc.update_hardware_row(2, {"Qty": 37, "Last Verified": "2026-02-15"})
        # Qty is column 5, Last Verified is column 6
        ws.update_cell.assert_any_call(2, 5, 37)
        ws.update_cell.assert_any_call(2, 6, "2026-02-15")

    def test_updates_hw_version(self):
        svc, ws = _make_sheets_service()
        svc.update_hardware_row(3, {"HW Version": "4.0"})
        # HW Version is column 3
        ws.update_cell.assert_called_once_with(3, 3, "4.0")


# ===========================================================================
# Qty mode detection
# ===========================================================================


class TestQtyModeDetection:
    """Test _detect_qty_mode for add/subtract/set from raw message."""

    def test_addition_keywords_turkish(self):
        from app.handlers.common import _detect_qty_mode
        assert _detect_qty_mode("ASM'ye 5 tag ekledim") == "add"

    def test_addition_keywords_english(self):
        from app.handlers.common import _detect_qty_mode
        assert _detect_qty_mode("added 5 tags to ASM") == "add"

    def test_removal_keywords_turkish(self):
        from app.handlers.common import _detect_qty_mode
        assert _detect_qty_mode("ASM'den 5 tag çıkardım") == "subtract"

    def test_removal_keywords_english(self):
        from app.handlers.common import _detect_qty_mode
        assert _detect_qty_mode("removed 3 tags from site") == "subtract"

    def test_no_keywords_is_absolute_set(self):
        from app.handlers.common import _detect_qty_mode
        assert _detect_qty_mode("ASM'de 32 tag var") == "set"

    def test_neutral_message_is_set(self):
        from app.handlers.common import _detect_qty_mode
        assert _detect_qty_mode("donanım bilgisi güncelle") == "set"


# ===========================================================================
# Hardware entry enrichment
# ===========================================================================


class TestEnrichHardwareEntries:
    """Test enrich_hardware_entries — annotates data with existing row info."""

    def test_enriches_existing_entry(self):
        from app.handlers.common import enrich_hardware_entries
        svc, _ = _make_sheets_service()
        data = {
            "site_id": "ASM-TR-01",
            "entries": [{"device_type": "Tag", "qty": 5}],
        }
        enrich_hardware_entries(data, "ASM'ye 5 tag ekledim", svc)
        entry = data["entries"][0]
        assert entry["_existing_qty"] == 32
        assert entry["_row_index"] == 2
        assert entry["_qty_mode"] == "add"

    def test_new_entry_has_none_existing(self):
        from app.handlers.common import enrich_hardware_entries
        svc, _ = _make_sheets_service()
        data = {
            "site_id": "ASM-TR-01",
            "entries": [{"device_type": "Gateway", "qty": 3}],
        }
        enrich_hardware_entries(data, "3 gateway ekledim", svc)
        entry = data["entries"][0]
        assert entry["_existing_qty"] is None
        assert entry["_row_index"] is None
        assert entry["_qty_mode"] == "add"

    def test_enriches_single_entry_format(self):
        """When data has device_type directly (not entries list)."""
        from app.handlers.common import enrich_hardware_entries
        svc, _ = _make_sheets_service()
        data = {
            "site_id": "ASM-TR-01",
            "device_type": "Tag",
            "qty": 5,
        }
        enrich_hardware_entries(data, "ASM'ye 5 tag ekledim", svc)
        assert data["_existing_qty"] == 32
        assert data["_row_index"] == 2
        assert data["_qty_mode"] == "add"

    def test_enriches_multiple_entries(self):
        from app.handlers.common import enrich_hardware_entries
        svc, _ = _make_sheets_service()
        data = {
            "site_id": "ASM-TR-01",
            "entries": [
                {"device_type": "Tag", "qty": 5},
                {"device_type": "Anchor", "qty": 3},
                {"device_type": "Gateway", "qty": 2},
            ],
        }
        enrich_hardware_entries(data, "tag anchor gateway ekledim", svc)
        assert data["entries"][0]["_existing_qty"] == 32  # Tag exists
        assert data["entries"][1]["_existing_qty"] == 10  # Anchor exists
        assert data["entries"][2]["_existing_qty"] is None  # Gateway new


# ===========================================================================
# Upsert write logic in _execute_write
# ===========================================================================


class TestHardwareUpsertWrite:
    """Test the upsert logic in _execute_write."""

    def test_existing_row_updates_qty_add(self):
        """Existing Tag row: 32 + 5 = 37."""
        from app.handlers.actions import _execute_write
        svc = MagicMock()
        data = {
            "site_id": "ASM-TR-01",
            "entries": [{
                "device_type": "Tag",
                "qty": 5,
                "_existing_qty": 32,
                "_row_index": 2,
                "_qty_mode": "add",
                "_existing_row": {"HW Version": "3.0", "FW Version": "2.1", "Notes": ""},
                "last_verified": "2026-02-15",
            }],
        }
        _execute_write(svc, "update_hardware", data)
        svc.update_hardware_row.assert_called_once()
        row_idx, updates = svc.update_hardware_row.call_args[0]
        assert row_idx == 2
        assert updates["Qty"] == 37

    def test_existing_row_subtract(self):
        """Existing Tag row: 32 - 5 = 27."""
        from app.handlers.actions import _execute_write
        svc = MagicMock()
        data = {
            "site_id": "ASM-TR-01",
            "entries": [{
                "device_type": "Tag",
                "qty": 5,
                "_existing_qty": 32,
                "_row_index": 2,
                "_qty_mode": "subtract",
                "_existing_row": {"HW Version": "3.0", "FW Version": "2.1", "Notes": ""},
                "last_verified": "2026-02-15",
            }],
        }
        _execute_write(svc, "update_hardware", data)
        _, updates = svc.update_hardware_row.call_args[0]
        assert updates["Qty"] == 27

    def test_existing_row_absolute_set(self):
        """Absolute set: qty becomes exactly what user says."""
        from app.handlers.actions import _execute_write
        svc = MagicMock()
        data = {
            "site_id": "ASM-TR-01",
            "entries": [{
                "device_type": "Tag",
                "qty": 32,
                "_existing_qty": 32,
                "_row_index": 2,
                "_qty_mode": "set",
                "_existing_row": {"HW Version": "3.0", "FW Version": "2.1", "Notes": ""},
                "last_verified": "2026-02-15",
            }],
        }
        _execute_write(svc, "update_hardware", data)
        _, updates = svc.update_hardware_row.call_args[0]
        assert updates["Qty"] == 32

    def test_new_row_appends(self):
        """No existing row → calls append_hardware."""
        from app.handlers.actions import _execute_write
        svc = MagicMock()
        data = {
            "site_id": "ASM-TR-01",
            "entries": [{
                "device_type": "Gateway",
                "qty": 3,
                "_existing_qty": None,
                "_row_index": None,
                "_qty_mode": "add",
                "last_verified": "2026-02-15",
            }],
        }
        _execute_write(svc, "update_hardware", data)
        svc.append_hardware.assert_called_once()
        svc.update_hardware_row.assert_not_called()

    def test_preserves_existing_versions(self):
        """When user doesn't provide versions, existing ones are NOT overwritten."""
        from app.handlers.actions import _execute_write
        svc = MagicMock()
        data = {
            "site_id": "ASM-TR-01",
            "entries": [{
                "device_type": "Tag",
                "qty": 5,
                "_existing_qty": 32,
                "_row_index": 2,
                "_qty_mode": "add",
                "_existing_row": {"HW Version": "3.0", "FW Version": "2.1", "Notes": "old note"},
                "last_verified": "2026-02-15",
            }],
        }
        _execute_write(svc, "update_hardware", data)
        _, updates = svc.update_hardware_row.call_args[0]
        # Should NOT include HW/FW Version (user didn't provide new ones)
        assert "HW Version" not in updates
        assert "FW Version" not in updates

    def test_user_provided_version_overwrites(self):
        """When user explicitly provides new HW version, it's included in update."""
        from app.handlers.actions import _execute_write
        svc = MagicMock()
        data = {
            "site_id": "ASM-TR-01",
            "entries": [{
                "device_type": "Tag",
                "qty": 5,
                "hw_version": "4.0",
                "_existing_qty": 32,
                "_row_index": 2,
                "_qty_mode": "add",
                "_existing_row": {"HW Version": "3.0", "FW Version": "2.1", "Notes": ""},
                "last_verified": "2026-02-15",
            }],
        }
        _execute_write(svc, "update_hardware", data)
        _, updates = svc.update_hardware_row.call_args[0]
        assert updates["HW Version"] == "4.0"

    def test_single_entry_upsert(self):
        """Single-entry format (no entries list) also supports upsert."""
        from app.handlers.actions import _execute_write
        svc = MagicMock()
        data = {
            "site_id": "ASM-TR-01",
            "device_type": "Tag",
            "qty": 5,
            "_existing_qty": 32,
            "_row_index": 2,
            "_qty_mode": "add",
            "_existing_row": {"HW Version": "3.0", "FW Version": "2.1", "Notes": ""},
            "last_verified": "2026-02-15",
        }
        _execute_write(svc, "update_hardware", data)
        svc.update_hardware_row.assert_called_once()
        _, updates = svc.update_hardware_row.call_args[0]
        assert updates["Qty"] == 37


# ===========================================================================
# Confirmation card display
# ===========================================================================


class TestConfirmationCardDisplay:
    """Test that the confirmation card shows update vs new row context."""

    def test_update_shows_qty_change(self):
        from app.utils.formatters import format_confirmation_message
        data = {
            "operation": "update_hardware",
            "site_id": "ASM-TR-01",
            "entries": [{
                "device_type": "Tag",
                "qty": 5,
                "_existing_qty": 32,
                "_qty_mode": "add",
            }],
        }
        blocks = format_confirmation_message(data)
        text = str(blocks)
        assert "32 → 37" in text
        assert "eklendi" in text

    def test_subtract_shows_decrease(self):
        from app.utils.formatters import format_confirmation_message
        data = {
            "operation": "update_hardware",
            "site_id": "ASM-TR-01",
            "entries": [{
                "device_type": "Tag",
                "qty": 5,
                "_existing_qty": 32,
                "_qty_mode": "subtract",
            }],
        }
        blocks = format_confirmation_message(data)
        text = str(blocks)
        assert "32 → 27" in text

    def test_absolute_set_shows_change(self):
        from app.utils.formatters import format_confirmation_message
        data = {
            "operation": "update_hardware",
            "site_id": "ASM-TR-01",
            "entries": [{
                "device_type": "Tag",
                "qty": 50,
                "_existing_qty": 32,
                "_qty_mode": "set",
            }],
        }
        blocks = format_confirmation_message(data)
        text = str(blocks)
        assert "32 → 50" in text

    def test_new_row_shows_yeni_kayit(self):
        from app.utils.formatters import format_confirmation_message
        data = {
            "operation": "update_hardware",
            "site_id": "ASM-TR-01",
            "entries": [{
                "device_type": "Gateway",
                "qty": 3,
                "_existing_qty": None,
                "_qty_mode": "add",
            }],
        }
        blocks = format_confirmation_message(data)
        text = str(blocks)
        assert "yeni" in text.lower()

    def test_negative_result_shows_warning(self):
        from app.utils.formatters import format_confirmation_message
        data = {
            "operation": "update_hardware",
            "site_id": "ASM-TR-01",
            "entries": [{
                "device_type": "Tag",
                "qty": 40,
                "_existing_qty": 32,
                "_qty_mode": "subtract",
            }],
        }
        blocks = format_confirmation_message(data)
        text = str(blocks)
        assert "⚠️" in text


# ===========================================================================
# Version-aware upsert (v1.8.6)
# ===========================================================================

# Sheet with multiple Tag rows at different HW versions
_MULTI_VERSION_ROWS = [
    _HW_HEADERS,
    ["ASM-TR-01", "Tag", "3.6.1", "2.1", "32", "2025-01-15", ""],
    ["ASM-TR-01", "Tag", "3.6.2", "2.2", "5", "2025-02-01", ""],
    ["ASM-TR-01", "Anchor", "1.0", "1.2", "10", "2025-01-15", ""],
    ["MNG-EG-01", "Tag", "2.0", "", "15", "2025-02-01", ""],
]


class TestFindHardwareRowVersionAware:
    """Test version-aware lookup in find_hardware_row."""

    def test_version_match_finds_correct_row(self):
        """hw_version='3.6.1' matches row 2 (not row 3)."""
        svc, _ = _make_sheets_service(_MULTI_VERSION_ROWS)
        result = svc.find_hardware_row("ASM-TR-01", "Tag", hw_version="3.6.1")
        assert result is not None
        row_idx, row_data = result
        assert row_idx == 2
        assert row_data["HW Version"] == "3.6.1"
        assert row_data["Qty"] == "32"

    def test_version_match_finds_second_row(self):
        """hw_version='3.6.2' matches row 3."""
        svc, _ = _make_sheets_service(_MULTI_VERSION_ROWS)
        result = svc.find_hardware_row("ASM-TR-01", "Tag", hw_version="3.6.2")
        assert result is not None
        row_idx, row_data = result
        assert row_idx == 3
        assert row_data["HW Version"] == "3.6.2"
        assert row_data["Qty"] == "5"

    def test_version_not_found_returns_none(self):
        """hw_version='4.0' doesn't exist → None."""
        svc, _ = _make_sheets_service(_MULTI_VERSION_ROWS)
        result = svc.find_hardware_row("ASM-TR-01", "Tag", hw_version="4.0")
        assert result is None

    def test_no_version_single_row_matches(self):
        """No hw_version + only one Tag row → returns that row."""
        svc, _ = _make_sheets_service(_SAMPLE_HW_ROWS)
        result = svc.find_hardware_row("ASM-TR-01", "Tag", hw_version=None)
        assert result is not None
        assert result[0] == 2

    def test_no_version_multiple_rows_returns_none(self):
        """No hw_version + multiple Tag rows at different versions → None (ambiguous)."""
        svc, _ = _make_sheets_service(_MULTI_VERSION_ROWS)
        result = svc.find_hardware_row("ASM-TR-01", "Tag", hw_version=None)
        assert result is None

    def test_backward_compat_no_version_param(self):
        """Calling without hw_version at all still works (single match)."""
        svc, _ = _make_sheets_service(_SAMPLE_HW_ROWS)
        result = svc.find_hardware_row("ASM-TR-01", "Tag")
        assert result is not None
        assert result[0] == 2


class TestEnrichVersionAware:
    """Test enrichment passes hw_version to find_hardware_row."""

    def test_enriches_with_matching_version(self):
        """Entry with hw_version='3.6.1' finds correct row."""
        from app.handlers.common import enrich_hardware_entries
        svc, _ = _make_sheets_service(_MULTI_VERSION_ROWS)
        data = {
            "site_id": "ASM-TR-01",
            "entries": [{"device_type": "Tag", "qty": 3, "hw_version": "3.6.1"}],
        }
        enrich_hardware_entries(data, "ASM'ye 3 tag ekledim", svc)
        entry = data["entries"][0]
        assert entry["_existing_qty"] == 32
        assert entry["_row_index"] == 2

    def test_enriches_new_version_as_none(self):
        """Entry with hw_version='4.0' (not in sheet) → new row."""
        from app.handlers.common import enrich_hardware_entries
        svc, _ = _make_sheets_service(_MULTI_VERSION_ROWS)
        data = {
            "site_id": "ASM-TR-01",
            "entries": [{"device_type": "Tag", "qty": 3, "hw_version": "4.0"}],
        }
        enrich_hardware_entries(data, "3 tag ekledim", svc)
        entry = data["entries"][0]
        assert entry["_existing_qty"] is None
        assert entry["_row_index"] is None

    def test_no_version_multi_rows_is_ambiguous(self):
        """No hw_version + multiple Tag rows → _existing_qty None, _ambiguous True."""
        from app.handlers.common import enrich_hardware_entries
        svc, _ = _make_sheets_service(_MULTI_VERSION_ROWS)
        data = {
            "site_id": "ASM-TR-01",
            "entries": [{"device_type": "Tag", "qty": 3}],
        }
        enrich_hardware_entries(data, "3 tag ekledim", svc)
        entry = data["entries"][0]
        assert entry["_existing_qty"] is None
        assert entry.get("_ambiguous_versions") is True

    def test_no_version_single_row_still_matches(self):
        """No hw_version + single Tag row → matches as before."""
        from app.handlers.common import enrich_hardware_entries
        svc, _ = _make_sheets_service(_SAMPLE_HW_ROWS)
        data = {
            "site_id": "ASM-TR-01",
            "entries": [{"device_type": "Tag", "qty": 5}],
        }
        enrich_hardware_entries(data, "ASM'ye 5 tag ekledim", svc)
        entry = data["entries"][0]
        assert entry["_existing_qty"] == 32
        assert entry["_row_index"] == 2


class TestConfirmationCardVersion:
    """Test confirmation card shows version info."""

    def test_update_shows_version_in_label(self):
        from app.utils.formatters import format_confirmation_message
        data = {
            "operation": "update_hardware",
            "site_id": "ASM-TR-01",
            "entries": [{
                "device_type": "Tag",
                "hw_version": "3.6.1",
                "qty": 3,
                "_existing_qty": 32,
                "_qty_mode": "add",
            }],
        }
        blocks = format_confirmation_message(data)
        text = str(blocks)
        assert "3.6.1" in text
        assert "32 → 35" in text

    def test_new_version_row_shows_version(self):
        from app.utils.formatters import format_confirmation_message
        data = {
            "operation": "update_hardware",
            "site_id": "ASM-TR-01",
            "entries": [{
                "device_type": "Tag",
                "hw_version": "3.6.2",
                "qty": 3,
                "_existing_qty": None,
                "_qty_mode": "add",
            }],
        }
        blocks = format_confirmation_message(data)
        text = str(blocks)
        assert "3.6.2" in text
        assert "yeni" in text.lower()

    def test_ambiguous_shows_versions_list(self):
        """Ambiguous entry should show available versions."""
        from app.utils.formatters import format_confirmation_message
        data = {
            "operation": "update_hardware",
            "site_id": "ASM-TR-01",
            "entries": [{
                "device_type": "Tag",
                "qty": 3,
                "_existing_qty": None,
                "_qty_mode": "add",
                "_ambiguous_versions": True,
                "_available_versions": ["3.6.1", "3.6.2"],
            }],
        }
        blocks = format_confirmation_message(data)
        text = str(blocks)
        assert "3.6.1" in text
        assert "3.6.2" in text


class TestUpsertWriteVersionAware:
    """Test that upsert write handles version-specific rows."""

    def test_version_specified_updates_correct_row(self):
        from app.handlers.actions import _execute_write
        svc = MagicMock()
        data = {
            "site_id": "ASM-TR-01",
            "entries": [{
                "device_type": "Tag",
                "hw_version": "3.6.1",
                "qty": 3,
                "_existing_qty": 32,
                "_row_index": 2,
                "_qty_mode": "add",
                "_existing_row": {"HW Version": "3.6.1", "FW Version": "2.1", "Notes": ""},
                "last_verified": "2026-02-15",
            }],
        }
        _execute_write(svc, "update_hardware", data)
        svc.update_hardware_row.assert_called_once()
        row_idx, updates = svc.update_hardware_row.call_args[0]
        assert row_idx == 2
        assert updates["Qty"] == 35

    def test_new_version_appends_with_version(self):
        from app.handlers.actions import _execute_write
        svc = MagicMock()
        data = {
            "site_id": "ASM-TR-01",
            "entries": [{
                "device_type": "Tag",
                "hw_version": "3.6.2",
                "qty": 3,
                "_existing_qty": None,
                "_row_index": None,
                "_qty_mode": "add",
                "last_verified": "2026-02-15",
            }],
        }
        _execute_write(svc, "update_hardware", data)
        svc.append_hardware.assert_called_once()
        appended = svc.append_hardware.call_args[0][0]
        assert appended["hw_version"] == "3.6.2"
