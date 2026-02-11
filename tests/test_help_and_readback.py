"""Tests for Item 3: Help command updates and post-action sheet link (Session 4).

- Help text includes the Google Sheet link
- Readback messages include "Detaylar için: [sheet link]"
- Sheet URL is configurable via GOOGLE_SHEET_URL config
"""

import pytest
from unittest.mock import patch

from app.config import get_google_sheet_url
from app.utils.formatters import format_help_text


class TestGoogleSheetUrlConfig:
    """Test that the sheet URL is available as a config variable."""

    def test_default_sheet_url(self):
        url = get_google_sheet_url()
        assert url.startswith("https://docs.google.com/spreadsheets/")

    @patch.dict("os.environ", {"GOOGLE_SHEET_URL": "https://example.com/sheet"})
    def test_custom_sheet_url_from_env(self):
        url = get_google_sheet_url()
        assert url == "https://example.com/sheet"


class TestHelpTextIncludesSheetLink:
    """Test that help output includes the Google Sheet link."""

    def test_help_contains_sheet_url(self):
        blocks = format_help_text()
        text = _blocks_to_text(blocks)
        assert "docs.google.com/spreadsheets" in text

    def test_help_mentions_responsible_not_technician(self):
        """Verify help text reflects the Item 2 rename."""
        blocks = format_help_text()
        text = _blocks_to_text(blocks).lower()
        # Should not reference "teknisyen" (Turkish for technician) as a field
        # The word may appear in role descriptions but not as a data field label
        assert "technician" not in text


class TestReadbackIncludesSheetLink:
    """Test that readback messages include the sheet link."""

    def test_readback_appends_sheet_link(self):
        from app.handlers.actions import _build_readback_with_link
        readback = "📊 `MIG-TR-01` (`SUP-003`): 5 toplam kayıt, 2 açık ticket."
        result = _build_readback_with_link(readback)
        assert "Detaylar için:" in result
        assert "docs.google.com/spreadsheets" in result

    def test_readback_empty_returns_just_link(self):
        from app.handlers.actions import _build_readback_with_link
        result = _build_readback_with_link("")
        assert "Detaylar için:" in result


# --- Helpers ---

def _blocks_to_text(blocks: list[dict]) -> str:
    parts = []
    for block in blocks:
        if "text" in block:
            t = block["text"]
            if isinstance(t, dict):
                parts.append(t.get("text", ""))
            else:
                parts.append(str(t))
        for field in block.get("fields", []):
            if isinstance(field, dict):
                parts.append(field.get("text", ""))
    return "\n".join(parts)
