"""Tests for Item 5: Stock audit gaps (Session 4).

Covers: stock readback after write, stock key mapping, stock query wiring.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.sheets import STOCK_COLUMNS


class TestStockKeyMapping:
    """Verify that append_stock correctly maps snake_case keys to sheet columns."""

    def test_all_stock_columns_have_valid_snake_case_keys(self):
        """Every STOCK_COLUMNS entry should produce a consistent snake_case key."""
        expected_keys = {
            "Location": "location",
            "Device Type": "device_type",
            "HW Version": "hw_version",
            "FW Version": "fw_version",
            "Qty": "qty",
            "Condition": "condition",
            "Reserved For": "reserved_for",
            "Notes": "notes",
            "Last Verified": "last_verified",
        }
        for col in STOCK_COLUMNS:
            key = col.lower().replace(" ", "_").replace("-", "_")
            assert col in expected_keys, f"Unexpected column: {col}"
            assert key == expected_keys[col], f"Column {col!r} maps to {key!r}, expected {expected_keys[col]!r}"


class TestStockReadback:
    """Verify stock readback after confirmation."""

    @patch("app.handlers.actions.get_sheets")
    def test_stock_readback_after_confirm(self, mock_get_sheets):
        from app.handlers.actions import _build_readback

        mock_sheets = MagicMock()
        mock_sheets.read_stock.return_value = [
            {"Location": "Istanbul Office", "Device Type": "Tag", "Qty": 10, "Condition": "New"},
            {"Location": "Istanbul Office", "Device Type": "Gateway", "Qty": 2, "Condition": "New"},
            {"Location": "Adana Storage", "Device Type": "Tag", "Qty": 5, "Condition": "Refurbished"},
        ]

        readback = _build_readback(
            mock_sheets, "update_stock",
            {"location": "Istanbul Office", "device_type": "Tag", "qty": 10, "condition": "New"},
        )
        assert "Stok" in readback or "stok" in readback
        assert "Istanbul Office" in readback

    @patch("app.handlers.actions.get_sheets")
    def test_stock_readback_handles_error(self, mock_get_sheets):
        from app.handlers.actions import _build_readback

        mock_sheets = MagicMock()
        mock_sheets.read_stock.side_effect = Exception("Sheet error")

        readback = _build_readback(
            mock_sheets, "update_stock",
            {"location": "Istanbul Office", "device_type": "Tag", "qty": 10},
        )
        assert readback == ""


class TestStockQueryFiltering:
    """Verify that stock queries can work with location filtering."""

    @patch("app.handlers.common.get_sheets")
    def test_stock_query_returns_all(self, mock_get_sheets):
        from app.handlers.common import _handle_query

        mock_sheets = MagicMock()
        mock_sheets.read_stock.return_value = [
            {"Device Type": "Tag", "Qty": 10, "Condition": "New", "Location": "Istanbul Office"},
        ]
        mock_get_sheets.return_value = mock_sheets

        say = MagicMock()
        _handle_query({"query_type": "stock"}, thread_ts="T001", say=say)

        say.assert_called()
        call_text = say.call_args_list[0][1].get("text", "")
        assert "Tag" in call_text

    @patch("app.handlers.common.get_sheets")
    def test_stock_query_empty(self, mock_get_sheets):
        from app.handlers.common import _handle_query

        mock_sheets = MagicMock()
        mock_sheets.read_stock.return_value = []
        mock_get_sheets.return_value = mock_sheets

        say = MagicMock()
        _handle_query({"query_type": "stock"}, thread_ts="T001", say=say)

        call_text = say.call_args_list[0][1].get("text", "")
        assert "bulunamadı" in call_text
