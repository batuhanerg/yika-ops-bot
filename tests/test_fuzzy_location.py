"""Tests for fuzzy stock location matching with Turkish suffix stripping.

Problem B: "Istanbuldan geldi" and "Istanbul ofis" should match "Istanbul Office".
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.handlers.common import thread_store


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _cleanup_threads():
    yield
    for i in range(1, 30):
        thread_store.clear(f"ts_loc_{i:03d}")


_STOCK_DATA = [
    {"Location": "Istanbul Office", "Device Type": "Tag", "Qty": 25},
    {"Location": "Istanbul Office", "Device Type": "Gateway", "Qty": 3},
    {"Location": "Adana Storage", "Device Type": "Gateway", "Qty": 5},
    {"Location": "Adana Storage", "Device Type": "Tag", "Qty": 12},
]


def _mock_sheets():
    mock = MagicMock()
    mock.read_stock.return_value = list(_STOCK_DATA)
    mock.find_stock_row_index.return_value = 2
    return mock


def _all_say_texts(say_mock) -> list[str]:
    texts = []
    for call in say_mock.call_args_list:
        text = call.kwargs.get("text", "")
        if not text and call.args:
            text = str(call.args[0])
        texts.append(text)
    return texts


# ===========================================================================
# Direct fuzzy matching function
# ===========================================================================


class TestFuzzyLocationMatching:
    """Test _match_stock_location directly."""

    def test_exact_name_matches(self):
        from app.handlers.common import _match_stock_location
        locations = ["Istanbul Office", "Adana Storage"]
        result = _match_stock_location("Istanbul Office'ten geldi", locations)
        assert result == ["Istanbul Office"]

    def test_istanbuldan_geldi(self):
        """Turkish suffix -dan on city name."""
        from app.handlers.common import _match_stock_location
        locations = ["Istanbul Office", "Adana Storage"]
        result = _match_stock_location("Istanbuldan geldi", locations)
        assert result == ["Istanbul Office"]

    def test_istanbul_ofis(self):
        """Partial match: city keyword is enough."""
        from app.handlers.common import _match_stock_location
        locations = ["Istanbul Office", "Adana Storage"]
        result = _match_stock_location("Istanbul ofis", locations)
        assert result == ["Istanbul Office"]

    def test_turkish_i_istanbul(self):
        """Turkish İstanbul matches Istanbul Office."""
        from app.handlers.common import _match_stock_location
        locations = ["Istanbul Office", "Adana Storage"]
        result = _match_stock_location("İstanbul", locations)
        assert result == ["Istanbul Office"]

    def test_adana_depodan(self):
        """'adana depodan' matches Adana Storage."""
        from app.handlers.common import _match_stock_location
        locations = ["Istanbul Office", "Adana Storage"]
        result = _match_stock_location("adana depodan", locations)
        assert result == ["Adana Storage"]

    def test_adanadan_geldi(self):
        """'adanadan geldi' — city + suffix -dan."""
        from app.handlers.common import _match_stock_location
        locations = ["Istanbul Office", "Adana Storage"]
        result = _match_stock_location("adanadan geldi", locations)
        assert result == ["Adana Storage"]

    def test_unknown_location_empty(self):
        from app.handlers.common import _match_stock_location
        locations = ["Istanbul Office", "Adana Storage"]
        result = _match_stock_location("Ankara depodan geldi", locations)
        assert result == []

    def test_ambiguous_match_returns_multiple(self):
        """If keyword matches multiple locations, return all."""
        from app.handlers.common import _match_stock_location
        locations = ["Istanbul Office", "Istanbul Warehouse"]
        result = _match_stock_location("Istanbuldan geldi", locations)
        assert len(result) == 2
        assert "Istanbul Office" in result
        assert "Istanbul Warehouse" in result

    def test_apostrophe_suffix(self):
        """'İstanbul'dan' with apostrophe."""
        from app.handlers.common import _match_stock_location
        locations = ["Istanbul Office", "Adana Storage"]
        result = _match_stock_location("İstanbul'dan geldi", locations)
        assert result == ["Istanbul Office"]

    def test_suffix_den(self):
        """'-den' suffix variant."""
        from app.handlers.common import _match_stock_location
        locations = ["Istanbul Office", "Adana Storage"]
        result = _match_stock_location("adanaden geldi", locations)
        # 'adanaden' → strip '-den' → 'adana'
        assert result == ["Adana Storage"]


# ===========================================================================
# Integration: fuzzy location in handle_stock_reply
# ===========================================================================


class TestStockReplyFuzzyIntegration:
    """Test fuzzy location matching through handle_stock_reply."""

    def test_fuzzy_match_updates_stock(self):
        """'Istanbuldan geldi' triggers stock update at Istanbul Office."""
        from app.handlers.common import handle_stock_reply

        state = {
            "stock_prompt_pending": True,
            "stock_entries": [
                {"device_type": "Tag", "qty": 10, "site_id": "ASM-TR-01", "direction": "subtract"},
            ],
            "user_id": "U_TEST",
            "language": "tr",
        }
        thread_store.set("ts_loc_001", state)
        say = MagicMock()

        with patch("app.handlers.common.get_sheets") as mock_sheets:
            m = _mock_sheets()
            mock_sheets.return_value = m
            result = handle_stock_reply("Istanbuldan geldi", "ts_loc_001", state, say, "U_TEST")

        assert result is True
        m.update_stock.assert_called_once()

    def test_turkish_i_matches(self):
        """'İstanbul' with Turkish İ triggers stock update."""
        from app.handlers.common import handle_stock_reply

        state = {
            "stock_prompt_pending": True,
            "stock_entries": [
                {"device_type": "Tag", "qty": 5, "site_id": "ASM-TR-01", "direction": "subtract"},
            ],
            "user_id": "U_TEST",
            "language": "tr",
        }
        thread_store.set("ts_loc_002", state)
        say = MagicMock()

        with patch("app.handlers.common.get_sheets") as mock_sheets:
            m = _mock_sheets()
            mock_sheets.return_value = m
            result = handle_stock_reply("İstanbul ofisten geldi", "ts_loc_002", state, say, "U_TEST")

        assert result is True
        m.update_stock.assert_called_once()

    def test_ambiguous_asks_clarification(self):
        """If multiple locations match, asks for clarification."""
        from app.handlers.common import handle_stock_reply

        state = {
            "stock_prompt_pending": True,
            "stock_entries": [
                {"device_type": "Tag", "qty": 5, "site_id": "ASM-TR-01", "direction": "subtract"},
            ],
            "user_id": "U_TEST",
            "language": "tr",
        }
        thread_store.set("ts_loc_003", state)
        say = MagicMock()

        with patch("app.handlers.common.get_sheets") as mock_sheets:
            m = MagicMock()
            # Two Istanbul locations
            m.read_stock.return_value = [
                {"Location": "Istanbul Office", "Device Type": "Tag", "Qty": 25},
                {"Location": "Istanbul Warehouse", "Device Type": "Tag", "Qty": 10},
            ]
            mock_sheets.return_value = m
            result = handle_stock_reply("Istanbuldan geldi", "ts_loc_003", state, say, "U_TEST")

        assert result is True
        all_texts = _all_say_texts(say)
        # Should list both options for clarification
        assert any("Istanbul Office" in t and "Istanbul Warehouse" in t for t in all_texts), \
            f"Clarification not shown: {all_texts}"
        # Should NOT update stock
        m.update_stock.assert_not_called()

    def test_unknown_still_lists_available(self):
        """Unknown location with no fuzzy match → lists available."""
        from app.handlers.common import handle_stock_reply

        state = {
            "stock_prompt_pending": True,
            "stock_entries": [
                {"device_type": "Tag", "qty": 5, "site_id": "ASM-TR-01", "direction": "subtract"},
            ],
            "user_id": "U_TEST",
            "language": "tr",
        }
        thread_store.set("ts_loc_004", state)
        say = MagicMock()

        with patch("app.handlers.common.get_sheets") as mock_sheets:
            mock_sheets.return_value = _mock_sheets()
            result = handle_stock_reply("Ankaradan geldi", "ts_loc_004", state, say, "U_TEST")

        assert result is True
        all_texts = _all_say_texts(say)
        assert any("Istanbul Office" in t or "Adana Storage" in t for t in all_texts)
