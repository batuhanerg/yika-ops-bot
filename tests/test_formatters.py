"""Tests for Slack Block Kit message formatting."""

import pytest

from app.utils.formatters import (
    format_confirmation_message,
    format_query_response,
    format_error_message,
    format_help_text,
)


class TestConfirmationMessage:
    def test_contains_all_fields(self):
        data = {
            "operation": "log_support",
            "site_id": "ASM-TR-01",
            "received_date": "2025-01-15",
            "type": "Visit",
            "status": "Resolved",
            "root_cause": "HW Fault (Production)",
            "issue_summary": "2 tag değiştirildi",
            "responsible": "Gökhan",
            "resolved_date": "2025-01-15",
            "resolution": "Kartlar değiştirildi",
        }
        blocks = format_confirmation_message(data)
        text = _blocks_to_text(blocks)

        assert "ASM-TR-01" in text
        assert "2025-01-15" in text
        assert "Visit" in text
        assert "Resolved" in text
        assert "HW Fault (Production)" in text
        assert "Gökhan" in text

    def test_has_confirm_cancel_buttons(self):
        data = {
            "operation": "log_support",
            "site_id": "ASM-TR-01",
            "received_date": "2025-01-15",
            "type": "Visit",
            "status": "Open",
            "root_cause": "User Error",
            "issue_summary": "Test issue",
            "responsible": "Batu",
        }
        blocks = format_confirmation_message(data)

        # Find actions block with buttons
        actions_block = None
        for block in blocks:
            if block.get("type") == "actions":
                actions_block = block
                break

        assert actions_block is not None, "No actions block found"
        buttons = actions_block["elements"]
        action_ids = [b["action_id"] for b in buttons]
        assert "confirm_action" in action_ids
        assert "cancel_action" in action_ids

        # Check button styles
        confirm_btn = next(b for b in buttons if b["action_id"] == "confirm_action")
        cancel_btn = next(b for b in buttons if b["action_id"] == "cancel_action")
        assert confirm_btn["style"] == "primary"
        assert cancel_btn["style"] == "danger"


class TestQueryResponse:
    def test_site_summary_formatted(self):
        summary = {
            "site_id": "ASM-TR-01",
            "customer": "Anadolu Sağlık Merkezi",
            "status": "Active",
            "open_issues": 2,
            "total_devices": 70,
            "last_visit": "2025-01-15",
        }
        blocks = format_query_response("site_summary", summary)
        text = _blocks_to_text(blocks)

        assert "ASM-TR-01" in text
        assert "Anadolu" in text
        assert "Active" in text


class TestErrorMessage:
    def test_unknown_site_error(self):
        blocks = format_error_message(
            "unknown_site",
            site_name="Bilinmeyen Firma",
            available_sites=["ASM-TR-01", "MIG-TR-01", "MCD-EG-01"],
        )
        text = _blocks_to_text(blocks)

        assert "Bilinmeyen Firma" in text or "bulunamadı" in text.lower()
        assert "ASM-TR-01" in text
        assert "MIG-TR-01" in text


class TestHelpText:
    def test_help_is_in_turkish(self):
        blocks = format_help_text()
        text = _blocks_to_text(blocks)

        assert "Mustafa" in text
        assert "Kullanım Kılavuzu" in text or "Kılavuz" in text

    def test_help_contains_all_sections(self):
        blocks = format_help_text()
        text = _blocks_to_text(blocks)

        # Should mention all operation types
        assert "Kurulum" in text or "kurulum" in text
        assert "Destek" in text or "destek" in text
        assert "Donanım" in text or "donanım" in text
        assert "Stok" in text or "stok" in text
        assert "Sorgula" in text or "sorgula" in text


def _blocks_to_text(blocks: list[dict]) -> str:
    """Extract all text content from Slack Block Kit blocks for assertion."""
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
            else:
                parts.append(str(field))
        for element in block.get("elements", []):
            if "text" in element:
                t = element["text"]
                if isinstance(t, dict):
                    parts.append(t.get("text", ""))
    return "\n".join(parts)
